"""
Lambda Handler — Transacciones (Órdenes de Trabajo)

Rutas manejadas:
  GET    /transacciones
  POST   /transacciones
  GET    /transacciones/{id}
  PUT    /transacciones/{id}
  PATCH  /transacciones/{id}/estado
  POST   /transacciones/{id}/adjunto   ← STUB: upload a S3
  DELETE /transacciones/{id}

DIFERENCIAS vs monolito:
1. El upload de archivos ya no guarda en disco local → genera presigned URL de S3.
   GAP CRÍTICO: el cliente debe hacer el upload directamente a S3 con la presigned URL.
   El monolito recibía el archivo en el mismo request (multipart/form-data).
2. Las notificaciones usan SES en lugar del singleton en memoria.
3. Se eliminó el import cross-blueprint (verificar_cliente_existe).
4. La generación de número de orden usa uuid para evitar colisiones.

GAP: El upload de archivos cambia el contrato de la API — el cliente necesita
     dos requests en lugar de uno. Esto requiere cambios en el frontend.
"""
import logging
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.db import DBSession
from shared.models import OrdenTrabajo, DetalleOrden, Cliente, Servicio
from shared.auth_utils import requerir_jwt, requerir_admin
from shared.cache import cache_service
from shared.notificaciones import (
    notificar_orden_creada, notificar_cambio_estado, notificar_orden_lista
)
from shared.response import ok, error, get_body, get_path_param, get_query_param, paginar_query
from marshmallow import Schema, fields, validate, ValidationError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ESTADOS_VALIDOS = ['pendiente', 'en_diagnostico', 'en_reparacion', 'completado', 'cancelado']
TRANSICIONES = {
    'pendiente':      ['en_diagnostico', 'cancelado'],
    'en_diagnostico': ['en_reparacion', 'cancelado'],
    'en_reparacion':  ['completado', 'cancelado'],
    'completado':     [],
    'cancelado':      [],
}


class DetalleOrdenSchema(Schema):
    servicio_id = fields.Integer(required=True)
    precio_unitario = fields.Decimal(required=True, places=2, validate=validate.Range(min=0))
    cantidad = fields.Integer(load_default=1, validate=validate.Range(min=1))
    notas = fields.String(allow_none=True, load_default=None)

class OrdenTrabajoSchema(Schema):
    cliente_id = fields.Integer(required=True)
    tecnico_id = fields.Integer(allow_none=True, load_default=None)
    descripcion_problema = fields.String(required=True, validate=validate.Length(min=10))
    tipo_equipo = fields.String(allow_none=True, load_default=None)
    marca_equipo = fields.String(allow_none=True, load_default=None)
    modelo_equipo = fields.String(allow_none=True, load_default=None)
    fecha_estimada = fields.DateTime(allow_none=True, load_default=None)
    detalles = fields.List(fields.Nested(DetalleOrdenSchema), load_default=[])

class OrdenUpdateSchema(Schema):
    tecnico_id = fields.Integer(allow_none=True)
    descripcion_problema = fields.String(validate=validate.Length(min=10))
    notas_tecnico = fields.String(allow_none=True)
    tipo_equipo = fields.String(allow_none=True)
    marca_equipo = fields.String(allow_none=True)
    modelo_equipo = fields.String(allow_none=True)
    fecha_estimada = fields.DateTime(allow_none=True)

class CambioEstadoSchema(Schema):
    estado = fields.String(required=True, validate=validate.OneOf(ESTADOS_VALIDOS))
    notas_tecnico = fields.String(allow_none=True, load_default=None)

orden_schema = OrdenTrabajoSchema()
orden_update_schema = OrdenUpdateSchema()
cambio_estado_schema = CambioEstadoSchema()


def handler(event, context):
    method = event.get('httpMethod', '')
    path = event.get('path', '')
    path_params = event.get('pathParameters') or {}
    orden_id = path_params.get('id')

    logger.info(f"Transacciones handler: {method} {path}")

    try:
        if method == 'GET' and not orden_id:
            return _listar(event)
        elif method == 'POST' and not orden_id:
            return _crear(event)
        elif method == 'GET' and orden_id:
            return _obtener(event, int(orden_id))
        elif method == 'PUT' and orden_id:
            return _actualizar(event, int(orden_id))
        elif method == 'PATCH' and orden_id and path.endswith('/estado'):
            return _cambiar_estado(event, int(orden_id))
        elif method == 'POST' and orden_id and path.endswith('/adjunto'):
            return _solicitar_url_adjunto(event, int(orden_id))
        elif method == 'DELETE' and orden_id:
            return _cancelar(event, int(orden_id))
        elif method == 'OPTIONS':
            return ok(None)
        else:
            return error('Ruta no encontrada', 404)
    except Exception as e:
        logger.exception(f"Error en transacciones handler: {e}")
        return error('Error interno del servidor', 500)


def _listar(event):
    claims, err = requerir_jwt(event)
    if err:
        return err

    estado = get_query_param(event, 'estado', '').strip()
    cliente_id = get_query_param(event, 'cliente_id', '')
    tecnico_id = get_query_param(event, 'tecnico_id', '')
    fecha_desde = get_query_param(event, 'fecha_desde', '').strip()
    fecha_hasta = get_query_param(event, 'fecha_hasta', '').strip()
    pagina = int(get_query_param(event, 'pagina', '1'))
    por_pagina = int(get_query_param(event, 'por_pagina', '20'))

    with DBSession() as session:
        query = session.query(OrdenTrabajo)
        if estado:
            query = query.filter_by(estado=estado)
        if cliente_id:
            query = query.filter_by(cliente_id=int(cliente_id))
        if tecnico_id:
            query = query.filter_by(tecnico_id=int(tecnico_id))
        if fecha_desde:
            try:
                query = query.filter(OrdenTrabajo.fecha_ingreso >= datetime.fromisoformat(fecha_desde))
            except ValueError:
                return error('Formato de fecha_desde inválido (use YYYY-MM-DD)', 400)
        if fecha_hasta:
            try:
                query = query.filter(OrdenTrabajo.fecha_ingreso <= datetime.fromisoformat(fecha_hasta))
            except ValueError:
                return error('Formato de fecha_hasta inválido (use YYYY-MM-DD)', 400)

        query = query.order_by(OrdenTrabajo.fecha_ingreso.desc())
        resultado = paginar_query(query, pagina, por_pagina)
        resultado['items'] = [o.to_dict() for o in resultado['items']]

    return ok(resultado)


def _crear(event):
    claims, err = requerir_jwt(event)
    if err:
        return err

    try:
        datos = orden_schema.load(get_body(event))
    except ValidationError as e:
        return error('Datos inválidos', 422, e.messages)

    with DBSession() as session:
        cliente = session.query(Cliente).filter_by(id=datos['cliente_id'], activo=True).first()
        if not cliente:
            return error('Cliente no encontrado o inactivo', 404)

        for det in datos.get('detalles', []):
            svc = session.query(Servicio).filter_by(id=det['servicio_id'], activo=True).first()
            if not svc:
                return error(f"Servicio ID {det['servicio_id']} no encontrado o inactivo", 404)

        # GAP: generación de número de orden con UUID parcial para evitar colisiones
        # El monolito usaba timestamp (podía colisionar bajo concurrencia)
        numero_orden = f"OT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

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
        session.add(orden)
        session.flush()

        total = 0.0
        for det_data in datos.get('detalles', []):
            detalle = DetalleOrden(
                orden_id=orden.id,
                servicio_id=det_data['servicio_id'],
                precio_unitario=det_data['precio_unitario'],
                cantidad=det_data.get('cantidad', 1),
                notas=det_data.get('notas'),
            )
            session.add(detalle)
            total += float(det_data['precio_unitario']) * det_data.get('cantidad', 1)

        orden.total = total
        session.flush()
        datos_orden = orden.to_dict(incluir_detalles=True)
        cliente_email = cliente.email

    if cliente_email:
        notificar_orden_creada(cliente_email, numero_orden)

    logger.info(f"Orden creada: {numero_orden}")
    return ok(datos_orden, 'Orden de trabajo creada', 201)


def _obtener(event, orden_id: int):
    claims, err = requerir_jwt(event)
    if err:
        return err

    with DBSession() as session:
        orden = session.query(OrdenTrabajo).get(orden_id)
        if not orden:
            return error('Orden no encontrada', 404)
        datos = orden.to_dict(incluir_detalles=True)

    return ok(datos)


def _actualizar(event, orden_id: int):
    claims, err = requerir_jwt(event)
    if err:
        return err

    try:
        datos = orden_update_schema.load(get_body(event))
    except ValidationError as e:
        return error('Datos inválidos', 422, e.messages)

    with DBSession() as session:
        orden = session.query(OrdenTrabajo).get(orden_id)
        if not orden:
            return error('Orden no encontrada', 404)
        if orden.estado in ('completado', 'cancelado'):
            return error('No se puede editar una orden completada o cancelada', 409)
        for campo, valor in datos.items():
            setattr(orden, campo, valor)
        datos_orden = orden.to_dict(incluir_detalles=True)

    logger.info(f"Orden actualizada: {orden_id}")
    return ok(datos_orden, 'Orden actualizada')


def _cambiar_estado(event, orden_id: int):
    claims, err = requerir_jwt(event)
    if err:
        return err

    try:
        datos = cambio_estado_schema.load(get_body(event))
    except ValidationError as e:
        return error('Datos inválidos', 422, e.messages)

    with DBSession() as session:
        orden = session.query(OrdenTrabajo).get(orden_id)
        if not orden:
            return error('Orden no encontrada', 404)

        estado_nuevo = datos['estado']
        estado_anterior = orden.estado

        if estado_nuevo not in TRANSICIONES.get(estado_anterior, []):
            return error(
                f"Transición inválida: {estado_anterior} → {estado_nuevo}",
                409,
                {'transiciones_validas': TRANSICIONES.get(estado_anterior, [])}
            )

        orden.estado = estado_nuevo
        if datos.get('notas_tecnico'):
            orden.notas_tecnico = datos['notas_tecnico']
        if estado_nuevo == 'completado':
            orden.fecha_completado = datetime.utcnow()
            orden.total = orden.calcular_total()

        datos_orden = orden.to_dict()
        cliente_email = orden.cliente.email if orden.cliente else None
        numero_orden = orden.numero_orden
        total = float(orden.total)

    if cliente_email:
        if estado_nuevo == 'completado':
            notificar_orden_lista(cliente_email, numero_orden, total)
        else:
            notificar_cambio_estado(cliente_email, numero_orden, estado_nuevo, datos.get('notas_tecnico'))

    logger.info(f"Estado orden {orden_id}: {estado_anterior} → {estado_nuevo}")
    return ok(datos_orden, f'Estado actualizado a: {estado_nuevo}')


def _solicitar_url_adjunto(event, orden_id: int):
    """
    GAP CRÍTICO — CAMBIO DE CONTRATO DE API:
    El monolito recibía el archivo directamente (multipart/form-data) y lo guardaba en disco.
    En Lambda no hay filesystem persistente, por lo que se genera una presigned URL de S3.
    El cliente debe hacer un segundo request PUT a esa URL para subir el archivo.

    Flujo nuevo:
    1. Cliente llama POST /transacciones/{id}/adjunto con {"nombre_archivo": "foto.jpg"}
    2. Lambda genera presigned URL de S3 y la retorna
    3. Cliente hace PUT a la presigned URL con el archivo binario
    4. Cliente llama PATCH /transacciones/{id}/adjunto-confirmado con la clave S3

    GAP: El paso 4 (confirmación) no está implementado en este handler.
    GAP: La validación de extensión de archivo no puede hacerse antes del upload.
    GAP: Requiere que el bucket S3 exista y que el rol Lambda tenga permisos s3:PutObject.
    """
    claims, err = requerir_jwt(event)
    if err:
        return err

    body = get_body(event)
    nombre_archivo = body.get('nombre_archivo', '')
    if not nombre_archivo:
        return error('Se requiere el campo nombre_archivo', 400)

    EXTENSIONES_PERMITIDAS = {'pdf', 'png', 'jpg', 'jpeg', 'docx'}
    ext = nombre_archivo.rsplit('.', 1)[-1].lower() if '.' in nombre_archivo else ''
    if ext not in EXTENSIONES_PERMITIDAS:
        return error('Extensión no permitida', 400, {'permitidas': list(EXTENSIONES_PERMITIDAS)})

    bucket = os.environ.get('S3_BUCKET_ADJUNTOS')
    if not bucket:
        return error('Bucket S3 no configurado (S3_BUCKET_ADJUNTOS)', 500)

    try:
        import boto3
        s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        clave_s3 = f"adjuntos/orden_{orden_id}/{uuid.uuid4().hex}_{nombre_archivo}"

        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket,
                'Key': clave_s3,
                'ContentType': f'application/{ext}',
            },
            ExpiresIn=300,  # 5 minutos para completar el upload
        )

        # Guardar la clave S3 en la orden (pendiente de confirmación)
        with DBSession() as session:
            orden = session.query(OrdenTrabajo).get(orden_id)
            if not orden:
                return error('Orden no encontrada', 404)
            orden.archivo_adjunto = clave_s3

        return ok({
            'presigned_url': presigned_url,
            'clave_s3': clave_s3,
            'expira_en_segundos': 300,
            'instrucciones': 'Realice un PUT a presigned_url con el archivo binario como body',
        }, 'URL de upload generada')

    except Exception as e:
        logger.error(f"Error al generar presigned URL: {e}")
        return error('Error al generar URL de upload', 500)


def _cancelar(event, orden_id: int):
    claims, err = requerir_jwt(event)
    if err:
        return err

    with DBSession() as session:
        orden = session.query(OrdenTrabajo).get(orden_id)
        if not orden:
            return error('Orden no encontrada', 404)
        if orden.estado == 'completado':
            return error('No se puede cancelar una orden ya completada', 409)
        if orden.estado != 'pendiente' and claims.get('rol') != 'admin':
            return error('Solo un administrador puede cancelar órdenes en proceso', 403)
        orden.estado = 'cancelado'

    logger.info(f"Orden cancelada: {orden_id}")
    return ok(None, 'Orden cancelada')
