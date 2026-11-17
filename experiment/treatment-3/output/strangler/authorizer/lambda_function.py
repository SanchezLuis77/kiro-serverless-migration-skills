"""
Lambda Authorizer para API Gateway — Validación JWT + Blacklist

Valida tokens JWT Bearer y verifica si están en la blacklist de DynamoDB.
Retorna una IAM policy que permite o niega el acceso al API.
"""
import os
import json
import logging
import jwt
import boto3
from typing import Dict, Any

# Configuración
JWT_SECRET = os.environ['JWT_SECRET_KEY']
BLACKLIST_TABLE = os.environ['BLACKLIST_TABLE_NAME']
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# Logger
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')
blacklist_table = dynamodb.Table(BLACKLIST_TABLE)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler principal del Authorizer.

    Input:
        {
          "type": "TOKEN",
          "authorizationToken": "Bearer <token>",
          "methodArn": "arn:aws:execute-api:..."
        }

    Output:
        {
          "principalId": "user-123",
          "policyDocument": { ... },
          "context": { "userId": "123", "userRole": "tecnico", ... }
        }
    """
    try:
        # Extraer token
        token = extract_token(event.get('authorizationToken', ''))
        if not token:
            logger.warning('Missing or invalid Authorization header')
            return generate_policy('unknown', 'Deny', event['methodArn'])

        # Decodificar y validar JWT
        payload = decode_jwt(token)
        if not payload:
            logger.warning('Invalid JWT token')
            return generate_policy('unknown', 'Deny', event['methodArn'])

        # Verificar blacklist
        jti = payload.get('jti')
        if is_token_revoked(jti):
            logger.info(f'Token {jti} is in blacklist')
            return generate_policy('unknown', 'Deny', event['methodArn'])

        # Token válido → Allow
        user_id = str(payload.get('sub', 'unknown'))
        logger.info(f'Token válido para user_id={user_id}')

        return generate_policy(
            principal_id=user_id,
            effect='Allow',
            resource=event['methodArn'],
            context={
                'userId': user_id,
                'userEmail': payload.get('email', ''),
                'userRole': payload.get('rol', 'tecnico'),
            }
        )

    except Exception as e:
        logger.error(f'Authorizer error: {e}', exc_info=True)
        return generate_policy('unknown', 'Deny', event['methodArn'])


def extract_token(auth_header: str) -> str:
    """
    Extrae el token de 'Authorization: Bearer <token>'.
    """
    if not auth_header or not auth_header.startswith('Bearer '):
        return ''
    return auth_header[7:].strip()


def decode_jwt(token: str) -> Dict[str, Any]:
    """
    Decodifica y valida el JWT token.
    Retorna el payload si es válido, None si no lo es.
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=['HS256'],
            options={'verify_exp': True}
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning('JWT token expired')
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f'Invalid JWT: {e}')
        return None


def is_token_revoked(jti: str) -> bool:
    """
    Verifica si el token está en la blacklist de DynamoDB.
    """
    if not jti:
        return False

    try:
        response = blacklist_table.get_item(Key={'token_jti': jti})
        return 'Item' in response
    except Exception as e:
        logger.error(f'Error checking blacklist: {e}')
        # Fail-open: si DynamoDB falla, permitir el token
        return False


def generate_policy(principal_id: str, effect: str, resource: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Genera una IAM policy para API Gateway.
    """
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource if effect == 'Allow' else '*'
            }]
        }
    }

    if context and effect == 'Allow':
        policy['context'] = context

    return policy
