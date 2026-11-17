import json
import os
import boto3
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# Configuración desde variables de entorno
BUCKET_NAME = os.environ['BUCKET_NAME']
MAX_FILE_SIZE_MB = int(os.environ.get('MAX_FILE_SIZE_MB', '16'))
ALLOWED_EXTENSIONS = os.environ.get('ALLOWED_EXTENSIONS', 'pdf,png,jpg,jpeg,docx').split(',')
URL_EXPIRATION_SECONDS = int(os.environ.get('URL_EXPIRATION_SECONDS', '300'))

s3_client = boto3.client('s3')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler principal de Lambda.

    Query params esperados:
      - filename: nombre del archivo (requerido)
      - content_type: MIME type (opcional, inferido de extensión)

    Retorna presigned URL para PUT directo a S3.
    """
    try:
        # Extraer parámetros
        params = event.get('queryStringParameters') or {}
        filename = params.get('filename')
        content_type = params.get('content_type')

        if not filename:
            return error_response(400, "Falta parámetro 'filename'")

        # Validar extensión
        extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else None
        if not extension or extension not in ALLOWED_EXTENSIONS:
            return error_response(
                400,
                f"Extensión no permitida. Permitidas: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Inferir content_type si no se proporciona
        if not content_type:
            content_type = infer_content_type(extension)

        # Generar key única en S3
        file_key = generate_s3_key(filename)

        # Generar presigned URL
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': file_key,
                'ContentType': content_type,
                'ContentLengthRange': [0, MAX_FILE_SIZE_MB * 1024 * 1024]
            },
            ExpiresIn=URL_EXPIRATION_SECONDS
        )

        # Respuesta exitosa
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'upload_url': presigned_url,
                'file_key': file_key,
                'expires_in': URL_EXPIRATION_SECONDS,
                'max_file_size_mb': MAX_FILE_SIZE_MB
            })
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return error_response(500, "Error interno del servidor")


def generate_s3_key(filename: str) -> str:
    """
    Genera una key única en S3 para evitar colisiones.
    Formato: uploads/{uuid}/{filename}
    """
    unique_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().strftime('%Y%m%d')
    return f"uploads/{timestamp}/{unique_id}/{filename}"


def infer_content_type(extension: str) -> str:
    """
    Infiere el Content-Type basado en la extensión.
    """
    content_types = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'txt': 'text/plain',
        'csv': 'text/csv'
    }
    return content_types.get(extension, 'application/octet-stream')


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Retorna una respuesta de error estandarizada.
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': message
        })
    }