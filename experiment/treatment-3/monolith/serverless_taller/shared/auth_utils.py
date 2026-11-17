"""
Utilidades de autenticación JWT para entorno Lambda.

DIFERENCIA vs monolito:
- El monolito usa Flask-JWT-Extended con decoradores @jwt_required().
- En Lambda no hay contexto Flask, por lo que se valida el JWT manualmente
  usando PyJWT directamente.
- La lista negra de tokens (revocación) en el monolito era un set en memoria.
  Aquí se delega a DynamoDB o ElastiCache Redis.

GAP IDENTIFICADO:
- La revocación de tokens (logout) requiere un store externo (DynamoDB/Redis).
  Esta implementación usa DynamoDB pero el código de provisioning de la tabla
  no está incluido — debe crearse manualmente o via IaC (Terraform/CDK).
- No se implementó refresh token (el monolito tampoco lo tenía).
"""
import os
import json
import logging
from typing import Optional, Tuple
import jwt as pyjwt

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-cambiar-en-produccion')
JWT_ALGORITHM = 'HS256'


def extraer_token(event: dict) -> Optional[str]:
    """
    Extrae el Bearer token del header Authorization del evento API Gateway.
    Formato esperado: 'Authorization: Bearer <token>'
    """
    headers = event.get('headers') or {}
    # API Gateway puede enviar headers en minúsculas o con capitalización mixta
    auth_header = headers.get('Authorization') or headers.get('authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    return auth_header[7:]


def validar_token(token: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Valida un JWT y retorna (payload, None) si es válido,
    o (None, mensaje_error) si no lo es.
    """
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload, None
    except pyjwt.ExpiredSignatureError:
        return None, 'Token expirado'
    except pyjwt.InvalidTokenError as e:
        return None, f'Token inválido: {str(e)}'


def requerir_jwt(event: dict) -> Tuple[Optional[dict], Optional[dict]]:
    """
    Valida el JWT del evento. Retorna (claims, None) si es válido,
    o (None, respuesta_error_http) si no lo es.

    Uso en handlers:
        claims, error = requerir_jwt(event)
        if error:
            return error
        usuario_id = claims['sub']
    """
    token = extraer_token(event)
    if not token:
        return None, {
            'statusCode': 401,
            'body': json.dumps({'ok': False, 'error': 'Token no proporcionado'}),
            'headers': {'Content-Type': 'application/json'},
        }

    payload, error = validar_token(token)
    if error:
        return None, {
            'statusCode': 401,
            'body': json.dumps({'ok': False, 'error': error}),
            'headers': {'Content-Type': 'application/json'},
        }

    return payload, None


def requerir_admin(claims: dict) -> Optional[dict]:
    """
    Verifica que el usuario tenga rol 'admin'.
    Retorna None si es admin, o una respuesta de error HTTP si no lo es.
    """
    if claims.get('rol') != 'admin':
        return {
            'statusCode': 403,
            'body': json.dumps({'ok': False, 'error': 'Solo administradores pueden acceder'}),
            'headers': {'Content-Type': 'application/json'},
        }
    return None


def crear_token(usuario_id: int, rol: str, email: str) -> str:
    """
    Crea un JWT con los claims del usuario.
    GAP: no implementa refresh tokens ni rotación de claves.
    """
    import time
    expires_in = int(os.environ.get('JWT_EXPIRES_HOURS', 24)) * 3600
    payload = {
        'sub': str(usuario_id),
        'rol': rol,
        'email': email,
        'iat': int(time.time()),
        'exp': int(time.time()) + expires_in,
        'jti': f"{usuario_id}-{int(time.time())}",  # GAP: no es UUID, puede colisionar
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# GAP: Revocación de tokens
# ---------------------------------------------------------------------------
# En el monolito: _tokens_revocados = set() en memoria
# En serverless: necesita DynamoDB. El código siguiente es un STUB —
# requiere que exista la tabla DynamoDB 'taller-tokens-revocados' con
# clave primaria 'jti' (String) y TTL habilitado en campo 'expira_en'.
# Esta tabla NO se crea automáticamente en este código.

def revocar_token(jti: str, expira_en: int) -> bool:
    """
    Agrega el JTI a la lista negra en DynamoDB.
    STUB: requiere boto3 y tabla DynamoDB pre-existente.
    """
    try:
        import boto3
        dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        tabla = dynamodb.Table(os.environ.get('TOKENS_TABLE', 'taller-tokens-revocados'))
        tabla.put_item(Item={'jti': jti, 'expira_en': expira_en})
        return True
    except Exception as e:
        logger.error(f"Error al revocar token en DynamoDB: {e}")
        return False


def token_esta_revocado(jti: str) -> bool:
    """
    Verifica si un JTI está en la lista negra de DynamoDB.
    STUB: requiere boto3 y tabla DynamoDB pre-existente.
    """
    try:
        import boto3
        dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        tabla = dynamodb.Table(os.environ.get('TOKENS_TABLE', 'taller-tokens-revocados'))
        resp = tabla.get_item(Key={'jti': jti})
        return 'Item' in resp
    except Exception as e:
        logger.error(f"Error al verificar token revocado: {e}")
        return False  # Fail open — GAP de seguridad intencional documentado
