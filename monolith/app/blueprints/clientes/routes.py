"""
Blueprint de Clientes — Taller PyME

Endpoints:
  GET    /api/clientes/               — Listar clientes (con búsqueda y paginación)
  POST   /api/clientes/               — Crear cliente
  GET    /api/clientes/<id>           — Obtener cliente por ID
  PUT    /api/clientes/<id>           — Actualizar cliente
  DELETE /api/clientes/<id>           — Desactivar cliente (soft delete)
  GET    /api/clientes/<id>/historial — Historial de órdenes de un cliente

Todos los endpoints requieren JWT.
"""
import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow import ValidationError

from app.extensions import db
from app.models.cliente import Cliente
from app.utils.helpers import paginar_query, respuesta_ok, respuesta_error
from app.services.cache_service import cache_service  # Uso del singleton de caché
from .schemas import cliente_schema, clientes_schema, cliente_update_schema

logger = logging.getLogger(__name__)

clientes_bp = Blueprint('clientes', __name__)


@clientes_bp.route('/', methods=['GET'])
@jwt_required()
def listar_clientes():
    """
    Lista clientes con filtros opcionales y paginación.
    Query params: q (búsqueda), pagina, por_pagina, activo
    """
    q = request.args.get('q', '').strip()
    pagina = int(request.args.get('pagina', 1))
    por_pagina = int(request.args.get('por_pagina', 20))
    solo_activos = request.args.get('activo', 'true').lower() == 'true'

    query = Cliente.query
    if solo_activos:
        query = query.filter_by(activo=True)
    if q:
        # Búsqueda por nombre, apellido o email
        filtro = f'%{q}%'
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(filtro),
                Cliente.apellido.ilike(filtro),
                Cliente.email.ilike(filtro),
                Cliente.telefono.ilike(filtro),
            )
        )

    query = query.order_by(Cliente.apellido, Cliente.nombre)
    resultado = paginar_query(query, pagina, por_pagina)
    resultado['items'] = clientes_schema.dump(resultado['items'])

    return respuesta_ok(resultado)


@clientes_bp.route('/', methods=['POST'])
@jwt_required()
def crear_cliente():
    """Crea un nuevo cliente. Invalida el caché de clientes."""
    try:
        datos = cliente_schema.load(request.get_json() or {})
    except ValidationError as e:
        return respuesta_error('Datos inválidos', 422, e.messages)

    # Verificar email duplicado si se proporcionó
    if datos.get('email'):
        if Cliente.query.filter_by(email=datos['email']).first():
            return respuesta_error('Ya existe un cliente con ese email', 409)

    cliente = Cliente(**datos)
    db.session.add(cliente)
    db.session.commit()

    # Invalidar caché de listado
    cache_service.invalidar_patron('clientes_lista')

    logger.info(f"Cliente creado: {cliente.id} - {cliente.nombre_completo()}")
    return respuesta_ok(cliente.to_dict(), 'Cliente creado', 201)


@clientes_bp.route('/<int:cliente_id>', methods=['GET'])
@jwt_required()
def obtener_cliente(cliente_id: int):
    """Obtiene un cliente por su ID. Usa caché para reducir consultas."""
    clave_cache = f'cliente_{cliente_id}'
    cached = cache_service.get(clave_cache)
    if cached:
        return respuesta_ok(cached)

    cliente = Cliente.query.get_or_404(cliente_id)
    datos = cliente.to_dict()
    cache_service.set(clave_cache, datos, ttl_segundos=120)
    return respuesta_ok(datos)


@clientes_bp.route('/<int:cliente_id>', methods=['PUT'])
@jwt_required()
def actualizar_cliente(cliente_id: int):
    """Actualiza los datos de un cliente."""
    cliente = Cliente.query.get_or_404(cliente_id)

    try:
        datos = cliente_update_schema.load(request.get_json() or {})
    except ValidationError as e:
        return respuesta_error('Datos inválidos', 422, e.messages)

    # Anti-patrón: asignación directa de campos sin capa de servicio
    for campo, valor in datos.items():
        setattr(cliente, campo, valor)

    db.session.commit()

    # Invalidar caché de este cliente
    cache_service.delete(f'cliente_{cliente_id}')
    cache_service.invalidar_patron('clientes_lista')

    logger.info(f"Cliente actualizado: {cliente_id}")
    return respuesta_ok(cliente.to_dict(), 'Cliente actualizado')


@clientes_bp.route('/<int:cliente_id>', methods=['DELETE'])
@jwt_required()
def eliminar_cliente(cliente_id: int):
    """
    Soft delete: desactiva el cliente sin eliminar registros históricos.
    Solo admins pueden eliminar.
    """
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return respuesta_error('Solo los administradores pueden eliminar clientes', 403)

    cliente = Cliente.query.get_or_404(cliente_id)
    cliente.activo = False
    db.session.commit()

    cache_service.delete(f'cliente_{cliente_id}')
    cache_service.invalidar_patron('clientes_lista')

    logger.info(f"Cliente desactivado: {cliente_id}")
    return respuesta_ok(None, 'Cliente desactivado')


@clientes_bp.route('/<int:cliente_id>/historial', methods=['GET'])
@jwt_required()
def historial_cliente(cliente_id: int):
    """
    Retorna el historial de órdenes de trabajo de un cliente.
    Anti-patrón: este endpoint toca modelos de transacciones directamente.
    Candidato fuerte para Strangler Fig.
    """
    cliente = Cliente.query.get_or_404(cliente_id)

    # Importación directa del modelo de transacciones (acoplamiento cross-módulo)
    from app.models.orden_trabajo import OrdenTrabajo

    ordenes = (
        OrdenTrabajo.query
        .filter_by(cliente_id=cliente_id)
        .order_by(OrdenTrabajo.fecha_ingreso.desc())
        .all()
    )

    return respuesta_ok({
        'cliente': cliente.to_dict(),
        'ordenes': [o.to_dict() for o in ordenes],
        'total_ordenes': len(ordenes),
    })


def verificar_cliente_existe(cliente_id: int) -> Cliente:
    """
    Helper exportado — reutilizado por el blueprint de transacciones.
    Anti-patrón: función de un blueprint importada por otro.
    """
    return Cliente.query.filter_by(id=cliente_id, activo=True).first()
