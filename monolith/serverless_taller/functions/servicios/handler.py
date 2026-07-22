"""
Lambda Handler — Servicios

Rutas manejadas:
  GET    /servicios
  GET    /servicios/categorias
  GET    /servicios/{id}
  POST   /servicios
  PUT    /servicios/{id}
  DELETE /servicios/{id}

DIFERENCIAS vs monolito:
- Endpoints públicos (sin JWT) se manejan omitiendo la validación.
- La constante CATEGORIAS ya no se importa desde otro módulo — está definida localmente.
  Esto resuelve el anti-patrón de import cross-blueprint del monolito.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.db import DBSession
from shared.models import Servicio
from shared.auth_utils import requerir_jwt, requerir_admin
from shared.cache import cache_service
from shared.response import ok, error, get_body, get_path_param, get_query_param, paginar_query
from marshmallow import Schema, fields, validate, ValidationError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CATEGORIAS = ['electronico', 'electrodomestico', 'computacion', 'celular', 'otro']


class ServicioSchema(Schema):
    id = fields.Integer(dump_only=True)
    nombre = fields.String(required=True, validate=validate.Length(min=3, max=150))
    descripcion = fields.String(allow_none=True, load_default=None)
    precio_base = fields.Decimal(required=True, places=2, validate=validate.Range(min=0))
    tiempo_estimado_horas = fields.Float(load_default=1.0, validate=validate.Range(min=0))
    categoria = fields.String(load_default='otro', validate=validate.OneOf(CATEGORIAS))

class ServicioUpdateSchema(Schema):
    nombre = fields.String(validate=validate.Length(min=3, max=150))
    descripcion = fields.String(allow_none=True)
    precio_base = fields.Decimal(places=2, validate=validate.Range(min=0))
    tiempo_estimado_horas = fields.Float(validate=validate.Range(min=0))
    categoria = fields.String(validate=validate.OneOf(CATEGORIAS))
    activo = fields.Boolean()

servicio_schema = ServicioSchema()
servicio_update_schema = ServicioUpdateSchema()


def handler(event, context):
    method = event.get('httpMethod', '')
    path = event.get('path', '')
    path_params = event.get('pathParameters') or {}
    servicio_id = path_params.get('id')

    logger.info(f"Servicios handler: {method} {path}")

    try:
        if method == 'GET' and path.endswith('/categorias'):
            return _listar_categorias(event)
        elif method == 'GET' and not servicio_id:
            return _listar(event)
        elif method == 'POST' and not servicio_id:
            return _crear(event)
        elif method == 'GET' and servicio_id:
            return _obtener(event, int(servicio_id))
        elif method == 'PUT' and servicio_id:
            return _actualizar(event, int(servicio_id))
        elif method == 'DELETE' and servicio_id:
            return _eliminar(event, int(servicio_id))
        elif method == 'OPTIONS':
            return ok(None)
        else:
            return error('Ruta no encontrada', 404)
    except Exception as e:
        logger.exception(f"Error en servicios handler: {e}")
        return error('Error interno del servidor', 500)


def _listar(event):
    # Endpoint público — sin JWT
    categoria = get_query_param(event, 'categoria', '').strip()
    q = get_query_param(event, 'q', '').strip()
    pagina = int(get_query_param(event, 'pagina', '1'))
    por_pagina = int(get_query_param(event, 'por_pagina', '20'))
    solo_activos = get_query_param(event, 'solo_activos', 'true').lower() == 'true'

    with DBSession() as session:
        query = session.query(Servicio)
        if solo_activos:
            query = query.filter_by(activo=True)
        if categoria:
            query = query.filter_by(categoria=categoria)
        if q:
            query = query.filter(Servicio.nombre.ilike(f'%{q}%'))
        query = query.order_by(Servicio.categoria, Servicio.nombre)
        resultado = paginar_query(query, pagina, por_pagina)
        resultado['items'] = [s.to_dict() for s in resultado['items']]

    return ok(resultado)


def _listar_categorias(event):
    clave = 'servicios_categorias'
    cached = cache_service.get(clave)
    if cached:
        return ok(cached)

    with DBSession() as session:
        categorias_con_conteo = []
        for cat in CATEGORIAS:
            conteo = session.query(Servicio).filter_by(categoria=cat, activo=True).count()
            categorias_con_conteo.append({'categoria': cat, 'cantidad_servicios': conteo})

    cache_service.set(clave, categorias_con_conteo, ttl_segundos=600)
    return ok(categorias_con_conteo)


def _obtener(event, servicio_id: int):
    clave = f'servicio_{servicio_id}'
    cached = cache_service.get(clave)
    if cached:
        return ok(cached)

    with DBSession() as session:
        servicio = session.query(Servicio).get(servicio_id)
        if not servicio:
            return error('Servicio no encontrado', 404)
        datos = servicio.to_dict()

    cache_service.set(clave, datos, ttl_segundos=300)
    return ok(datos)


def _crear(event):
    claims, err = requerir_jwt(event)
    if err:
        return err

    try:
        datos = servicio_schema.load(get_body(event))
    except ValidationError as e:
        return error('Datos inválidos', 422, e.messages)

    with DBSession() as session:
        servicio = Servicio(
            nombre=datos['nombre'],
            descripcion=datos.get('descripcion'),
            precio_base=datos['precio_base'],
            tiempo_estimado_horas=datos.get('tiempo_estimado_horas', 1.0),
            categoria=datos.get('categoria', 'otro'),
        )
        session.add(servicio)
        session.flush()
        datos_servicio = servicio.to_dict()

    cache_service.invalidar_patron('servicio')
    cache_service.delete('servicios_categorias')
    logger.info(f"Servicio creado: {datos_servicio['id']}")
    return ok(datos_servicio, 'Servicio creado', 201)


def _actualizar(event, servicio_id: int):
    claims, err = requerir_jwt(event)
    if err:
        return err

    try:
        datos = servicio_update_schema.load(get_body(event))
    except ValidationError as e:
        return error('Datos inválidos', 422, e.messages)

    with DBSession() as session:
        servicio = session.query(Servicio).get(servicio_id)
        if not servicio:
            return error('Servicio no encontrado', 404)
        for campo, valor in datos.items():
            setattr(servicio, campo, valor)
        datos_servicio = servicio.to_dict()

    cache_service.delete(f'servicio_{servicio_id}')
    cache_service.delete('servicios_categorias')
    logger.info(f"Servicio actualizado: {servicio_id}")
    return ok(datos_servicio, 'Servicio actualizado')


def _eliminar(event, servicio_id: int):
    claims, err = requerir_jwt(event)
    if err:
        return err

    err_admin = requerir_admin(claims)
    if err_admin:
        return err_admin

    with DBSession() as session:
        servicio = session.query(Servicio).get(servicio_id)
        if not servicio:
            return error('Servicio no encontrado', 404)
        servicio.activo = False

    cache_service.delete(f'servicio_{servicio_id}')
    cache_service.delete('servicios_categorias')
    logger.info(f"Servicio desactivado: {servicio_id}")
    return ok(None, 'Servicio desactivado')
