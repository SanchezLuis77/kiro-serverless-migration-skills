"""
Helpers de respuesta HTTP para handlers Lambda.

DIFERENCIA vs monolito:
- El monolito usa flask.jsonify() que retorna un objeto Response de Flask.
- En Lambda, el handler debe retornar un dict con statusCode, headers y body (string).
- Los CORS headers deben incluirse explícitamente (en Flask los maneja flask-cors).

GAP IDENTIFICADO:
- CORS no está configurado a nivel de código Lambda; debe configurarse en API Gateway.
  Esta implementación agrega headers básicos pero la configuración de orígenes
  permitidos debe hacerse en serverless.yml o en la consola de AWS.
"""
import json
from decimal import Decimal
from datetime import datetime


class DecimalEncoder(json.JSONEncoder):
    """
    Encoder personalizado para manejar tipos Decimal y datetime
    que SQLAlchemy retorna y json.dumps no sabe serializar.
    GAP: el monolito usaba jsonify de Flask que maneja esto automáticamente.
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',  # GAP: debe restringirse en producción
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,DELETE,OPTIONS',
}


def ok(datos=None, mensaje='OK', codigo=200) -> dict:
    """Respuesta exitosa en formato Lambda."""
    return {
        'statusCode': codigo,
        'headers': CORS_HEADERS,
        'body': json.dumps({
            'ok': True,
            'mensaje': mensaje,
            'datos': datos,
        }, cls=DecimalEncoder),
    }


def error(mensaje: str, codigo: int = 400, detalle=None) -> dict:
    """Respuesta de error en formato Lambda."""
    cuerpo = {'ok': False, 'error': mensaje}
    if detalle:
        cuerpo['detalle'] = detalle
    return {
        'statusCode': codigo,
        'headers': CORS_HEADERS,
        'body': json.dumps(cuerpo, cls=DecimalEncoder),
    }


def get_body(event: dict) -> dict:
    """
    Extrae y parsea el body del evento API Gateway.
    API Gateway puede enviar el body como string o ya parseado.
    """
    body = event.get('body') or '{}'
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
    return body or {}


def get_path_param(event: dict, nombre: str) -> str:
    """Extrae un path parameter del evento API Gateway."""
    params = event.get('pathParameters') or {}
    return params.get(nombre, '')


def get_query_param(event: dict, nombre: str, default='') -> str:
    """Extrae un query string parameter del evento API Gateway."""
    params = event.get('queryStringParameters') or {}
    return params.get(nombre, default)


def paginar_query(query, pagina: int = 1, por_pagina: int = 20) -> dict:
    """
    Paginación para SQLAlchemy sin Flask.
    GAP: SQLAlchemy puro no tiene .paginate() — eso es de Flask-SQLAlchemy.
    Se reimplementa con offset/limit.
    """
    pagina = max(1, pagina)
    por_pagina = min(max(1, por_pagina), 100)
    offset = (pagina - 1) * por_pagina

    total = query.count()
    items = query.offset(offset).limit(por_pagina).all()
    paginas = (total + por_pagina - 1) // por_pagina

    return {
        'items': items,
        'total': total,
        'pagina': pagina,
        'por_pagina': por_pagina,
        'paginas': paginas,
        'tiene_siguiente': pagina < paginas,
        'tiene_anterior': pagina > 1,
    }
