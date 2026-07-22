"""
Blueprint de Servicios — Taller PyME

Endpoints:
  GET    /api/servicios/            — Listar servicios (público, con filtro por categoría)
  GET    /api/servicios/categorias  — Listar categorías disponibles (público, cacheado)
  POST   /api/servicios/            — Crear servicio (requiere JWT)
  GET    /api/servicios/<id>        — Obtener servicio (público)
  PUT    /api/servicios/<id>        — Actualizar servicio (requiere JWT)
  DELETE /api/servicios/<id>        — Desactivar servicio (requiere JWT admin)
"""
import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt, verify_jwt_in_request
from marshmallow import ValidationError

from app.extensions import db
from app.models.servicio import Servicio
from app.utils.helpers import paginar_query, respuesta_ok, respuesta_error
from app.services.cache_service import cache_service
from .schemas import servicio_schema, servicios_schema, servicio_update_schema

logger = logging.getLogger(__name__)

servicios_bp = Blueprint('servicios', __name__)

# Lista de categorías disponibles — en producción vendría de la BD
CATEGORIAS = ['electronico', 'electrodomestico', 'computacion', 'celular', 'otro']


@servicios_bp.route('/', methods=['GET'])
def listar_servicios():
    """
    Lista servicios disponibles. Endpoint PÚBLICO — no requiere autenticación.
    Soporta filtrado por categoría y búsqueda por nombre.
    Query params: categoria, q, pagina, por_pagina, solo_activos
    """
    categoria = request.args.get('categoria', '').strip()
    q = request.args.get('q', '').strip()
    pagina = int(request.args.get('pagina', 1))
    por_pagina = int(request.args.get('por_pagina', 20))
    solo_activos = request.args.get('solo_activos', 'true').lower() == 'true'

    query = Servicio.query
    if solo_activos:
        query = query.filter_by(activo=True)
    if categoria:
        query = query.filter_by(categoria=categoria)
    if q:
        query = query.filter(Servicio.nombre.ilike(f'%{q}%'))

    query = query.order_by(Servicio.categoria, Servicio.nombre)
    resultado = paginar_query(query, pagina, por_pagina)
    resultado['items'] = servicios_schema.dump(resultado['items'])

    return respuesta_ok(resultado)


@servicios_bp.route('/categorias', methods=['GET'])
def listar_categorias():
    """
    Retorna las categorías de servicio disponibles.
    Endpoint PÚBLICO, respuesta cacheada en memoria.
    """
    clave = 'servicios_categorias'
    cached = cache_service.get(clave)
    if cached:
        return respuesta_ok(cached)

    # Anti-patrón: lógica de negocio directamente en el controlador
    categorias_con_conteo = []
    for cat in CATEGORIAS:
        conteo = Servicio.query.filter_by(categoria=cat, activo=True).count()
        categorias_con_conteo.append({
            'categoria': cat,
            'cantidad_servicios': conteo,
        })

    cache_service.set(clave, categorias_con_conteo, ttl_segundos=600)
    return respuesta_ok(categorias_con_conteo)


@servicios_bp.route('/<int:servicio_id>', methods=['GET'])
def obtener_servicio(servicio_id: int):
    """Obtiene un servicio por ID. Endpoint PÚBLICO."""
    clave = f'servicio_{servicio_id}'
    cached = cache_service.get(clave)
    if cached:
        return respuesta_ok(cached)

    servicio = Servicio.query.get_or_404(servicio_id)
    datos = servicio.to_dict()
    cache_service.set(clave, datos, ttl_segundos=300)
    return respuesta_ok(datos)


@servicios_bp.route('/', methods=['POST'])
@jwt_required()
def crear_servicio():
    """Crea un nuevo tipo de servicio. Requiere JWT."""
    try:
        datos = servicio_schema.load(request.get_json() or {})
    except ValidationError as e:
        return respuesta_error('Datos inválidos', 422, e.messages)

    servicio = Servicio(
        nombre=datos['nombre'],
        descripcion=datos.get('descripcion'),
        precio_base=datos['precio_base'],
        tiempo_estimado_horas=datos.get('tiempo_estimado_horas', 1.0),
        categoria=datos.get('categoria', 'otro'),
    )
    db.session.add(servicio)
    db.session.commit()

    # Invalidar cachés relacionados
    cache_service.invalidar_patron('servicio')
    cache_service.delete('servicios_categorias')

    logger.info(f"Servicio creado: {servicio.id} - {servicio.nombre}")
    return respuesta_ok(servicio.to_dict(), 'Servicio creado', 201)


@servicios_bp.route('/<int:servicio_id>', methods=['PUT'])
@jwt_required()
def actualizar_servicio(servicio_id: int):
    """Actualiza los datos de un servicio."""
    servicio = Servicio.query.get_or_404(servicio_id)

    try:
        datos = servicio_update_schema.load(request.get_json() or {})
    except ValidationError as e:
        return respuesta_error('Datos inválidos', 422, e.messages)

    for campo, valor in datos.items():
        setattr(servicio, campo, valor)

    db.session.commit()

    cache_service.delete(f'servicio_{servicio_id}')
    cache_service.delete('servicios_categorias')

    logger.info(f"Servicio actualizado: {servicio_id}")
    return respuesta_ok(servicio.to_dict(), 'Servicio actualizado')


@servicios_bp.route('/<int:servicio_id>', methods=['DELETE'])
@jwt_required()
def eliminar_servicio(servicio_id: int):
    """
    Desactiva un servicio (soft delete). Solo admins.
    No se eliminan físicamente para preservar historial de órdenes.
    """
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return respuesta_error('Solo administradores pueden eliminar servicios', 403)

    servicio = Servicio.query.get_or_404(servicio_id)
    servicio.activo = False
    db.session.commit()

    cache_service.delete(f'servicio_{servicio_id}')
    cache_service.delete('servicios_categorias')

    logger.info(f"Servicio desactivado: {servicio_id}")
    return respuesta_ok(None, 'Servicio desactivado')
