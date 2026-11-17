"""
Blueprint de Transacciones (Órdenes de Trabajo) — Taller PyME

Este es el módulo central del negocio. Tiene acoplamiento con clientes y servicios.

Endpoints:
  GET    /api/transacciones/                 — Listar órdenes (filtros + paginación)
  POST   /api/transacciones/                 — Crear orden de trabajo
  GET    /api/transacciones/<id>             — Obtener orden completa
  PUT    /api/transacciones/<id>             — Actualizar datos de orden
  PATCH  /api/transacciones/<id>/estado      — Cambiar estado de la orden
  POST   /api/transacciones/<id>/adjunto     — Subir archivo adjunto
  DELETE /api/transacciones/<id>             — Cancelar orden (solo admin)

Anti-patrones intencionales:
- Importa helper directamente del blueprint de clientes
- Calcula el total dentro del controlador (lógica de negocio mezclada)
- Usa el notificacion_service como efecto secundario en el controlador
"""
import os
import logging
from datetime import datetime
from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from marshmallow import ValidationError
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.orden_trabajo import OrdenTrabajo, DetalleOrden
from app.models.servicio import Servicio
from app.utils.helpers import (
    paginar_query, respuesta_ok, respuesta_error,
    extension_permitida, generar_numero_orden
)
from app.services.cache_service import cache_service
from app.services.notificacion_service import notificacion_service

# Anti-patrón: importación directa de función del blueprint de clientes
from app.blueprints.clientes.routes import verificar_cliente_existe

from .schemas import orden_schema, orden_update_schema, cambio_estado_schema

logger = logging.getLogger(__name__)

transacciones_bp = Blueprint('transacciones', __name__)


@transacciones_bp.route('/', methods=['GET'])
@jwt_required()
def listar_ordenes():
    """
    Lista órdenes de trabajo con filtros.
    Query params: estado, cliente_id, tecnico_id, fecha_desde, fecha_hasta, pagina, por_pagina
    """
    estado = request.args.get('estado', '').strip()
    cliente_id = request.args.get('cliente_id', type=int)
    tecnico_id = request.args.get('tecnico_id', type=int)
    fecha_desde = request.args.get('fecha_desde', '').strip()
    fecha_hasta = request.args.get('fecha_hasta', '').strip()
    pagina = int(request.args.get('pagina', 1))
    por_pagina = int(request.args.get('por_pagina', 20))

    query = OrdenTrabajo.query

    if estado:
        query = query.filter_by(estado=estado)
    if cliente_id:
        query = query.filter_by(cliente_id=cliente_id)
    if tecnico_id:
        query = query.filter_by(tecnico_id=tecnico_id)
    if fecha_desde:
        try:
            query = query.filter(
                OrdenTrabajo.fecha_ingreso >= datetime.fromisoformat(fecha_desde)
            )
        except ValueError:
            return respuesta_error('Formato de fecha_desde inválido (use YYYY-MM-DD)', 400)
    if fecha_hasta:
        try:
            query = query.filter(
                OrdenTrabajo.fecha_ingreso <= datetime.fromisoformat(fecha_hasta)
            )
        except ValueError:
            return respuesta_error('Formato de fecha_hasta inválido (use YYYY-MM-DD)', 400)

    query = query.order_by(OrdenTrabajo.fecha_ingreso.desc())
    resultado = paginar_query(query, pagina, por_pagina)
    resultado['items'] = [o.to_dict() for o in resultado['items']]

    return respuesta_ok(resultado)


@transacciones_bp.route('/', methods=['POST'])
@jwt_required()
def crear_orden():
    """
    Crea una nueva orden de trabajo con sus detalles.

    Anti-patrón: toda la lógica de creación está en el controlador,
    incluyendo cálculo del total y disparo de notificación.
    Candidato obvio para extraer a Lambda via Strangler Fig.
    """
    try:
        datos = orden_schema.load(request.get_json() or {})
    except ValidationError as e:
        return respuesta_error('Datos inválidos', 422, e.messages)

    # Verificar que el cliente existe (acoplamiento cross-blueprint)
    cliente = verificar_cliente_existe(datos['cliente_id'])
    if not cliente:
        return respuesta_error('Cliente no encontrado o inactivo', 404)

    # Verificar servicios de los detalles
    detalles_data = datos.get('detalles', [])
    for det in detalles_data:
        svc = Servicio.query.filter_by(id=det['servicio_id'], activo=True).first()
        if not svc:
            return respuesta_error(
                f"Servicio ID {det['servicio_id']} no encontrado o inactivo", 404
            )

    # Generar número de orden único
    numero_orden = generar_numero_orden()

    # Crear la orden
    orden = OrdenTrabajo(
        numero_orden=numero_orden,
        cliente_id=datos['cliente_id'],
        tecnico_id=datos.get('tecnico_id'),
        descripcion_problema=datos['descripcion_problema'],
        tipo_equipo=datos.get('tipo_equipo'),
        marca_equipo=datos.get('marca_equipo'),
        modelo_equipo=datos.get('modelo_equipo'),
        fecha_estimada=datos.get('fecha_estimada'),
        estado='pendiente',
    )
    db.session.add(orden)
    db.session.flush()  # Para obtener el ID antes del commit

    # Anti-patrón: lógica de negocio (cálculo de total) dentro del controlador
    total = 0.0
    for det_data in detalles_data:
        detalle = DetalleOrden(
            orden_id=orden.id,
            servicio_id=det_data['servicio_id'],
            precio_unitario=det_data['precio_unitario'],
            cantidad=det_data.get('cantidad', 1),
            notas=det_data.get('notas'),
        )
        db.session.add(detalle)
        total += float(det_data['precio_unitario']) * det_data.get('cantidad', 1)

    orden.total = total
    db.session.commit()

    # Efecto secundario: notificación al cliente (acoplamiento a servicio externo)
    if cliente.email:
        notificacion_service.notificar_orden_creada(cliente.email, numero_orden)

    logger.info(f"Orden creada: {numero_orden} para cliente {datos['cliente_id']}")
    return respuesta_ok(orden.to_dict(incluir_detalles=True), 'Orden de trabajo creada', 201)


@transacciones_bp.route('/<int:orden_id>', methods=['GET'])
@jwt_required()
def obtener_orden(orden_id: int):
    """Obtiene una orden de trabajo completa con todos sus detalles."""
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    return respuesta_ok(orden.to_dict(incluir_detalles=True))


@transacciones_bp.route('/<int:orden_id>', methods=['PUT'])
@jwt_required()
def actualizar_orden(orden_id: int):
    """Actualiza datos generales de la orden (no cambia estado ni detalles)."""
    orden = OrdenTrabajo.query.get_or_404(orden_id)

    if orden.estado in ('completado', 'cancelado'):
        return respuesta_error('No se puede editar una orden completada o cancelada', 409)

    try:
        datos = orden_update_schema.load(request.get_json() or {})
    except ValidationError as e:
        return respuesta_error('Datos inválidos', 422, e.messages)

    for campo, valor in datos.items():
        setattr(orden, campo, valor)

    db.session.commit()
    logger.info(f"Orden actualizada: {orden_id}")
    return respuesta_ok(orden.to_dict(incluir_detalles=True), 'Orden actualizada')


@transacciones_bp.route('/<int:orden_id>/estado', methods=['PATCH'])
@jwt_required()
def cambiar_estado_orden(orden_id: int):
    """
    Cambia el estado de una orden de trabajo.
    Dispara notificación al cliente si tiene email.
    Candidato fuerte para extraer a Lambda (Strangler Fig).
    """
    orden = OrdenTrabajo.query.get_or_404(orden_id)

    try:
        datos = cambio_estado_schema.load(request.get_json() or {})
    except ValidationError as e:
        return respuesta_error('Datos inválidos', 422, e.messages)

    estado_nuevo = datos['estado']
    estado_anterior = orden.estado

    # Validar transiciones de estado permitidas
    transiciones = {
        'pendiente':       ['en_diagnostico', 'cancelado'],
        'en_diagnostico':  ['en_reparacion', 'cancelado'],
        'en_reparacion':   ['completado', 'cancelado'],
        'completado':      [],
        'cancelado':       [],
    }
    if estado_nuevo not in transiciones.get(estado_anterior, []):
        return respuesta_error(
            f"Transición inválida: {estado_anterior} → {estado_nuevo}",
            409,
            {'transiciones_validas': transiciones.get(estado_anterior, [])}
        )

    orden.estado = estado_nuevo
    if datos.get('notas_tecnico'):
        orden.notas_tecnico = datos['notas_tecnico']

    if estado_nuevo == 'completado':
        orden.fecha_completado = datetime.utcnow()
        # Recalcular total por si hubo cambios
        orden.total = orden.calcular_total()

    db.session.commit()

    # Anti-patrón: notificación disparada directamente desde el controlador
    cliente = orden.cliente
    if cliente and cliente.email:
        if estado_nuevo == 'completado':
            notificacion_service.notificar_orden_lista(
                cliente.email, orden.numero_orden, float(orden.total)
            )
        else:
            notificacion_service.notificar_cambio_estado(
                cliente.email, orden.numero_orden, estado_nuevo, datos.get('notas_tecnico')
            )

    logger.info(f"Estado orden {orden_id}: {estado_anterior} → {estado_nuevo}")
    return respuesta_ok(orden.to_dict(), f'Estado actualizado a: {estado_nuevo}')


@transacciones_bp.route('/<int:orden_id>/adjunto', methods=['POST'])
@jwt_required()
def subir_adjunto(orden_id: int):
    """
    Sube un archivo adjunto a la orden (foto del equipo, diagnóstico, etc.).

    Anti-patrón de migración: guarda el archivo en el sistema de archivos LOCAL.
    Al migrar a Lambda, esto debe cambiarse a S3. El Orquestador DevOps
    debe detectar este patrón como un bloqueador crítico de migración.
    """
    orden = OrdenTrabajo.query.get_or_404(orden_id)

    if 'archivo' not in request.files:
        return respuesta_error('No se encontró el archivo en la solicitud', 400)

    archivo = request.files['archivo']
    if archivo.filename == '':
        return respuesta_error('No se seleccionó ningún archivo', 400)

    if not extension_permitida(archivo.filename):
        return respuesta_error(
            'Extensión no permitida',
            400,
            {'permitidas': list(current_app.config['ALLOWED_EXTENSIONS'])}
        )

    # Guardar en disco local (anti-patrón para Serverless)
    nombre_seguro = secure_filename(archivo.filename)
    nombre_final = f"orden_{orden_id}_{nombre_seguro}"
    ruta_destino = os.path.join(current_app.config['UPLOAD_FOLDER'], nombre_final)
    archivo.save(ruta_destino)

    # Guardar ruta relativa en la BD
    orden.archivo_adjunto = nombre_final
    db.session.commit()

    logger.info(f"Adjunto subido para orden {orden_id}: {nombre_final}")
    return respuesta_ok(
        {'archivo': nombre_final, 'ruta': ruta_destino},
        'Archivo adjunto guardado'
    )


@transacciones_bp.route('/<int:orden_id>', methods=['DELETE'])
@jwt_required()
def cancelar_orden(orden_id: int):
    """
    Cancela una orden de trabajo.
    Solo administradores pueden cancelar órdenes ya iniciadas.
    """
    claims = get_jwt()
    orden = OrdenTrabajo.query.get_or_404(orden_id)

    if orden.estado == 'completado':
        return respuesta_error('No se puede cancelar una orden ya completada', 409)

    if orden.estado != 'pendiente' and claims.get('rol') != 'admin':
        return respuesta_error(
            'Solo un administrador puede cancelar órdenes en proceso', 403
        )

    orden.estado = 'cancelado'
    db.session.commit()

    logger.info(f"Orden cancelada: {orden_id} por usuario {get_jwt_identity()}")
    return respuesta_ok(None, 'Orden cancelada')
