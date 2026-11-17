"""
Blueprint de Reportes — Taller PyME

Este módulo tiene el mayor nivel de acoplamiento: consulta directamente
tablas de clientes, servicios y órdenes de trabajo. Es el mejor candidato
para migrar a Lambda (Strangler Fig) porque:
1. Es de solo lectura (no tiene efectos secundarios en BD)
2. Tiene dependencias de múltiples tablas
3. Sus resultados son ideales para cachear en ElastiCache/DynamoDB

Endpoints:
  GET  /api/reportes/resumen          — KPIs generales del negocio
  GET  /api/reportes/ingresos         — Ingresos por período (query params)
  GET  /api/reportes/tecnicos         — Rendimiento por técnico
  GET  /api/reportes/servicios-top    — Servicios más solicitados
  GET  /api/reportes/estado-cache     — Estado del caché en memoria (diagnóstico)
"""
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import func, desc

from app.extensions import db
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.servicio import Servicio
from app.models.orden_trabajo import OrdenTrabajo, DetalleOrden
from app.utils.helpers import respuesta_ok, respuesta_error
from app.services.cache_service import cache_service

# Anti-patrón: importación directa desde blueprint de servicios para reutilizar constante
from app.blueprints.servicios.routes import CATEGORIAS

logger = logging.getLogger(__name__)

reportes_bp = Blueprint('reportes', __name__)


@reportes_bp.route('/resumen', methods=['GET'])
@jwt_required()
def resumen_negocio():
    """
    Retorna KPIs generales del negocio.
    Resultado cacheado por 5 minutos.
    Requiere JWT — solo para usuarios autenticados.

    Este endpoint consulta TODAS las tablas del sistema.
    Candidato principal para migrar a Lambda con DynamoDB como fuente de datos.
    """
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return respuesta_error('Solo administradores pueden ver reportes', 403)

    clave = 'reporte_resumen'
    cached = cache_service.get(clave)
    if cached:
        return respuesta_ok(cached)

    # ---- Métricas de órdenes ----
    total_ordenes = OrdenTrabajo.query.count()
    ordenes_pendientes = OrdenTrabajo.query.filter_by(estado='pendiente').count()
    ordenes_en_proceso = OrdenTrabajo.query.filter(
        OrdenTrabajo.estado.in_(['en_diagnostico', 'en_reparacion'])
    ).count()
    ordenes_completadas = OrdenTrabajo.query.filter_by(estado='completado').count()
    ordenes_canceladas = OrdenTrabajo.query.filter_by(estado='cancelado').count()

    # ---- Ingresos del mes actual ----
    hoy = datetime.utcnow()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ingresos_mes = db.session.query(
        func.coalesce(func.sum(OrdenTrabajo.total), 0)
    ).filter(
        OrdenTrabajo.estado == 'completado',
        OrdenTrabajo.fecha_completado >= inicio_mes
    ).scalar()

    # ---- Métricas de clientes y catálogo ----
    total_clientes = Cliente.query.filter_by(activo=True).count()
    total_servicios = Servicio.query.filter_by(activo=True).count()
    total_tecnicos = Usuario.query.filter_by(rol='tecnico', activo=True).count()

    resumen = {
        'ordenes': {
            'total': total_ordenes,
            'pendientes': ordenes_pendientes,
            'en_proceso': ordenes_en_proceso,
            'completadas': ordenes_completadas,
            'canceladas': ordenes_canceladas,
        },
        'ingresos_mes_actual': float(ingresos_mes),
        'clientes_activos': total_clientes,
        'servicios_activos': total_servicios,
        'tecnicos_activos': total_tecnicos,
        'generado_en': datetime.utcnow().isoformat(),
    }

    cache_service.set(clave, resumen, ttl_segundos=300)
    return respuesta_ok(resumen)


@reportes_bp.route('/ingresos', methods=['GET'])
@jwt_required()
def reporte_ingresos():
    """
    Ingresos agrupados por día/semana/mes en un rango de fechas.
    Query params: desde, hasta, agrupacion (dia|semana|mes)

    Anti-patrón: SQL complejo directamente en el controlador.
    """
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return respuesta_error('Solo administradores pueden ver reportes', 403)

    desde_str = request.args.get('desde', '')
    hasta_str = request.args.get('hasta', '')
    agrupacion = request.args.get('agrupacion', 'dia')

    # Defaults: últimos 30 días
    hasta = datetime.utcnow()
    desde = hasta - timedelta(days=30)

    if desde_str:
        try:
            desde = datetime.fromisoformat(desde_str)
        except ValueError:
            return respuesta_error('Formato de "desde" inválido (use YYYY-MM-DD)', 400)
    if hasta_str:
        try:
            hasta = datetime.fromisoformat(hasta_str)
        except ValueError:
            return respuesta_error('Formato de "hasta" inválido (use YYYY-MM-DD)', 400)

    clave_cache = f'reporte_ingresos_{desde.date()}_{hasta.date()}_{agrupacion}'
    cached = cache_service.get(clave_cache)
    if cached:
        return respuesta_ok(cached)

    # Agrupar por fecha usando SQLite strftime
    if agrupacion == 'mes':
        formato_fecha = '%Y-%m'
    elif agrupacion == 'semana':
        formato_fecha = '%Y-%W'
    else:
        formato_fecha = '%Y-%m-%d'

    resultados = db.session.query(
        func.strftime(formato_fecha, OrdenTrabajo.fecha_completado).label('periodo'),
        func.count(OrdenTrabajo.id).label('cantidad_ordenes'),
        func.sum(OrdenTrabajo.total).label('total_ingresos'),
    ).filter(
        OrdenTrabajo.estado == 'completado',
        OrdenTrabajo.fecha_completado >= desde,
        OrdenTrabajo.fecha_completado <= hasta,
    ).group_by('periodo').order_by('periodo').all()

    datos = [
        {
            'periodo': r.periodo,
            'cantidad_ordenes': r.cantidad_ordenes,
            'total_ingresos': float(r.total_ingresos or 0),
        }
        for r in resultados
    ]

    respuesta = {
        'desde': desde.isoformat(),
        'hasta': hasta.isoformat(),
        'agrupacion': agrupacion,
        'datos': datos,
        'total_general': sum(d['total_ingresos'] for d in datos),
    }

    cache_service.set(clave_cache, respuesta, ttl_segundos=600)
    return respuesta_ok(respuesta)


@reportes_bp.route('/tecnicos', methods=['GET'])
@jwt_required()
def reporte_tecnicos():
    """
    Rendimiento de técnicos: órdenes completadas, ingresos generados, tiempo promedio.
    Consume datos de usuarios y órdenes de trabajo.
    """
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return respuesta_error('Solo administradores pueden ver reportes', 403)

    clave = 'reporte_tecnicos'
    cached = cache_service.get(clave)
    if cached:
        return respuesta_ok(cached)

    tecnicos = Usuario.query.filter_by(rol='tecnico', activo=True).all()
    datos = []

    for tecnico in tecnicos:
        ordenes_completadas = OrdenTrabajo.query.filter_by(
            tecnico_id=tecnico.id, estado='completado'
        ).count()
        ordenes_en_proceso = OrdenTrabajo.query.filter(
            OrdenTrabajo.tecnico_id == tecnico.id,
            OrdenTrabajo.estado.in_(['en_diagnostico', 'en_reparacion'])
        ).count()

        ingresos = db.session.query(
            func.coalesce(func.sum(OrdenTrabajo.total), 0)
        ).filter_by(tecnico_id=tecnico.id, estado='completado').scalar()

        datos.append({
            'tecnico_id': tecnico.id,
            'nombre': f'{tecnico.nombre} {tecnico.apellido}',
            'email': tecnico.email,
            'ordenes_completadas': ordenes_completadas,
            'ordenes_en_proceso': ordenes_en_proceso,
            'ingresos_generados': float(ingresos),
        })

    # Ordenar por ingresos descendente
    datos.sort(key=lambda x: x['ingresos_generados'], reverse=True)

    cache_service.set(clave, datos, ttl_segundos=300)
    return respuesta_ok(datos)


@reportes_bp.route('/servicios-top', methods=['GET'])
@jwt_required()
def servicios_mas_solicitados():
    """
    Los servicios más solicitados, con ingresos generados.
    Query param: limite (default 10), categoria

    Candidato para migración: solo lectura, sin efectos secundarios.
    """
    limite = int(request.args.get('limite', 10))
    categoria_filtro = request.args.get('categoria', '').strip()

    clave = f'servicios_top_{limite}_{categoria_filtro}'
    cached = cache_service.get(clave)
    if cached:
        return respuesta_ok(cached)

    query = db.session.query(
        Servicio.id,
        Servicio.nombre,
        Servicio.categoria,
        func.count(DetalleOrden.id).label('veces_solicitado'),
        func.sum(DetalleOrden.precio_unitario * DetalleOrden.cantidad).label('ingresos'),
    ).join(DetalleOrden, Servicio.id == DetalleOrden.servicio_id)

    if categoria_filtro and categoria_filtro in CATEGORIAS:
        query = query.filter(Servicio.categoria == categoria_filtro)

    resultados = (
        query
        .group_by(Servicio.id)
        .order_by(desc('veces_solicitado'))
        .limit(limite)
        .all()
    )

    datos = [
        {
            'servicio_id': r.id,
            'nombre': r.nombre,
            'categoria': r.categoria,
            'veces_solicitado': r.veces_solicitado,
            'ingresos_generados': float(r.ingresos or 0),
        }
        for r in resultados
    ]

    cache_service.set(clave, datos, ttl_segundos=300)
    return respuesta_ok(datos)


@reportes_bp.route('/estado-cache', methods=['GET'])
@jwt_required()
def estado_cache():
    """
    Diagnóstico del estado del caché en memoria.
    Útil para el Orquestador DevOps para entender el uso de estado compartido.
    Requiere JWT de administrador.
    """
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return respuesta_error('Solo administradores', 403)

    return respuesta_ok(cache_service.estadisticas(), 'Estado del caché')
