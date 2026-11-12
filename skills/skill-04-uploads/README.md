# Skill 04 — Migrador de Uploads

**Estado:** ✅ Completado  
**Versión:** 1.0.0  
**Última actualización:** 9 de noviembre de 2026

---

## Descripción

Genera la infraestructura serverless para migrar uploads de archivos desde filesystem local (Flask) a Amazon S3 con presigned URLs. Resuelve el anti-patrón **AP-local-filesystem** (GAP-02) detectado en monolitos Flask que usan `archivo.save(ruta_local)` para guardar archivos en disco.

### ¿Qué genera este Skill?

1. **S3 bucket** con configuración de seguridad:
   - Versionamiento activado (recuperación de archivos)
   - Cifrado AES-256 en reposo
   - CORS para upload directo desde browser
   - Public access bloqueado (solo presigned URLs)
   - Lifecycle policy (eliminar versiones antiguas después de 90 días)

2. **Lambda para presigned URLs** (Python 3.11):
   - Genera URLs firmadas con validez de 5 minutos
   - Valida extensión de archivo y tamaño máximo
   - Integrada con API Gateway

3. **Código de la Lambda:**
   - Handler completo en Python
   - Validación de inputs
   - Manejo de errores
   - `requirements.txt` (boto3)

4. **Guías de documentación:**
   - `MIGRATION_GUIDE.md` — Cómo adaptar el cliente (breaking changes)
   - `DEPLOYMENT_GUIDE.md` — Cómo desplegar en AWS

---

## Uso

### Prerrequisitos

- Python 3.9 o superior
- **migration-manifest.json** generado por Skill 01
- AWS CLI configurado (para despliegue)
- SAM CLI instalado (para despliegue de Lambda)

### Ejecución

```bash
# Desde la raíz del workspace
python skills/skill-04-uploads/scripts/generate_uploads.py \
  --manifest monolith/migration-manifest.json

# Con configuración personalizada
python skills/skill-04-uploads/scripts/generate_uploads.py \
  --manifest monolith/migration-manifest.json \
  --output ./output/uploads \
  --bucket-name my-company-uploads \
  --max-file-size 32 \
  --allowed-extensions "pdf,png,jpg,docx,xlsx"
```

### Parámetros

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--manifest` | Ruta al migration-manifest.json | (requerido) |
| `--output` | Directorio de salida | `serverless-output/uploads/` |
| `--bucket-name` | Nombre del S3 bucket | `taller-uploads-<random>` |
| `--max-file-size` | Tamaño máximo en MB | `16` |
| `--allowed-extensions` | Extensiones permitidas (CSV) | `pdf,png,jpg,jpeg,docx,xlsx` |
| `--allowed-origins` | Orígenes CORS (CSV) | `https://localhost:3000,https://tu-app.com` |

### Output generado

```
<output_dir>/
├── template-s3.yaml                   # CloudFormation: S3 bucket
├── template-presigned-lambda.yaml     # SAM: Lambda + API Gateway
├── presigned-function/                # Código Lambda
│   ├── lambda_function.py            # Handler principal
│   └── requirements.txt              # boto3
├── MIGRATION_GUIDE.md                 # Guía para migrar el cliente
└── DEPLOYMENT_GUIDE.md                # Guía de despliegue AWS
```

---

## Anti-patrón resuelto

### AP-local-filesystem (GAP-02)

**Problema:**  
El monolito Flask usa `archivo.save('/uploads/file.jpg')` para guardar archivos en disco local. En Lambda, el filesystem es efímero (solo `/tmp` con 512 MB) y no persiste entre invocaciones.

**Solución aplicada:**

| Monolito (antes) | Serverless (después) |
|------------------|----------------------|
| `archivo.save('/uploads/file.jpg')` | Cliente sube directamente a S3 |
| Filesystem local persistente | S3 bucket con versionamiento |
| Single point of failure | Alta disponibilidad (11 9s) |
| Backup manual | S3 Versioning + Cross-Region Replication |
| Tamaño limitado por disco | Ilimitado |

**Arquitectura:**

```
┌────────────┐     1. GET /upload-url     ┌────────────────┐
│  Cliente   │ ───────────────────────────> │ Lambda Presigned│
│  (Browser) │ <─────────────────────────  │ URL Generator   │
└────────────┘     2. presigned_url       └────────────────┘
      │
      │ 3. PUT <presigned_url>
      │    (upload directo)
      ▼
┌─────────────────┐
│   S3 Bucket     │
│ (versionado +   │
│  cifrado)       │
└─────────────────┘
```

---

## Breaking Changes

⚠️ **IMPORTANTE:** El flujo de upload cambia de 1 paso (multipart/form-data) a 2 pasos (presigned URL + PUT directo a S3).

### ANTES (monolito):

```javascript
// Un solo request con FormData
const formData = new FormData();
formData.append('archivo', file);

await fetch('/api/transacciones/123/adjunto', {
  method: 'POST',
  body: formData
});
```

### DESPUÉS (serverless):

```javascript
// Paso 1: Solicitar presigned URL
const { upload_url, file_key } = await fetch(
  '/api/transacciones/123/adjunto/upload-url?filename=foto.jpg'
).then(r => r.json());

// Paso 2: Upload directo a S3 (sin token, URL firmada)
await fetch(upload_url, {
  method: 'PUT',
  body: file,
  headers: { 'Content-Type': file.type }
});

// Paso 3: Notificar al backend
await fetch('/api/transacciones/123/adjunto', {
  method: 'POST',
  body: JSON.stringify({ file_key, filename: file.name }),
  headers: { 'Content-Type': 'application/json' }
});
```

**Ventajas del nuevo flujo:**

✅ **No consume ancho de banda del backend** — Upload directo a S3  
✅ **Más rápido** — Sin proxy por el servidor Flask/Lambda  
✅ **Más escalable** — S3 maneja millones de uploads concurrentes  
✅ **Más barato** — No pagas por data transfer en el backend  
✅ **Progress tracking** — El cliente puede monitorear el progreso directamente

---

## Integración con otros Skills

### ⬅️ Consume desde Skill 01:
- `modules[*].endpoints`: detecta endpoints con anti-patrón AP-local-filesystem
- `modules[*].anti_patterns`: lista de archivos con `save()` calls

### ⬅️ Consume desde Skill 02 (opcional):
- VPCId — Si Lambda necesita acceder a RDS para actualizar metadata de archivos

### ➡️ Produce para Skill 05 (Validador):
- S3 bucket name — Para validar que existe
- Presigned Lambda ARN — Para tests E2E

---

## Ejemplos de uso en Kiro IDE

### Detectar endpoints con uploads

```
Usuario: "quiero migrar los uploads a S3"
Kiro: [activa Skill 04]
      [lee migration-manifest.json]
      [detecta 1 endpoint con AP-local-filesystem]
      [genera infraestructura S3 + Lambda]
      [muestra breaking changes y guías]
```

### Consulta sobre arquitectura

```
Usuario: "cómo funciona el upload en serverless?"
Kiro: [activa Skill 04]
      [explica flujo de presigned URLs]
      [muestra código de ejemplo]
      [recomienda best practices]
```

---

## Limitaciones conocidas

1. **Breaking change en el API:** El cliente DEBE adaptarse al flujo de 2 pasos. No hay forma de mantener compatibilidad con el flujo antiguo sin proxy.

2. **Tamaño máximo de archivo:** Presigned URLs tienen límite de 5 GB por objeto. Para archivos >5 GB, se requiere multipart upload (más complejo).

3. **Validación de contenido:** S3 NO valida el contenido del archivo (virus, malware). Considerar AWS Lambda + ClamAV para escaneo post-upload.

4. **Costo de GET requests:** Cada descarga desde S3 cuesta $0.0004/1000 requests. Para descargas muy frecuentes, considerar CloudFront.

---

## Costos estimados

| Recurso | Costo Mensual (1000 uploads/mes, 10 GB almacenados) |
|---------|-----------------------------------------------------|
| S3 Standard Storage | $0.23 |
| Lambda (1M requests) | $0.20 |
| API Gateway (1M requests) | $3.50 |
| Data Transfer OUT (10 GB) | $0.90 |
| **TOTAL** | **~$4.83/mes** |

---

## Tests

```bash
# Test 1: Generación básica
python skills/skill-04-uploads/scripts/generate_uploads.py \
  --manifest monolith/migration-manifest.json

# Test 2: Configuración personalizada
python skills/skill-04-uploads/scripts/generate_uploads.py \
  --manifest monolith/migration-manifest.json \
  --bucket-name test-bucket \
  --max-file-size 32 \
  --allowed-extensions "pdf,png"

# Test 3: Sin endpoints de uploads
python skills/skill-04-uploads/scripts/generate_uploads.py \
  --manifest empty-manifest.json
# Esperado: exit code 2, mensaje "No se detectaron endpoints con uploads"
```

---

## Referencias

- [S3 Presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html)
- [S3 CORS Configuration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html)
- [S3 Security Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
- [Lambda S3 Integration](https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html)

---

## Siguientes pasos

1. ✅ Generar infraestructura con el script
2. ⏭️ Revisar MIGRATION_GUIDE.md para cambios en el cliente
3. ⏭️ Desplegar con SAM CLI (ver DEPLOYMENT_GUIDE.md)
4. ⏭️ Actualizar frontend para flujo de 2 pasos
5. ⏭️ Probar upload E2E
6. ⏭️ Configurar monitoreo CloudWatch

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software  
**Institución:** Pontificia Universidad Javeriana Cali  
**Director:** Juan Gabriel Quintero Barbosa — Head Solutions Architecture, AWS Colombia
