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
aws cloudformation deploy \
  --template-file template-s3.yaml \
  --stack-name upload-s3-stack \
  --parameter-overrides Environment=dev \
  --capabilities CAPABILITY_IAM
```

**Outputs esperados:**
- `BucketName`: `taller-uploads-0ae08399-dev`
- `BucketArn`: `arn:aws:s3:::taller-uploads-0ae08399-dev`

**Verificación:**
```bash
# Verificar que el bucket existe
aws s3 ls | grep taller-uploads-0ae08399

# Verificar CORS configurado
aws s3api get-bucket-cors --bucket taller-uploads-0ae08399-dev
```

---

## Paso 2 — Desplegar Lambda de Presigned URLs

```bash
# Construir y desplegar con SAM
sam build --template-file template-presigned-lambda.yaml
sam deploy \
  --stack-name upload-lambda-stack \
  --parameter-overrides \
      Environment=dev \
      BucketStackName=upload-s3-stack \
  --capabilities CAPABILITY_IAM \
  --resolve-s3
```

**Outputs esperados:**
- `PresignedUrlFunctionArn`: ARN de la Lambda
- `ApiEndpoint`: URL del API Gateway

**Verificación:**
```bash
# Obtener URL del endpoint
API_URL=$(aws cloudformation describe-stacks \
  --stack-name upload-lambda-stack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
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
curl -X PUT "$UPLOAD_URL" \
  --upload-file test.pdf \
  -H "Content-Type: application/pdf"

# 3. Verificar que el archivo está en S3
aws s3 ls s3://taller-uploads-0ae08399-dev/$FILE_KEY
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
aws cloudformation deploy \
  --template-file template-s3.yaml \
  --stack-name upload-s3-stack \
  --parameter-overrides Environment=dev \
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
aws cloudwatch get-metric-statistics \
  --namespace AWS/S3 \
  --metric-name NumberOfObjects \
  --dimensions Name=BucketName,Value=taller-uploads-0ae08399-dev \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
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
aws iam get-role-policy \
  --role-name upload-lambda-stack-PresignedUrlFunctionRole-XXX \
  --policy-name S3AccessPolicy
```

### Error: "CORS policy: No 'Access-Control-Allow-Origin' header"

**Causa:** CORS no configurado en S3 o dominio incorrecto

**Solución:**
```bash
# Verificar CORS
aws s3api get-bucket-cors --bucket taller-uploads-0ae08399-dev

# Reconfigurar si es necesario
aws s3api put-bucket-cors \
  --bucket taller-uploads-0ae08399-dev \
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
aws s3 rm s3://taller-uploads-0ae08399-dev --recursive

# Eliminar S3 stack
aws cloudformation delete-stack --stack-name upload-s3-stack
```

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Fecha:** 2026-11-12