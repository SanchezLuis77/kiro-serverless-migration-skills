---
name: "upload-migrator"
version: "1.0.0"
description: "Genera la infraestructura para migrar uploads de filesystem local a S3 con presigned URLs, resolviendo el anti-patrón AP-local-filesystem (GAP-02). Incluye Lambda para generación de URLs firmadas y guía de migración del cliente."
author: "Luis Gerardo Sánchez Ordóñez"
tags: ["aws", "serverless", "s3", "uploads", "presigned-url", "migration"]
triggers:
  - "migrar uploads"
  - "generar s3"
  - "presigned url"
  - "subir archivos"
  - "migrate uploads"
  - "file uploads"
---

# Skill 04 — Migrador de Uploads

## Cuándo activar este Skill

Activa este Skill cuando el desarrollador necesite alguna de las siguientes acciones:

- Migrar uploads de archivos del filesystem local a Amazon S3
- Generar infraestructura para presigned URLs (subida directa del cliente a S3)
- Resolver el anti-patrón **AP-local-filesystem** (GAP-02)
- Crear Lambda para generación de URLs firmadas
- Documentar breaking changes en el API (cambio de POST multipart a flujo de 2 pasos)

**Palabras clave que activan este Skill:** "uploads", "archivos", "s3", "presigned url", "filesystem", "adjuntos", "file upload", "storage migration"

---

## Instrucciones para el agente

Sigue estos pasos en orden cuando se active el Skill:

### Paso 1 — Validar prerrequisitos

Verifica que existen los siguientes archivos:

1. **migration-manifest.json** — Generado por Skill 01
2. **Endpoints con AP-local-filesystem detectados** — Verifica en el manifest

Si no hay endpoints con uploads, informa al usuario:
```
ℹ️ No se detectaron endpoints con uploads a filesystem.
   El monolito no tiene el anti-patrón AP-local-filesystem.
   Este Skill no es necesario para esta migración.
```

### Paso 2 — Ejecutar el generador de uploads

Ejecuta el script desde la raíz del workspace:

```bash
python skills/skill-04-uploads/scripts/generate_uploads.py --manifest <ruta_manifest>
```

Parámetros opcionales:
- `--output <directorio>`: Directorio de salida (default: `./serverless-output/uploads/`)
- `--bucket-name <nombre>`: Nombre del bucket S3 (default: `taller-uploads-<random>`)
- `--max-file-size <MB>`: Tamaño máximo de archivo en MB (default: 16)
- `--allowed-extensions <ext,ext>`: Extensiones permitidas (default: `pdf,png,jpg,jpeg,docx`)

El script generará:
1. **template-s3.yaml** — S3 bucket con configuración de seguridad
2. **template-presigned-lambda.yaml** — Lambda para generar URLs firmadas
3. **presigned-function/** — Código de la Lambda (Python)
4. **MIGRATION_GUIDE.md** — Guía para migrar el cliente (breaking changes)
5. **DEPLOYMENT_GUIDE.md** — Guía de despliegue completa

### Paso 3 — Presentar el resumen al desarrollador

Presenta la siguiente información de forma estructurada:

1. **Endpoints afectados:**
   - Total de endpoints con uploads: `<N>`
   - Lista de endpoints que requieren migración:
     - [POST] /api/transacciones/{orden_id}/adjunto
     - [... otros endpoints]

2. **Infraestructura generada:**
   - S3 bucket con nombre: `<bucket_name>`
   - Versionamiento: Activado (recuperación de archivos)
   - Cifrado: AES-256 en reposo
   - CORS: Configurado para upload directo desde browser
   - Lifecycle policy: Eliminar versiones antiguas después de 90 días
   - Public access: BLOQUEADO (solo presigned URLs)

3. **Lambda de presigned URLs:**
   - Runtime: Python 3.11
   - Timeout: 10 segundos
   - Memory: 256 MB
   - Genera URLs firmadas con validez de 5 minutos
   - Valida extensión de archivo y tamaño máximo

4. **Breaking changes en el API:**
   ⚠️ **IMPORTANTE:** El flujo de upload cambia de 1 paso a 2 pasos:
   
   **ANTES (monolito):**
   ```bash
   # Un solo request multipart/form-data
   POST /api/transacciones/{id}/adjunto
   Content-Type: multipart/form-data
   
   archivo=@foto.jpg
   ```
   
   **DESPUÉS (serverless):**
   ```bash
   # Paso 1: Solicitar presigned URL
   GET /api/transacciones/{id}/adjunto/upload-url?filename=foto.jpg
   Response: {"upload_url": "https://s3...", "file_key": "uploads/..."}
   
   # Paso 2: Cliente sube directamente a S3
   PUT <upload_url>
   Content-Type: image/jpeg
   Body: <archivo binario>
   
   # Paso 3: Notificar al backend que el upload completó
   POST /api/transacciones/{id}/adjunto
   Body: {"file_key": "uploads/...", "filename": "foto.jpg"}
   ```

### Paso 4 — Guiar la migración del cliente

Informa al usuario sobre los cambios necesarios:

```markdown
## 🔄 Migración del Cliente (Breaking Changes)

### Cambios requeridos en el frontend

#### ANTES (monolito):
\`\`\`javascript
// Upload directo con FormData
const formData = new FormData();
formData.append('archivo', file);

fetch(`/api/transacciones/${id}/adjunto`, {
  method: 'POST',
  body: formData,
  headers: { 'Authorization': `Bearer ${token}` }
});
\`\`\`

#### DESPUÉS (serverless):
\`\`\`javascript
// Paso 1: Solicitar presigned URL
const response1 = await fetch(
  `/api/transacciones/${id}/adjunto/upload-url?filename=${file.name}`,
  { headers: { 'Authorization': `Bearer ${token}` } }
);
const { upload_url, file_key } = await response1.json();

// Paso 2: Upload directo a S3 (sin token, URL firmada)
await fetch(upload_url, {
  method: 'PUT',
  body: file,
  headers: { 'Content-Type': file.type }
});

// Paso 3: Notificar al backend
await fetch(`/api/transacciones/${id}/adjunto`, {
  method: 'POST',
  body: JSON.stringify({ file_key, filename: file.name }),
  headers: { 
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});
\`\`\`

### Ventajas del nuevo flujo

✅ **No consume ancho de banda del backend** — Upload directo a S3  
✅ **Más rápido** — Sin proxy por el servidor Flask/Lambda  
✅ **Más escalable** — S3 maneja millones de uploads concurrentes  
✅ **Más barato** — No pagas por data transfer en el backend  
✅ **Progress tracking** — El cliente puede monitorear el progreso directamente
```

---

## Prerrequisitos

- Python 3.9 o superior instalado en el sistema
- AWS CLI configurado con credenciales válidas
- **migration-manifest.json** generado por Skill 01
- No se requieren dependencias externas para el generador — usa únicamente módulos de la biblioteca estándar de Python

---

## Output generado

### Estructura de directorios

```
<output_dir>/
├── template-s3.yaml                   # S3 bucket + policies
├── template-presigned-lambda.yaml     # Lambda para presigned URLs
├── presigned-function/                # Código Lambda
│   ├── lambda_function.py            # Handler principal
│   └── requirements.txt              # boto3
├── MIGRATION_GUIDE.md                 # Guía para migrar el cliente
└── DEPLOYMENT_GUIDE.md                # Guía de despliegue
```

---

## Características técnicas

### Resolución de anti-patrones

#### AP-local-filesystem
**Problema:** Archivos guardados en disco local del servidor Flask con `archivo.save(ruta_local)`. En Lambda, el filesystem es efímero (solo `/tmp` con 512 MB) y no persiste entre invocaciones.

**Solución aplicada:**

| Monolito (antes) | Serverless (después) |
|------------------|----------------------|
| `archivo.save('/uploads/file.jpg')` | Cliente sube directamente a S3 |
| Filesystem local persistente | S3 bucket con versionamiento |
| Single point of failure | Alta disponibilidad (11 9s) |
| Backup manual | S3 Versioning + Cross-Region Replication |
| Tamaño limitado por disco | Ilimitado |

**Flujo de presigned URL:**

```python
# Lambda genera URL firmada
s3_client = boto3.client('s3')
presigned_url = s3_client.generate_presigned_url(
    'put_object',
    Params={
        'Bucket': bucket_name,
        'Key': f'uploads/{uuid4()}/{filename}',
        'ContentType': content_type
    },
    ExpiresIn=300  # 5 minutos
)

# Cliente usa la URL para upload directo
# PUT <presigned_url>
# Body: <archivo binario>
```

**Seguridad:**
- ✅ URL firmada válida solo 5 minutos
- ✅ Puede usarse solo UNA vez (por la naturaleza de PUT)
- ✅ Cliente NO necesita credenciales AWS
- ✅ S3 bucket NO es público (solo presigned URLs)

### S3 Bucket Configuration

**Configuración de seguridad:**
```yaml
PublicAccessBlockConfiguration:
  BlockPublicAcls: true
  BlockPublicPolicy: true
  IgnorePublicAcls: true
  RestrictPublicBuckets: true
```

**CORS para upload directo:**
```yaml
CorsConfiguration:
  CorsRules:
    - AllowedOrigins: ['https://tu-app.com']
      AllowedMethods: [PUT, POST]
      AllowedHeaders: ['*']
      MaxAge: 3600
```

**Lifecycle policy:**
```yaml
LifecycleConfiguration:
  Rules:
    - Status: Enabled
      NoncurrentVersionExpirationInDays: 90
      AbortIncompleteMultipartUpload:
        DaysAfterInitiation: 7
```

### Lambda Presigned URL

**Input:**
```json
{
  "queryStringParameters": {
    "filename": "foto_equipo.jpg",
    "content_type": "image/jpeg"
  },
  "requestContext": {
    "authorizer": {
      "userId": "123"
    }
  }
}
```

**Output:**
```json
{
  "statusCode": 200,
  "body": {
    "upload_url": "https://taller-uploads.s3.amazonaws.com/uploads/abc-123/foto_equipo.jpg?X-Amz-Signature=...",
    "file_key": "uploads/abc-123/foto_equipo.jpg",
    "expires_in": 300
  }
}
```

---

## Optimizaciones aplicadas

1. **Upload directo a S3:**
   - No consume bandwidth del backend
   - Ahorro de ~$0.09/GB de data transfer
   - Latencia reducida (sin proxy)

2. **Presigned URLs de corta duración:**
   - 5 minutos de validez
   - Reduce ventana de ataque
   - Cliente debe usarla inmediatamente

3. **S3 Intelligent-Tiering (opcional):**
   - Archivos usados frecuentemente: Standard
   - Archivos no usados: IA, Glacier
   - Ahorro automático de costos

4. **CloudFront CDN (opcional, no incluido):**
   - Para descargas frecuentes
   - Caché en edge locations
   - Ahorro en data transfer de S3

---

## Integración con otros Skills

### ⬅️ Consume desde Skill 01:
- `modules[*].endpoints`: detecta endpoints con AP-local-filesystem
- `modules[*].anti_patterns`: lista de archivos con `save()` calls

### ⬅️ Consume desde Skill 02:
- VPCId (si Lambda necesita acceder a RDS para actualizar metadata)

### ➡️ Produce para Skill 05 (Validador):
- S3 bucket name (para validar que existe)
- Presigned Lambda ARN (para tests E2E)

---

## Limitaciones conocidas

1. **Breaking change en el API:** El cliente DEBE adaptarse al flujo de 2 pasos. No hay forma de mantener compatibilidad con el flujo antiguo sin proxy.

2. **Tamaño máximo de archivo:** Presigned URLs tienen límite de 5 GB por objeto. Para archivos >5 GB, se requiere multipart upload (más complejo).

3. **Validación de contenido:** S3 NO valida el contenido del archivo (virus, malware). Considerar AWS Lambda + ClamAV para escaneo post-upload.

4. **Costo de GET requests:** Cada descarga desde S3 cuesta $0.0004/1000 requests. Para descargas muy frecuentes, considerar CloudFront.

---

## Troubleshooting

### Error 403 al subir a presigned URL

**Causa:** URL expirada o CORS mal configurado

**Solución:**
```bash
# Verificar CORS del bucket
aws s3api get-bucket-cors --bucket <bucket-name>

# Regenerar presigned URL (5 min de validez)
```

### Error "SignatureDoesNotMatch"

**Causa:** Cliente modificó la URL o headers

**Solución:**
- NO modificar la URL presigned
- Usar exactamente los headers indicados
- Content-Type debe coincidir con el solicitado

### Lambda retorna "AccessDenied"

**Causa:** IAM policy no permite s3:PutObject

**Solución:**
```yaml
Policies:
  - Statement:
      - Effect: Allow
        Action:
          - s3:PutObject
          - s3:GetObject
        Resource: !Sub '${UploadBucket.Arn}/*'
```

---

## Referencias

- [S3 Presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html)
- [S3 CORS Configuration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html)
- [S3 Security Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
- [Lambda S3 Integration](https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html)

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software  
**Institución:** Pontificia Universidad Javeriana Cali  
**Director:** Juan Gabriel Quintero Barbosa — Head Solutions Architecture, AWS Colombia
