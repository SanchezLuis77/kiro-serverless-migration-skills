"""
generate_uploads.py — Skill 04: Migrador de Uploads

Genera la infraestructura serverless para migrar uploads de archivos desde filesystem
local a Amazon S3 con presigned URLs:
  - S3 bucket con configuración de seguridad
  - Lambda para generación de presigned URLs
  - Código de la Lambda (Python 3.11)
  - Guías de migración del cliente (breaking changes)
  - Guía de despliegue completa

Consume el migration-manifest.json del Skill 01 y detecta endpoints con
anti-patrón AP-local-filesystem (archivo.save() en Flask).

Principios de diseño:
  - Sin dependencias externas: usa exclusivamente módulos de la biblioteca estándar
    de Python 3.9+ (json, os, sys, pathlib, argparse, typing, uuid, textwrap)
  - Templates CloudFormation como cadenas de texto (no require PyYAML)
  - Salida determinista: mismo input → mismo output

Uso:
    python generate_uploads.py --manifest <ruta_manifest>
    python generate_uploads.py --manifest <ruta> --output <dir> --bucket-name <nombre>

Códigos de salida:
    0 — Generación exitosa; infraestructura lista para desplegar
    1 — El archivo manifest no existe
    2 — No se detectaron endpoints con uploads
    3 — Error de escritura del output

Proyecto: Trabajo de Grado — Maestría en Ingeniería de Software
          Pontificia Universidad Javeriana Cali
Autor:    Luis Gerardo Sánchez Ordóñez
Director: Juan Gabriel Quintero Barbosa — Head Solutions Architecture, AWS Colombia
"""

import json
import os
import sys
import argparse
import textwrap
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

# ---------------------------------------------------------------------------
# Constantes globales
# ---------------------------------------------------------------------------

SKILL_VERSION = "1.0.0"
DEFAULT_OUTPUT_DIR = "serverless-output/uploads"
DEFAULT_BUCKET_PREFIX = "taller-uploads"
DEFAULT_MAX_FILE_SIZE_MB = 16
DEFAULT_ALLOWED_EXTENSIONS = "pdf,png,jpg,jpeg,docx,xlsx"
PRESIGNED_URL_EXPIRATION = 300  # 5 minutos

# ---------------------------------------------------------------------------
# === ManifestLoader ===
# Responsabilidad: cargar y validar el migration-manifest.json
# ---------------------------------------------------------------------------

class ManifestLoader:
    """
    Carga y valida el migration-manifest.json generado por Skill 01.
    """

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path
        self.warnings: List[str] = []

    def load(self) -> Dict[str, Any]:
        """
        Carga el manifest desde disco y valida que contenga las claves requeridas.
        Retorna el dict del manifest o lanza FileNotFoundError.
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(
                f"❌ Manifest no encontrado: {self.manifest_path}\n"
                f"   Ejecuta primero: python skills/skill-01-analyzer/scripts/analyze_monolith.py"
            )

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Validar estructura básica
        if "modules" not in manifest:
            raise ValueError(f"❌ Manifest inválido: falta clave 'modules'")

        return manifest

    def extract_upload_endpoints(self, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extrae endpoints que manejan uploads de archivos.
        Detecta anti-patrón AP-local-filesystem o métodos POST con archivos.
        """
        upload_endpoints = []

        for module in manifest.get("modules", []):
            for endpoint in module.get("endpoints", []):
                # Detectar AP-local-filesystem en anti_patterns
                has_filesystem_antipattern = any(
                    ap.get("code") == "AP-local-filesystem"
                    for ap in endpoint.get("anti_patterns", [])
                )

                # También detectar por path + método (heurística)
                path = endpoint.get("path", "")
                method = endpoint.get("method", "")
                has_upload_hint = (
                    method == "POST" and
                    any(keyword in path.lower() for keyword in ["adjunto", "upload", "archivo", "file", "attach"])
                )

                if has_filesystem_antipattern or has_upload_hint:
                    upload_endpoints.append({
                        "endpoint_id": endpoint.get("id"),
                        "method": method,
                        "path": path,
                        "module": module.get("name"),
                        "has_antipattern": has_filesystem_antipattern
                    })

        return upload_endpoints


# ---------------------------------------------------------------------------
# === S3TemplateGenerator ===
# Responsabilidad: generar template-s3.yaml
# ---------------------------------------------------------------------------

class S3TemplateGenerator:
    """
    Genera CloudFormation template para S3 bucket con:
      - Versionamiento activado
      - Cifrado AES-256
      - CORS para upload directo
      - Public access bloqueado
      - Lifecycle policy
    """

    def __init__(self, bucket_name: str, allowed_origins: List[str]) -> None:
        self.bucket_name = bucket_name
        self.allowed_origins = allowed_origins

    def generate(self) -> str:
        """
        Retorna el template CloudFormation como string YAML.
        """
        origins_yaml = "\n          ".join(f"- '{origin}'" for origin in self.allowed_origins)

        template = f"""
AWSTemplateFormatVersion: '2010-09-09'
Description: >
  S3 bucket para uploads del monolito migrado a serverless.
  Generado por Skill 04 — Upload Migrator.

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]
    Description: Ambiente de despliegue

Resources:
  # ====================================================================
  # S3 Bucket — Almacenamiento de archivos subidos por usuarios
  # ====================================================================
  UploadBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '{self.bucket_name}-${{Environment}}'
      VersioningConfiguration:
        Status: Enabled
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      CorsConfiguration:
        CorsRules:
          - AllowedOrigins:
{origins_yaml}
            AllowedMethods:
              - PUT
              - POST
            AllowedHeaders:
              - '*'
            MaxAge: 3600
      LifecycleConfiguration:
        Rules:
          - Id: DeleteOldVersionsAfter90Days
            Status: Enabled
            NoncurrentVersionExpirationInDays: 90
          - Id: AbortIncompleteMultipartUpload
            Status: Enabled
            AbortIncompleteMultipartUpload:
              DaysAfterInitiation: 7

  # ====================================================================
  # Bucket Policy — Denegar acceso público explícitamente
  # ====================================================================
  UploadBucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref UploadBucket
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Sid: DenyInsecureTransport
            Effect: Deny
            Principal: '*'
            Action: 's3:*'
            Resource:
              - !Sub '${{UploadBucket.Arn}}/*'
              - !GetAtt UploadBucket.Arn
            Condition:
              Bool:
                'aws:SecureTransport': false

Outputs:
  BucketName:
    Description: Nombre del S3 bucket
    Value: !Ref UploadBucket
    Export:
      Name: !Sub '${{AWS::StackName}}-BucketName'

  BucketArn:
    Description: ARN del S3 bucket
    Value: !GetAtt UploadBucket.Arn
    Export:
      Name: !Sub '${{AWS::StackName}}-BucketArn'

  BucketDomainName:
    Description: Domain name del bucket
    Value: !GetAtt UploadBucket.RegionalDomainName
    Export:
      Name: !Sub '${{AWS::StackName}}-BucketDomainName'
"""
        return textwrap.dedent(template).strip()


# ---------------------------------------------------------------------------
# === LambdaTemplateGenerator ===
# Responsabilidad: generar template-presigned-lambda.yaml
# ---------------------------------------------------------------------------

class LambdaTemplateGenerator:
    """
    Genera CloudFormation template para Lambda de presigned URLs.
    """

    def __init__(
        self,
        bucket_stack_name: str,
        max_file_size_mb: int,
        allowed_extensions: str,
        expiration_seconds: int
    ) -> None:
        self.bucket_stack_name = bucket_stack_name
        self.max_file_size_mb = max_file_size_mb
        self.allowed_extensions = allowed_extensions
        self.expiration_seconds = expiration_seconds

    def generate(self) -> str:
        """
        Retorna el template CloudFormation como string YAML.
        """
        template = f"""
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: >
  Lambda para generación de presigned URLs (S3 uploads).
  Generado por Skill 04 — Upload Migrator.

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]
    Description: Ambiente de despliegue

  BucketStackName:
    Type: String
    Default: {self.bucket_stack_name}
    Description: Nombre del stack de S3 (para importar bucket name)

Globals:
  Function:
    Timeout: 10
    MemorySize: 256
    Runtime: python3.11
    Architectures:
      - x86_64
    Environment:
      Variables:
        BUCKET_NAME: !ImportValue
          Fn::Sub: '${{BucketStackName}}-BucketName'
        MAX_FILE_SIZE_MB: '{self.max_file_size_mb}'
        ALLOWED_EXTENSIONS: '{self.allowed_extensions}'
        URL_EXPIRATION_SECONDS: '{self.expiration_seconds}'

Resources:
  # ====================================================================
  # Lambda — Generación de presigned URLs
  # ====================================================================
  PresignedUrlFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub 'upload-presigned-url-${{Environment}}'
      CodeUri: presigned-function/
      Handler: lambda_function.lambda_handler
      Description: Genera presigned URLs para upload directo a S3
      Policies:
        - Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - s3:PutObject
                - s3:GetObject
              Resource:
                Fn::Sub:
                  - '${{BucketArn}}/*'
                  - BucketArn: !ImportValue
                      Fn::Sub: '${{BucketStackName}}-BucketArn'
      Events:
        GetUploadUrl:
          Type: Api
          Properties:
            Path: /upload-url
            Method: GET
            RestApiId: !Ref PresignedApi

  # ====================================================================
  # API Gateway — Endpoint público para solicitar presigned URLs
  # ====================================================================
  PresignedApi:
    Type: AWS::Serverless::Api
    Properties:
      Name: !Sub 'upload-presigned-api-${{Environment}}'
      StageName: !Ref Environment
      Cors:
        AllowOrigin: "'*'"
        AllowHeaders: "'Content-Type,Authorization'"
        AllowMethods: "'GET,OPTIONS'"

Outputs:
  PresignedUrlFunctionArn:
    Description: ARN de la Lambda de presigned URLs
    Value: !GetAtt PresignedUrlFunction.Arn
    Export:
      Name: !Sub '${{AWS::StackName}}-FunctionArn'

  ApiEndpoint:
    Description: URL del API Gateway
    Value: !Sub 'https://${{PresignedApi}}.execute-api.${{AWS::Region}}.amazonaws.com/${{Environment}}/upload-url'
    Export:
      Name: !Sub '${{AWS::StackName}}-ApiEndpoint'
"""
        return textwrap.dedent(template).strip()


# ---------------------------------------------------------------------------
# === LambdaCodeGenerator ===
# Responsabilidad: generar el código Python de la Lambda
# ---------------------------------------------------------------------------

class LambdaCodeGenerator:
    """
    Genera lambda_function.py para presigned URLs.
    """

    def generate_handler(self) -> str:
        """
        Retorna el código Python del handler de Lambda.
        """
        code = """
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
    \"\"\"
    Handler principal de Lambda.
    
    Query params esperados:
      - filename: nombre del archivo (requerido)
      - content_type: MIME type (opcional, inferido de extensión)
    
    Retorna presigned URL para PUT directo a S3.
    \"\"\"
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
    \"\"\"
    Genera una key única en S3 para evitar colisiones.
    Formato: uploads/{uuid}/{filename}
    \"\"\"
    unique_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().strftime('%Y%m%d')
    return f"uploads/{timestamp}/{unique_id}/{filename}"


def infer_content_type(extension: str) -> str:
    \"\"\"
    Infiere el Content-Type basado en la extensión.
    \"\"\"
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
    \"\"\"
    Retorna una respuesta de error estandarizada.
    \"\"\"
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
"""
        return textwrap.dedent(code).strip()

    def generate_requirements(self) -> str:
        """
        Retorna el contenido de requirements.txt.
        """
        return "boto3>=1.26.0\n"


# ---------------------------------------------------------------------------
# === MigrationGuideGenerator ===
# Responsabilidad: generar MIGRATION_GUIDE.md
# ---------------------------------------------------------------------------

class MigrationGuideGenerator:
    """
    Genera guía de migración para el cliente (breaking changes).
    """

    def __init__(self, upload_endpoints: List[Dict[str, Any]]) -> None:
        self.upload_endpoints = upload_endpoints

    def generate(self) -> str:
        """
        Retorna el contenido del MIGRATION_GUIDE.md.
        """
        endpoints_list = "\n".join(
            f"- `[{ep['method']}] {ep['path']}` (módulo: {ep['module']})"
            for ep in self.upload_endpoints
        )

        guide = f"""
# Guía de Migración — Uploads a S3

**⚠️ BREAKING CHANGE:** El flujo de upload de archivos cambia de 1 paso (multipart/form-data) a 2 pasos (presigned URL + PUT directo a S3).

---

## Endpoints afectados

Los siguientes endpoints del monolito requieren cambios en el cliente:

{endpoints_list}

---

## Flujo ANTES (monolito)

```javascript
// Un solo request con FormData
const formData = new FormData();
formData.append('archivo', file);

const response = await fetch('/api/transacciones/123/adjunto', {{
  method: 'POST',
  body: formData,
  headers: {{
    'Authorization': `Bearer ${{token}}`
  }}
}});

const result = await response.json();
console.log('Archivo subido:', result.url);
```

**Características:**
- ✅ Un solo request
- ❌ Consume bandwidth del backend
- ❌ Timeout en archivos grandes
- ❌ No hay progress tracking nativo

---

## Flujo DESPUÉS (serverless)

```javascript
// Paso 1: Solicitar presigned URL
const response1 = await fetch(
  `/api/transacciones/123/adjunto/upload-url?filename=${{encodeURIComponent(file.name)}}`,
  {{
    headers: {{ 'Authorization': `Bearer ${{token}}` }}
  }}
);

const {{ upload_url, file_key, expires_in }} = await response1.json();

// Paso 2: Upload directo a S3 (sin token, URL firmada)
const response2 = await fetch(upload_url, {{
  method: 'PUT',
  body: file,
  headers: {{
    'Content-Type': file.type
  }}
}});

if (!response2.ok) {{
  throw new Error('Error al subir archivo a S3');
}}

// Paso 3: Notificar al backend que el upload completó
const response3 = await fetch('/api/transacciones/123/adjunto', {{
  method: 'POST',
  body: JSON.stringify({{
    file_key: file_key,
    filename: file.name,
    size: file.size,
    content_type: file.type
  }}),
  headers: {{
    'Authorization': `Bearer ${{token}}`,
    'Content-Type': 'application/json'
  }}
}});

const result = await response3.json();
console.log('Archivo registrado en BD:', result);
```

**Características:**
- ⚠️ Tres requests (más complejo)
- ✅ NO consume bandwidth del backend
- ✅ Sin timeouts (S3 maneja archivos grandes)
- ✅ Progress tracking con `xhr.upload.onprogress`
- ✅ Más rápido (sin proxy)
- ✅ Más escalable (S3 maneja millones de uploads concurrentes)

---

## Implementación con Progress Tracking

```javascript
function uploadFileWithProgress(file, presignedUrl, onProgress) {{
  return new Promise((resolve, reject) => {{
    const xhr = new XMLHttpRequest();
    
    // Configurar evento de progreso
    xhr.upload.addEventListener('progress', (e) => {{
      if (e.lengthComputable) {{
        const percentComplete = (e.loaded / e.total) * 100;
        onProgress(percentComplete);
      }}
    }});
    
    // Configurar evento de completado
    xhr.addEventListener('load', () => {{
      if (xhr.status === 200) {{
        resolve();
      }} else {{
        reject(new Error(`Upload falló: ${{xhr.status}}`));
      }}
    }});
    
    // Configurar evento de error
    xhr.addEventListener('error', () => {{
      reject(new Error('Error de red al subir archivo'));
    }});
    
    // Enviar request
    xhr.open('PUT', presignedUrl);
    xhr.setRequestHeader('Content-Type', file.type);
    xhr.send(file);
  }});
}}

// Uso:
await uploadFileWithProgress(file, upload_url, (progress) => {{
  console.log(`Progreso: ${{progress.toFixed(1)}}%`);
  updateProgressBar(progress);
}});
```

---

## Manejo de Errores

### Error 403: URL expirada

```javascript
try {{
  await fetch(upload_url, {{ method: 'PUT', body: file }});
}} catch (error) {{
  if (error.status === 403) {{
    // La URL expiró (5 minutos), solicitar una nueva
    console.error('URL expirada, reintentando...');
    // Volver al Paso 1
  }}
}}
```

### Error de tamaño de archivo

```javascript
const MAX_FILE_SIZE_MB = 16;

if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {{
  alert(`Archivo muy grande. Máximo: ${{MAX_FILE_SIZE_MB}} MB`);
  return;
}}
```

### Error de extensión no permitida

```javascript
const ALLOWED_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'docx'];
const extension = file.name.split('.').pop().toLowerCase();

if (!ALLOWED_EXTENSIONS.includes(extension)) {{
  alert(`Extensión no permitida. Permitidas: ${{ALLOWED_EXTENSIONS.join(', ')}}`);
  return;
}}
```

---

## Migración Incremental

Si no puedes cambiar el cliente inmediatamente:

1. **Opción A: Mantener ambos flujos**
   - Nuevo endpoint: `GET /adjunto/upload-url` (presigned)
   - Endpoint legacy: `POST /adjunto` (proxy a S3)
   - Migrar clientes gradualmente

2. **Opción B: Wrapper en el backend**
   - El backend recibe multipart/form-data
   - Internamente sube a S3 (sin filesystem)
   - ⚠️ Consume bandwidth y no aprovecha beneficios de S3

---

## Checklist de Migración

- [ ] Actualizar código del cliente para flujo de 3 pasos
- [ ] Implementar progress tracking (opcional)
- [ ] Añadir validación de extensión en el frontend
- [ ] Añadir validación de tamaño en el frontend
- [ ] Probar uploads con archivos pequeños (<1 MB)
- [ ] Probar uploads con archivos grandes (>5 MB)
- [ ] Probar manejo de errores (URL expirada, red caída)
- [ ] Actualizar documentación del API
- [ ] Notificar a equipos dependientes del cambio
- [ ] Configurar monitoreo de errores en S3 uploads

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Fecha:** {datetime.now().strftime("%Y-%m-%d")}
"""
        return textwrap.dedent(guide).strip()


# ---------------------------------------------------------------------------
# === DeploymentGuideGenerator ===
# Responsabilidad: generar DEPLOYMENT_GUIDE.md
# ---------------------------------------------------------------------------

class DeploymentGuideGenerator:
    """
    Genera guía de despliegue completa.
    """

    def __init__(self, bucket_name: str) -> None:
        self.bucket_name = bucket_name

    def generate(self) -> str:
        """
        Retorna el contenido del DEPLOYMENT_GUIDE.md.
        """
        guide = f"""
# Guía de Despliegue — Infraestructura de Uploads

Esta guía detalla cómo desplegar la infraestructura de S3 + Lambda para uploads serverless.

---

## Prerrequisitos

- AWS CLI configurado con credenciales válidas
- SAM CLI instalado: `pip install aws-sam-cli`
- Permisos IAM:
  - `s3:CreateBucket`, `s3:PutBucketPolicy`, `s3:PutBucketCors`
  - `lambda:CreateFunction`, `lambda:UpdateFunctionCode`
  - `apigateway:CreateRestApi`
  - `cloudformation:CreateStack`, `cloudformation:UpdateStack`

---

## Paso 1 — Desplegar S3 Bucket

```bash
aws cloudformation deploy \\
  --template-file template-s3.yaml \\
  --stack-name upload-s3-stack \\
  --parameter-overrides Environment=dev \\
  --capabilities CAPABILITY_IAM
```

**Outputs esperados:**
- `BucketName`: `{self.bucket_name}-dev`
- `BucketArn`: `arn:aws:s3:::{self.bucket_name}-dev`

**Verificación:**
```bash
# Verificar que el bucket existe
aws s3 ls | grep {self.bucket_name}

# Verificar CORS configurado
aws s3api get-bucket-cors --bucket {self.bucket_name}-dev
```

---

## Paso 2 — Desplegar Lambda de Presigned URLs

```bash
# Construir y desplegar con SAM
sam build --template-file template-presigned-lambda.yaml
sam deploy \\
  --stack-name upload-lambda-stack \\
  --parameter-overrides \\
      Environment=dev \\
      BucketStackName=upload-s3-stack \\
  --capabilities CAPABILITY_IAM \\
  --resolve-s3
```

**Outputs esperados:**
- `PresignedUrlFunctionArn`: ARN de la Lambda
- `ApiEndpoint`: URL del API Gateway

**Verificación:**
```bash
# Obtener URL del endpoint
API_URL=$(aws cloudformation describe-stacks \\
  --stack-name upload-lambda-stack \\
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \\
  --output text)

echo "API Endpoint: $API_URL"

# Test: solicitar presigned URL
curl "$API_URL?filename=test.pdf"
```

---

## Paso 3 — Probar Upload End-to-End

```bash
# 1. Solicitar presigned URL
RESPONSE=$(curl -s "$API_URL?filename=test.pdf")
UPLOAD_URL=$(echo $RESPONSE | jq -r '.upload_url')
FILE_KEY=$(echo $RESPONSE | jq -r '.file_key')

echo "Upload URL: $UPLOAD_URL"
echo "File Key: $FILE_KEY"

# 2. Subir archivo usando la URL
curl -X PUT "$UPLOAD_URL" \\
  --upload-file test.pdf \\
  -H "Content-Type: application/pdf"

# 3. Verificar que el archivo está en S3
aws s3 ls s3://{self.bucket_name}-dev/$FILE_KEY
```

---

## Paso 4 — Configurar CORS para tu Frontend

Edita `template-s3.yaml` y reemplaza el AllowedOrigin:

```yaml
CorsConfiguration:
  CorsRules:
    - AllowedOrigins:
        - 'https://tu-app.com'  # ⬅️ Reemplazar con tu dominio
        - 'http://localhost:3000'  # Para desarrollo local
```

Redespliega:
```bash
aws cloudformation deploy \\
  --template-file template-s3.yaml \\
  --stack-name upload-s3-stack \\
  --parameter-overrides Environment=dev \\
  --capabilities CAPABILITY_IAM
```

---

## Monitoreo y Logs

### CloudWatch Logs de Lambda

```bash
# Ver logs recientes
sam logs --stack-name upload-lambda-stack --tail

# Filtrar errores
sam logs --stack-name upload-lambda-stack --filter "ERROR"
```

### Métricas de S3

```bash
# Número de requests PUT
aws cloudwatch get-metric-statistics \\
  --namespace AWS/S3 \\
  --metric-name NumberOfObjects \\
  --dimensions Name=BucketName,Value={self.bucket_name}-dev \\
  --start-time 2024-01-01T00:00:00Z \\
  --end-time 2024-01-02T00:00:00Z \\
  --period 3600 \\
  --statistics Sum
```

---

## Costos Estimados

| Recurso | Costo Mensual (estimado) |
|---------|--------------------------|
| S3 (1000 objetos, 10 GB) | $0.23 |
| Lambda (1M requests) | $0.20 |
| API Gateway (1M requests) | $3.50 |
| Data Transfer OUT (10 GB) | $0.90 |
| **TOTAL** | **~$4.83/mes** |

---

## Troubleshooting

### Error: "Access Denied" al subir a presigned URL

**Causa:** IAM policy de Lambda no permite `s3:PutObject`

**Solución:**
```bash
# Verificar policy de Lambda
aws iam get-role-policy \\
  --role-name upload-lambda-stack-PresignedUrlFunctionRole-XXX \\
  --policy-name S3AccessPolicy
```

### Error: "CORS policy: No 'Access-Control-Allow-Origin' header"

**Causa:** CORS no configurado en S3 o dominio incorrecto

**Solución:**
```bash
# Verificar CORS
aws s3api get-bucket-cors --bucket {self.bucket_name}-dev

# Reconfigurar si es necesario
aws s3api put-bucket-cors \\
  --bucket {self.bucket_name}-dev \\
  --cors-configuration file://cors.json
```

### Error: "SignatureDoesNotMatch" en presigned URL

**Causa:** Cliente modificó la URL o headers

**Solución:**
- NO modificar la URL retornada por Lambda
- Usar exactamente el `Content-Type` indicado
- La URL expira en 5 minutos

---

## Limpieza (Eliminar Recursos)

```bash
# Eliminar Lambda stack
sam delete --stack-name upload-lambda-stack

# Vaciar bucket antes de eliminar
aws s3 rm s3://{self.bucket_name}-dev --recursive

# Eliminar S3 stack
aws cloudformation delete-stack --stack-name upload-s3-stack
```

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Fecha:** {datetime.now().strftime("%Y-%m-%d")}
"""
        return textwrap.dedent(guide).strip()


# ---------------------------------------------------------------------------
# === OutputWriter ===
# Responsabilidad: escribir archivos generados en disco
# ---------------------------------------------------------------------------

class OutputWriter:
    """
    Escribe los templates y archivos generados en el directorio de salida.
    """

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def write_all(
        self,
        s3_template: str,
        lambda_template: str,
        lambda_handler: str,
        lambda_requirements: str,
        migration_guide: str,
        deployment_guide: str
    ) -> None:
        """
        Escribe todos los archivos generados en output_dir.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Templates CloudFormation
        self._write_file("template-s3.yaml", s3_template)
        self._write_file("template-presigned-lambda.yaml", lambda_template)

        # Código de Lambda
        lambda_dir = self.output_dir / "presigned-function"
        lambda_dir.mkdir(exist_ok=True)
        self._write_file("presigned-function/lambda_function.py", lambda_handler)
        self._write_file("presigned-function/requirements.txt", lambda_requirements)

        # Guías de documentación
        self._write_file("MIGRATION_GUIDE.md", migration_guide)
        self._write_file("DEPLOYMENT_GUIDE.md", deployment_guide)

        print(f"\n✅ Archivos generados exitosamente en: {self.output_dir}")

    def _write_file(self, relative_path: str, content: str) -> None:
        """
        Escribe un archivo en output_dir/relative_path.
        """
        file_path = self.output_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"   📄 {relative_path}")


# ---------------------------------------------------------------------------
# === CLI ===
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """
    Parsea argumentos de línea de comandos.
    """
    parser = argparse.ArgumentParser(
        description="Genera infraestructura serverless para uploads a S3 con presigned URLs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Ejemplos de uso:
          python generate_uploads.py --manifest migration-manifest.json
          python generate_uploads.py --manifest ../manifest.json --output ./output
          python generate_uploads.py --manifest manifest.json --bucket-name my-uploads
        """)
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Ruta al migration-manifest.json (generado por Skill 01)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help=f"Directorio de salida (default: {DEFAULT_OUTPUT_DIR})"
    )

    parser.add_argument(
        "--bucket-name",
        type=str,
        default=f"{DEFAULT_BUCKET_PREFIX}-{uuid.uuid4().hex[:8]}",
        help=f"Nombre del S3 bucket (default: {DEFAULT_BUCKET_PREFIX}-<random>)"
    )

    parser.add_argument(
        "--max-file-size",
        type=int,
        default=DEFAULT_MAX_FILE_SIZE_MB,
        help=f"Tamaño máximo de archivo en MB (default: {DEFAULT_MAX_FILE_SIZE_MB})"
    )

    parser.add_argument(
        "--allowed-extensions",
        type=str,
        default=DEFAULT_ALLOWED_EXTENSIONS,
        help=f"Extensiones permitidas, separadas por coma (default: {DEFAULT_ALLOWED_EXTENSIONS})"
    )

    parser.add_argument(
        "--allowed-origins",
        type=str,
        default="https://localhost:3000,https://tu-app.com",
        help="Orígenes permitidos para CORS, separados por coma"
    )

    return parser.parse_args()


def main() -> int:
    """
    Punto de entrada principal del generador.
    """
    args = parse_args()

    print("=" * 70)
    print("Skill 04 — Migrador de Uploads")
    print(f"Versión: {SKILL_VERSION}")
    print("=" * 70)

    # Paso 1: Cargar manifest
    print(f"\n📄 Cargando manifest: {args.manifest}")
    try:
        loader = ManifestLoader(args.manifest)
        manifest = loader.load()
        upload_endpoints = loader.extract_upload_endpoints(manifest)
    except FileNotFoundError as e:
        print(f"\n{e}")
        return 1
    except ValueError as e:
        print(f"\n{e}")
        return 1

    if not upload_endpoints:
        print("\nℹ️  No se detectaron endpoints con uploads a filesystem.")
        print("   El monolito no tiene el anti-patrón AP-local-filesystem.")
        print("   Este Skill no es necesario para esta migración.")
        return 2

    print(f"\n✅ Detectados {len(upload_endpoints)} endpoint(s) con uploads:")
    for ep in upload_endpoints:
        ap_marker = " [AP-local-filesystem]" if ep['has_antipattern'] else ""
        print(f"   • [{ep['method']}] {ep['path']}{ap_marker}")

    # Paso 2: Generar templates
    print(f"\n🔧 Generando templates CloudFormation...")
    
    allowed_origins = args.allowed_origins.split(',')
    
    s3_gen = S3TemplateGenerator(args.bucket_name, allowed_origins)
    s3_template = s3_gen.generate()

    lambda_gen = LambdaTemplateGenerator(
        bucket_stack_name="upload-s3-stack",
        max_file_size_mb=args.max_file_size,
        allowed_extensions=args.allowed_extensions,
        expiration_seconds=PRESIGNED_URL_EXPIRATION
    )
    lambda_template = lambda_gen.generate()

    # Paso 3: Generar código Lambda
    print(f"🐍 Generando código Lambda...")
    lambda_code_gen = LambdaCodeGenerator()
    lambda_handler = lambda_code_gen.generate_handler()
    lambda_requirements = lambda_code_gen.generate_requirements()

    # Paso 4: Generar guías
    print(f"📖 Generando guías de migración y despliegue...")
    migration_gen = MigrationGuideGenerator(upload_endpoints)
    migration_guide = migration_gen.generate()

    deployment_gen = DeploymentGuideGenerator(args.bucket_name)
    deployment_guide = deployment_gen.generate()

    # Paso 5: Escribir archivos
    print(f"\n💾 Escribiendo archivos en: {args.output}")
    try:
        writer = OutputWriter(args.output)
        writer.write_all(
            s3_template=s3_template,
            lambda_template=lambda_template,
            lambda_handler=lambda_handler,
            lambda_requirements=lambda_requirements,
            migration_guide=migration_guide,
            deployment_guide=deployment_guide
        )
    except Exception as e:
        print(f"\n❌ Error al escribir archivos: {e}")
        return 3

    # Paso 6: Resumen final
    print("\n" + "=" * 70)
    print("✅ Generación completada exitosamente")
    print("=" * 70)
    print(f"\n📦 Infraestructura generada:")
    print(f"   • S3 bucket: {args.bucket_name}")
    print(f"   • Presigned URL expiration: {PRESIGNED_URL_EXPIRATION}s (5 minutos)")
    print(f"   • Max file size: {args.max_file_size} MB")
    print(f"   • Allowed extensions: {args.allowed_extensions}")
    print(f"\n⚠️  BREAKING CHANGE:")
    print(f"   El flujo de upload cambia de 1 paso a 2 pasos.")
    print(f"   Lee MIGRATION_GUIDE.md para detalles.\n")
    print(f"📚 Siguiente paso:")
    print(f"   1. Lee {args.output}/DEPLOYMENT_GUIDE.md")
    print(f"   2. Despliega: sam build && sam deploy")
    print(f"   3. Actualiza el cliente según MIGRATION_GUIDE.md")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
