"""
Lambda Handler — Reportes

Rutas manejadas:
  GET /reportes/resumen
  GET /reportes/ingresos
  GET /reportes/tecnicos
  GET /reportes/servicios-top
  GET /reportes/estado-cache

DIFERENCIAS vs monolito:
- func.strftime('%Y-%m-%d', ...) es específico de SQLite.
  Con PostgreSQL (RDS) se usa to_char() o date_trunc().
  GAP: el código de reportes usa strftime de SQLite — no funciona en RDS PostgreSQL.
- La constante CATEGORIAS ya no se importa desde el blueprint de servicios.
"""
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.db import DBSession
from shared.models import OrdenTrabajo, DetalleOrden, Cliente, Servicio, Usuario
from shared.auth_utils import requerir_jwt, requerir_admin
from shared.cache import cache_service
from shared.response import ok, error, get_query_param
from sqlalchemy import func, desc

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CATEGORIAS = ['electronico', 'electrodomestico', 'computacion', 'celular', 'otro']


def handler(event, context):
    method = event.get('httpMethod', '')
    path = event.get('path', '')

    logger.info(f"Reportes handler: {method} {path}")

    try:
        if method == 'GET' and path.endswith('/resumen'):
            return _resumen(event)
        elif method == 'GET' and path.endswith('/ingresos'):
            return _ingresos(event)
        elif method == 'GET' and path.endswith('/tecnicos'):
            return _tecnicos(event)
        elif method == 'GET' and path.endswith('/servicios-top'):
            return _servicios_top(event)
        elif method == 'GET' and path.endswith('/estado-cache'):
            return _estado_cache(event)
        elif method == 'OPTIONS':
            return ok(None)
        else:
            return error('Ruta no encontrada', 404)
    except Exception as e:
        logger.exception(f"Error en reportes handler: {e}")
        return error('Error interno del servidor', 500)


def _resumen(event):
    claims, err = requerir_jwt(event)
    if err:
        return err
    err_admin = requerir_admin(claims)
    if err_admin:
        return err_admin

    clave = 'reporte_resumen'
    cached = cache_service.get(clave)
    if cached:
        return ok(cached)

    with DBSession() as session:
        total_ordenes = session.query(OrdenTrabajo).count()
        ordenes_pendientes = session.query(OrdenTrabajo).filter_by(estado='pendiente').count()
        ordenes_en_proceso = session.query(OrdenTrabajo).filter(
            OrdenTrabajo.estado.in_(['en_diagnostico', 'en_reparacion'])
        ).count()
        ordenes_completadas = session.query(OrdenTrabajo).filter_by(estado='completado').count()
        ordenes_canceladas = session.query(OrdenTrabajo).filter_by(estado='cancelado').count()

        hoy = datetime.utcnow()
        inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ingresos_mes = session.query(
            func.coalesce(func.sum(OrdenTrabajo.total), 0)
        ).filter(
            OrdenTrabajo.estado == 'completado',
            OrdenTrabajo.fecha_completado >= inicio_mes
        ).scalar()

        total_clientes = session.query(Cliente).filter_by(activo=True).count()
        total_servicios = session.query(Servicio).filter_by(activo=True).count()
        total_tecnicos = session.query(Usuario).filter_by(rol='tecnico', activo=True).count()

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
    return ok(resumen)


def _ingresos(event):
    claims, err = requerir_jwt(event)
    if err:
        return err
    err_admin = requerir_admin(claims)
    if err_admin:
        return err_admin

    desde_str = get_query_param(event, 'desde', '')
    hasta_str = get_query_param(event, 'hasta', '')
    agrupacion = get_query_param(event, 'agrupacion', 'dia')

    hasta = datetime.utcnow()
    desde = hasta - timedelta(days=30)

    if desde_str:
        try:
            desde = datetime.fromisoformat(desde_str)
        except ValueError:
            return error('Formato de "desde" inválido (use YYYY-MM-DD)', 400)
    if hasta_str:
        try:
            hasta = datetime.fromisoformat(hasta_str)
        except ValueError:
            return error('Formato de "hasta" inválido (use YYYY-MM-DD)', 400)

    clave_cache = f'reporte_ingresos_{desde.date()}_{hasta.date()}_{agrupacion}'
    cached = cache_service.get(clave_cache)
    if cached:
        return ok(cached)

    # GAP CRÍTICO: func.strftime es SQLite-específico.
    # Para PostgreSQL (RDS) se necesita:
    #   agrupacion='dia'  → func.to_char(OrdenTrabajo.fecha_completado, 'YYYY-MM-DD')
    #   agrupacion='mes'  → func.to_char(OrdenTrabajo.fecha_completado, 'YYYY-MM')
    #   agrupacion='semana' → func.to_char(OrdenTrabajo.fecha_completado, 'IYYY-IW')
    # Este código SOLO funciona con SQLite. Con RDS PostgreSQL fallará.
    if agrupacion == 'mes':
        formato_fecha = '%Y-%m'
    elif agrupacion == 'semana':
        formato_fecha = '%Y-%W'
    else:
        formato_fecha = '%Y-%m-%d'

    with DBSession() as session:
        resultados = session.query(
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
    return ok(respuesta)


def _tecnicos(event):
    claims, err = requerir_jwt(event)
    if err:
        return err
    err_admin = requerir_admin(claims)
    if err_admin:
        return err_admin

    clave = 'reporte_tecnicos'
    cached = cache_service.get(clave)
    if cached:
        return ok(cached)

    with DBSession() as session:
        tecnicos = session.query(Usuario).filter_by(rol='tecnico', activo=True).all()
        datos = []
        for tecnico in tecnicos:
            ordenes_completadas = session.query(OrdenTrabajo).filter_by(
                tecnico_id=tecnico.id, estado='completado'
            ).count()
            ordenes_en_proceso = session.query(OrdenTrabajo).filter(
                OrdenTrabajo.tecnico_id == tecnico.id,
                OrdenTrabajo.estado.in_(['en_diagnostico', 'en_reparacion'])
            ).count()
            ingresos = session.query(
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

    datos.sort(key=lambda x: x['ingresos_generados'], reverse=True)
    cache_service.set(clave, datos, ttl_segundos=300)
    return ok(datos)


def _servicios_top(event):
    claims, err = requerir_jwt(event)
    if err:
        return err
    err_admin = requerir_admin(claims)
    if err_admin:
        return err_admin

    limite = int(get_query_param(event, 'limite', '10'))
    categoria_filtro = get_query_param(event, 'categoria', '').strip()

    clave = f'servicios_top_{limite}_{categoria_filtro}'
    cached = cache_service.get(clave)
    if cached:
        return ok(cached)

    with DBSession() as session:
        query = session.query(
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
    return ok(datos)


def _estado_cache(event):
    claims, err = requerir_jwt(event)
    if err:
        return err
    err_admin = requerir_admin(claims)
    if err_admin:
        return err_admin

    return ok(cache_service.estadisticas(), 'Estado del caché Redis')
