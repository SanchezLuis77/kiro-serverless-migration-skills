"""
Blueprint de Autenticación — Taller PyME

Endpoints:
  POST   /api/auth/register   — Registrar nuevo usuario (público)
  POST   /api/auth/login      — Iniciar sesión, retorna JWT (público)
  GET    /api/auth/me         — Perfil del usuario autenticado (protegido)
  POST   /api/auth/logout     — Invalidar sesión (protegido)
  PUT    /api/auth/password   — Cambiar contraseña (protegido)
"""
import logging
from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from marshmallow import ValidationError

from app.extensions import db, bcrypt
from app.models.usuario import Usuario
from app.utils.helpers import respuesta_ok, respuesta_error
from .schemas import login_schema, registro_schema, cambiar_password_schema

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# Conjunto en memoria de tokens revocados (anti-patrón: no persiste reinicios)
_tokens_revocados = set()


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Registra un nuevo usuario en el sistema.
    Endpoint público — en producción requeriría código de invitación.
    """
    try:
        datos = registro_schema.load(request.get_json() or {})
    except ValidationError as e:
        return respuesta_error('Datos inválidos', 422, e.messages)

    # Verificar que el email no exista
    if Usuario.query.filter_by(email=datos['email']).first():
        return respuesta_error('El email ya está registrado', 409)

    usuario = Usuario(
        nombre=datos['nombre'],
        apellido=datos['apellido'],
        email=datos['email'],
        password_hash=bcrypt.generate_password_hash(datos['password']).decode('utf-8'),
        rol=datos.get('rol', 'tecnico'),
    )
    db.session.add(usuario)
    db.session.commit()

    logger.info(f"Usuario registrado: {usuario.email} [{usuario.rol}]")
    return respuesta_ok(usuario.to_dict(), 'Usuario registrado', 201)


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Autentica un usuario y retorna un token JWT.
    También guarda el ID en la sesión Flask (doble mecanismo — típico de PyME).
    """
    try:
        datos = login_schema.load(request.get_json() or {})
    except ValidationError as e:
        return respuesta_error('Datos inválidos', 422, e.messages)

    usuario = Usuario.query.filter_by(email=datos['email']).first()

    if not usuario or not bcrypt.check_password_hash(usuario.password_hash, datos['password']):
        return respuesta_error('Credenciales inválidas', 401)

    if not usuario.activo:
        return respuesta_error('Usuario desactivado, contacte al administrador', 403)

    # Crear token JWT con datos extra en el payload
    token = create_access_token(
        identity=str(usuario.id),
        additional_claims={'rol': usuario.rol, 'email': usuario.email}
    )

    # Anti-patrón: también guardar en sesión Flask
    session['usuario_id'] = usuario.id
    session['usuario_rol'] = usuario.rol

    logger.info(f"Login exitoso: {usuario.email}")
    return respuesta_ok({
        'access_token': token,
        'usuario': usuario.to_dict(),
    }, 'Login exitoso')


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def perfil():
    """
    Retorna el perfil del usuario autenticado mediante JWT.
    Endpoint protegido.
    """
    usuario_id = int(get_jwt_identity())
    usuario = Usuario.query.get_or_404(usuario_id)
    return respuesta_ok(usuario.to_dict())


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Invalida el token JWT agregándolo a la lista negra en memoria.
    Anti-patrón: la lista se pierde al reiniciar el servidor.
    """
    jti = get_jwt()['jti']
    _tokens_revocados.add(jti)

    # Limpiar sesión Flask también
    session.clear()

    logger.info(f"Logout: usuario {get_jwt_identity()}")
    return respuesta_ok(None, 'Sesión cerrada')


@auth_bp.route('/password', methods=['PUT'])
@jwt_required()
def cambiar_password():
    """Permite al usuario autenticado cambiar su contraseña."""
    try:
        datos = cambiar_password_schema.load(request.get_json() or {})
    except ValidationError as e:
        return respuesta_error('Datos inválidos', 422, e.messages)

    usuario_id = int(get_jwt_identity())
    usuario = Usuario.query.get_or_404(usuario_id)

    if not bcrypt.check_password_hash(usuario.password_hash, datos['password_actual']):
        return respuesta_error('Contraseña actual incorrecta', 401)

    usuario.password_hash = bcrypt.generate_password_hash(datos['password_nueva']).decode('utf-8')
    db.session.commit()

    logger.info(f"Contraseña cambiada: {usuario.email}")
    return respuesta_ok(None, 'Contraseña actualizada')


def obtener_usuario_actual():
    """
    Helper reutilizable — devuelve el usuario desde el JWT.
    Anti-patrón: función exportada desde el blueprint, usada por otros módulos.
    """
    from flask_jwt_extended import verify_jwt_in_request
    verify_jwt_in_request()
    usuario_id = int(get_jwt_identity())
    return Usuario.query.get(usuario_id)
