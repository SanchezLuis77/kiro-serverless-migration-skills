"""
Lambda Handler — Autenticación

Rutas manejadas (via API Gateway):
  POST /auth/register
  POST /auth/login
  GET  /auth/me
  POST /auth/logout
  PUT  /auth/password

DIFERENCIAS vs monolito Flask:
1. No hay Blueprint ni decoradores @jwt_required() — la validación es manual.
2. No hay sesión Flask (session[]) — se eliminó el doble mecanismo de sesión.
3. El routing se hace con if/elif sobre event['httpMethod'] + event['resource'].
4. La revocación de tokens usa DynamoDB en lugar de un set en memoria.

GAP: El routing manual con if/elif no escala bien. En el monolito Flask
     el routing era declarativo. Aquí se necesitaría un micro-framework
     (aws-lambda-powertools Router) para mantener legibilidad.
"""
import json
import logging
import os
import sys

# Asegurar que el directorio raíz esté en el path para imports relativos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.db import DBSession
from shared.models import Usuario
from shared.auth_utils import (
    requerir_jwt, crear_token, revocar_token,
    token_esta_revocado
)
from shared.response import ok, error, get_body
from marshmallow import Schema, fields, validate, ValidationError
import bcrypt as bcrypt_lib

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ── Schemas (replicados del monolito, sin dependencia de Flask) ──────────────

class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True, validate=validate.Length(min=6))

class RegistroSchema(Schema):
    nombre = fields.String(required=True, validate=validate.Length(min=2, max=100))
    apellido = fields.String(required=True, validate=validate.Length(min=2, max=100))
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True, validate=validate.Length(min=6))
    rol = fields.String(load_default='tecnico', validate=validate.OneOf(['admin', 'tecnico']))

class CambiarPasswordSchema(Schema):
    password_actual = fields.String(required=True, load_only=True)
    password_nueva = fields.String(required=True, load_only=True, validate=validate.Length(min=6))

login_schema = LoginSchema()
registro_schema = RegistroSchema()
cambiar_password_schema = CambiarPasswordSchema()


# ── Handler principal ────────────────────────────────────────────────────────

def handler(event, context):
    """
    Punto de entrada Lambda. Enruta según método HTTP y path.

    GAP: El routing manual es frágil. Con aws-lambda-powertools se haría:
        @app.post('/auth/register')
        def register(event): ...
    """
    method = event.get('httpMethod', '')
    path = event.get('path', '')

    logger.info(f"Auth handler: {method} {path}")

    try:
        if method == 'POST' and path.endswith('/register'):
            return _register(event)
        elif method == 'POST' and path.endswith('/login'):
            return _login(event)
        elif method == 'GET' and path.endswith('/me'):
            return _perfil(event)
        elif method == 'POST' and path.endswith('/logout'):
            return _logout(event)
        elif method == 'PUT' and path.endswith('/password'):
            return _cambiar_password(event)
        elif method == 'OPTIONS':
            return ok(None, 'CORS preflight')
        else:
            return error('Ruta no encontrada', 404)
    except Exception as e:
        logger.exception(f"Error no manejado en auth handler: {e}")
        return error('Error interno del servidor', 500)


def _register(event):
    try:
        datos = registro_schema.load(get_body(event))
    except ValidationError as e:
        return error('Datos inválidos', 422, e.messages)

    with DBSession() as session:
        if session.query(Usuario).filter_by(email=datos['email']).first():
            return error('El email ya está registrado', 409)

        password_hash = bcrypt_lib.hashpw(
            datos['password'].encode('utf-8'),
            bcrypt_lib.gensalt()
        ).decode('utf-8')

        usuario = Usuario(
            nombre=datos['nombre'],
            apellido=datos['apellido'],
            email=datos['email'],
            password_hash=password_hash,
            rol=datos.get('rol', 'tecnico'),
        )
        session.add(usuario)
        session.flush()
        datos_usuario = usuario.to_dict()

    logger.info(f"Usuario registrado: {datos['email']}")
    return ok(datos_usuario, 'Usuario registrado', 201)


def _login(event):
    try:
        datos = login_schema.load(get_body(event))
    except ValidationError as e:
        return error('Datos inválidos', 422, e.messages)

    with DBSession() as session:
        usuario = session.query(Usuario).filter_by(email=datos['email']).first()

        if not usuario:
            return error('Credenciales inválidas', 401)

        if not bcrypt_lib.checkpw(datos['password'].encode('utf-8'), usuario.password_hash.encode('utf-8')):
            return error('Credenciales inválidas', 401)

        if not usuario.activo:
            return error('Usuario desactivado, contacte al administrador', 403)

        token = crear_token(usuario.id, usuario.rol, usuario.email)
        datos_usuario = usuario.to_dict()

    logger.info(f"Login exitoso: {datos['email']}")
    return ok({'access_token': token, 'usuario': datos_usuario}, 'Login exitoso')


def _perfil(event):
    claims, err = requerir_jwt(event)
    if err:
        return err

    usuario_id = int(claims['sub'])
    with DBSession() as session:
        usuario = session.query(Usuario).get(usuario_id)
        if not usuario:
            return error('Usuario no encontrado', 404)
        datos = usuario.to_dict()

    return ok(datos)


def _logout(event):
    claims, err = requerir_jwt(event)
    if err:
        return err

    jti = claims.get('jti', '')
    exp = claims.get('exp', 0)
    revocar_token(jti, exp)

    logger.info(f"Logout: usuario {claims.get('sub')}")
    return ok(None, 'Sesión cerrada')


def _cambiar_password(event):
    claims, err = requerir_jwt(event)
    if err:
        return err

    try:
        datos = cambiar_password_schema.load(get_body(event))
    except ValidationError as e:
        return error('Datos inválidos', 422, e.messages)

    usuario_id = int(claims['sub'])
    with DBSession() as session:
        usuario = session.query(Usuario).get(usuario_id)
        if not usuario:
            return error('Usuario no encontrado', 404)

        if not bcrypt_lib.checkpw(datos['password_actual'].encode('utf-8'), usuario.password_hash.encode('utf-8')):
            return error('Contraseña actual incorrecta', 401)

        usuario.password_hash = bcrypt_lib.hashpw(
            datos['password_nueva'].encode('utf-8'),
            bcrypt_lib.gensalt()
        ).decode('utf-8')

    logger.info(f"Contraseña cambiada: usuario {usuario_id}")
    return ok(None, 'Contraseña actualizada')
