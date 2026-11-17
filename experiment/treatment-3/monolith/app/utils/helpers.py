"""
Funciones utilitarias compartidas por múltiples blueprints.
"""
import os
import logging
from datetime import datetime
from flask import jsonify, current_app
from sqlalchemy.orm import Query

logger = logging.getLogger(__name__)


def paginar_query(query: Query, pagina: int = 1, por_pagina: int = 20) -> dict:
    """
    Pagina un query de SQLAlchemy y retorna un dict con metadatos.
    Usado directamente en los controladores — el resultado ya está deserializado.
    """
    pagina = max(1, pagina)
    por_pagina = min(max(1, por_pagina), 100)  # Entre 1 y 100

    paginado = query.paginate(page=pagina, per_page=por_pagina, error_out=False)
    return {
        'items': paginado.items,
        'total': paginado.total,
        'pagina': pagina,
        'por_pagina': por_pagina,
        'paginas': paginado.pages,
        'tiene_siguiente': paginado.has_next,
        'tiene_anterior': paginado.has_prev,
    }


def extension_permitida(nombre_archivo: str) -> bool:
    """Verifica si la extensión del archivo es válida para upload."""
    extensiones = current_app.config.get('ALLOWED_EXTENSIONS', set())
    if '.' not in nombre_archivo:
        return False
    ext = nombre_archivo.rsplit('.', 1)[1].lower()
    return ext in extensiones


def generar_numero_orden() -> str:
    """
    Genera un número de orden único basado en timestamp.
    Formato: OT-YYYYMMDD-HHMMSS
    Anti-patrón: no usa secuencia de BD, puede colisionar bajo alta concurrencia.
    """
    ahora = datetime.utcnow()
    return f"OT-{ahora.strftime('%Y%m%d-%H%M%S')}"


def respuesta_ok(datos: any, mensaje: str = 'OK', codigo: int = 200):
    """Envuelve una respuesta exitosa en el formato estándar de la API."""
    return jsonify({
        'ok': True,
        'mensaje': mensaje,
        'datos': datos,
    }), codigo


def respuesta_error(mensaje: str, codigo: int = 400, detalle: any = None):
    """Envuelve una respuesta de error en el formato estándar de la API."""
    cuerpo = {'ok': False, 'error': mensaje}
    if detalle:
        cuerpo['detalle'] = detalle
    return jsonify(cuerpo), codigo
