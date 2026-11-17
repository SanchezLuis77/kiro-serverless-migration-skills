"""
Lambda Handler — Clientes

Rutas manejadas:
  GET    /clientes
  POST   /clientes
  GET    /clientes/{id}
  PUT    /clientes/{id}
  DELETE /clientes/{id}
  GET    /clientes/{id}/historial

DIFERENCIAS vs monolito:
- Sin Blueprint Flask ni decoradores.
- Paginación reimplementada con offset/limit (sin .paginate() de Flask-SQLAlchemy).
- Caché usa Redis en lugar de dict en memoria.
- El historial de cliente ya no importa desde otro blueprint — usa el modelo directamente.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.db import DBSession
from shared.models import Cliente, OrdenTrabajo
from shared.auth_utils import requerir_jwt, requerir_admin
from shared.cache import cache_service
from shared.response import ok, error, get_body, get_path_param, get_query_param, paginar_query
from marshmallow import Schema, fields, validate, ValidationError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ClienteSchema(Schema):
    id = fields.Integer(dump_only=True)
    nombre = fields.String(required=True, validate=validate.Length(min=2, max=100))
    apellido = fields.String(required=True, validate=validate.Length(min=2, max=100))
    email = fields.Email(allow_none=True, load_default=None)
    telefono = fields.String(required=True, validate=validate.Length(min=7, max=20))
    direccion = fields.String(allow_none=True, load_default=None)
    documento_identidad = fields.String(allow_none=True, load_default=None)

class ClienteUpdateSchema(Schema):
    nombre = fields.String(validate=validate.Length(min=2, max=100))
    apellido = fields.String(validate=validate.Length(min=2, max=100))
    email = fields.Email(allow_none=True)
    telefono = fields.String(validate=validate.Length(min=7, max=20))
    direccion = fields.String(allow_none=True)
    documento_identidad = fields.String(allow_none=True)

cliente_schema = ClienteSchema()
cliente_update_schema = ClienteUpdateSchema()


def handler(event, context):
    method = event.get('httpMethod', '')
    path = event.get('path', '')
    path_params = event.get('pathParameters') or {}
    cliente_id = path_params.get('id')

    logger.info(f"Clientes handler: {method} {path}")

    try:
        if method == 'GET' and not cliente_id:
            return _listar(event)
        elif method == 'POST' and not cliente_id:
            return _crear(event)
        elif method == 'GET' and cliente_id and path.endswith('/historial'):
            return _historial(event, int(cliente_id))
        elif method == 'GET' and cliente_id:
            return _obtener(event, int(cliente_id))
        elif method == 'PUT' and cliente_id:
            return _actualizar(event, int(cliente_id))
        elif method == 'DELETE' and cliente_id:
            return _eliminar(event, int(cliente_id))
        elif method == 'OPTIONS':
            return ok(None)
        else:
            return error('Ruta no encontrada', 404)
    except Exception as e:
        logger.exception(f"Error en clientes handler: {e}")
        return error('Error interno del servidor', 500)


def _listar(event):
    claims, err = requerir_jwt(event)
    if err:
        return err

    q = get_query_param(event, 'q', '').strip()
    pagina = int(get_query_param(event, 'pagina', '1'))
    por_pagina = int(get_query_param(event, 'por_pagina', '20'))
    solo_activos = get_query_param(event, 'activo', 'true').lower() == 'true'

    with DBSession() as session:
        query = session.query(Cliente)
        if solo_activos:
            query = query.filter_by(activo=True)
        if q:
            filtro = f'%{q}%'
            query = query.filter(
                Cliente.nombre.ilike(filtro) |
                Cliente.apellido.ilike(filtro) |
                Cliente.email.ilike(filtro)
            )
        query = query.order_by(Cliente.apellido, Cliente.nombre)
        resultado = paginar_query(query, pagina, por_pagina)
        resultado['items'] = [c.to_dict() for c in resultado['items']]

    return ok(resultado)


def _crear(event):
    claims, err = requerir_jwt(event)
    if err:
        return err

    try:
        datos = cliente_schema.load(get_body(event))
    except ValidationError as e:
        return error('Datos inválidos', 422, e.messages)

    with DBSession() as session:
        if datos.get('email'):
            if session.query(Cliente).filter_by(email=datos['email']).first():
                return error('Ya existe un cliente con ese email', 409)

        cliente = Cliente(**datos)
        session.add(cliente)
        session.flush()
        datos_cliente = cliente.to_dict()

    cache_service.invalidar_patron('clientes_lista')
    logger.info(f"Cliente creado: {datos_cliente['id']}")
    return ok(datos_cliente, 'Cliente creado', 201)


def _obtener(event, cliente_id: int):
    claims, err = requerir_jwt(event)
    if err:
        return err

    clave = f'cliente_{cliente_id}'
    cached = cache_service.get(clave)
    if cached:
        return ok(cached)

    with DBSession() as session:
        cliente = session.query(Cliente).get(cliente_id)
        if not cliente:
            return error('Cliente no encontrado', 404)
        datos = cliente.to_dict()

    cache_service.set(clave, datos, ttl_segundos=120)
    return ok(datos)


def _actualizar(event, cliente_id: int):
    claims, err = requerir_jwt(event)
    if err:
        return err

    try:
        datos = cliente_update_schema.load(get_body(event))
    except ValidationError as e:
        return error('Datos inválidos', 422, e.messages)

    with DBSession() as session:
        cliente = session.query(Cliente).get(cliente_id)
        if not cliente:
            return error('Cliente no encontrado', 404)
        for campo, valor in datos.items():
            setattr(cliente, campo, valor)
        datos_cliente = cliente.to_dict()

    cache_service.delete(f'cliente_{cliente_id}')
    cache_service.invalidar_patron('clientes_lista')
    logger.info(f"Cliente actualizado: {cliente_id}")
    return ok(datos_cliente, 'Cliente actualizado')


def _eliminar(event, cliente_id: int):
    claims, err = requerir_jwt(event)
    if err:
        return err

    err_admin = requerir_admin(claims)
    if err_admin:
        return err_admin

    with DBSession() as session:
        cliente = session.query(Cliente).get(cliente_id)
        if not cliente:
            return error('Cliente no encontrado', 404)
        cliente.activo = False

    cache_service.delete(f'cliente_{cliente_id}')
    cache_service.invalidar_patron('clientes_lista')
    logger.info(f"Cliente desactivado: {cliente_id}")
    return ok(None, 'Cliente desactivado')


def _historial(event, cliente_id: int):
    claims, err = requerir_jwt(event)
    if err:
        return err

    with DBSession() as session:
        cliente = session.query(Cliente).get(cliente_id)
        if not cliente:
            return error('Cliente no encontrado', 404)

        ordenes = (
            session.query(OrdenTrabajo)
            .filter_by(cliente_id=cliente_id)
            .order_by(OrdenTrabajo.fecha_ingreso.desc())
            .all()
        )
        datos = {
            'cliente': cliente.to_dict(),
            'ordenes': [o.to_dict() for o in ordenes],
            'total_ordenes': len(ordenes),
        }

    return ok(datos)
