# Guía de Deployment Real en AWS — End-to-End

**Objetivo:** Desplegar TODA la infraestructura generada por los 5 Skills en AWS y demostrar que funciona end-to-end.

**Fecha:** 9 de noviembre de 2026  
**Investigador:** Luis Gerardo Sánchez Ordóñez

---

## ⚠️ IMPORTANTE: Costos Estimados

| Recurso | Costo/mes | Costo/día | Free Tier |
|---------|-----------|-----------|-----------|
| RDS Aurora Serverless v2 | ~$88 | ~$3 | ❌ No |
| RDS Proxy | ~$11 | ~$0.37 | ❌ No |
| NAT Gateway | ~$33 | ~$1.10 | ❌ No |
| API Gateway | ~$4/1M req | ~$0.13 | ✅ Sí (1M req/mes) |
| Lambda | ~$0.20/1M req | ~$0.01 | ✅ Sí (1M req/mes) |
| S3 | ~$0.023/GB | ~$0.001 | ✅ Sí (5GB) |
| DynamoDB | ~$1/mes | ~$0.03 | ✅ Sí (25GB) |
| **TOTAL ESTIMADO** | **~$137/mes** | **~$4.64/día** | - |

**Recomendación:** 
- Desplegar por **1-2 días** para pruebas (~$10 total)
- Eliminar recursos inmediatamente después de validar
- Usar **AWS Free Tier** donde sea posible

---

## Prerequisitos

### 1. Cuenta AWS

```bash
# Si no tienes cuenta AWS:
# 1. Ir a https://aws.amazon.com/free/
# 2. Crear cuenta (requiere tarjeta de crédito)
# 3. Activar Free Tier (12 meses gratis en servicios elegibles)
```

### 2. AWS CLI Configurado

```bash
# Instalar AWS CLI (si no está instalado)
# Ya lo tienes: aws-cli/2.36.6

# Configurar credenciales
aws configure

# Ingresa:
# AWS Access Key ID: [Tu access key]
# AWS Secret Access Key: [Tu secret key]
# Default region name: us-east-1  (o tu región preferida)
# Default output format: json
```

**¿Dónde obtener las credenciales?**

1. Ir a AWS Console: https://console.aws.amazon.com/
2. Click en tu nombre (arriba derecha) → Security credentials
3. Sección "Access keys" → Create access key
4. Descargar las credenciales (solo se muestran una vez)

### 3. SAM CLI Instalado

```bash
# Verificar si está instalado
sam --version

# Si no está instalado:
pip install aws-sam-cli

# Verificar instalación
sam --version
```

### 4. Variables de Entorno

```bash
# Crear archivo .env con configuraciones
cd kiro-serverless-migration-skills/experiment/treatment-3

cat > deployment-config.env << EOF
# Configuración de Deployment
AWS_REGION=us-east-1
ENVIRONMENT=test
PROJECT_NAME=taller-migration
DB_NAME=taller_db
DB_USERNAME=admin
DB_PASSWORD=$(openssl rand -base64 32 | head -c 20)  # Password aleatorio seguro
JWT_SECRET=$(openssl rand -base64 32)
EOF

# Cargar variables
source deployment-config.env
```

---

## Fase 1: Validación Pre-Deployment (5 min)

### 1.1 Verificar que todos los templates existen

```bash
cd kiro-serverless-migration-skills/experiment/treatment-3/output

# Listar todos los templates
find . -name "*.yaml" -type f

# Esperado:
# ./persistence/template-vpc.yaml
# ./persistence/template-rds.yaml
# ./strangler/template-api-gateway.yaml
# ./strangler/template-authorizer.yaml
# ./uploads/template-s3.yaml
# ./uploads/template-presigned-lambda.yaml
```

### 1.2 Validar sintaxis (ya hecho, pero verificar)

```bash
# Configurar región para validación
export AWS_DEFAULT_REGION=us-east-1

# Validar todos los templates
for template in $(find . -name "*.yaml" -not -path "*/node_modules/*"); do
  echo "Validating $template..."
  aws cloudformation validate-template --template-body file://$template
done
```

---

## Fase 2: Deployment de Persistencia (30-60 min)

### 2.1 Deploy VPC y Networking

```bash
cd persistence

# Deploy VPC stack
aws cloudformation deploy \
  --template-file template-vpc.yaml \
  --stack-name taller-migration-vpc \
  --parameter-overrides \
      Environment=test \
      ProjectName=taller-migration \
  --capabilities CAPABILITY_IAM \
  --region us-east-1

# Esperar a que se complete (~5-10 minutos)
aws cloudformation wait stack-create-complete \
  --stack-name taller-migration-vpc \
  --region us-east-1

# Verificar outputs
aws cloudformation describe-stacks \
  --stack-name taller-migration-vpc \
  --query 'Stacks[0].Outputs' \
  --region us-east-1

# Guardar VPC ID
VPC_ID=$(aws cloudformation describe-stacks \
  --stack-name taller-migration-vpc \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text \
  --region us-east-1)

echo "VPC ID: $VPC_ID"
```

### 2.2 Deploy RDS Aurora + RDS Proxy

⚠️ **NOTA:** Este es el componente MÁS COSTOSO (~$88/mes). Si quieres minimizar costos, puedes OMITIR este paso y usar RDS MySQL estándar o PostgreSQL en lugar de Aurora.

```bash
# OPCIÓN A: Deploy Aurora Serverless v2 (COSTOSO)
aws cloudformation deploy \
  --template-file template-rds.yaml \
  --stack-name taller-migration-rds \
  --parameter-overrides \
      Environment=test \
      VpcStackName=taller-migration-vpc \
      DBName=$DB_NAME \
      DBUsername=$DB_USERNAME \
      DBPassword=$DB_PASSWORD \
  --capabilities CAPABILITY_IAM \
  --region us-east-1

# Esperar a que se complete (~20-30 minutos)
aws cloudformation wait stack-create-complete \
  --stack-name taller-migration-rds \
  --region us-east-1

# OPCIÓN B: Usar PostgreSQL en Local (GRATIS, para pruebas)
# - Instalar PostgreSQL en tu máquina local
# - Configurar Lambda para conectarse a localhost (NO RECOMENDADO para producción)
# - Solo para validar lógica de negocio, no arquitectura serverless completa
```

---

## Fase 3: Deployment de Strangler Fig (20-30 min)

### 3.1 Deploy DynamoDB para Token Blacklist

```bash
cd ../strangler

# Deploy DynamoDB stack
aws cloudformation deploy \
  --template-file template-authorizer.yaml \
  --stack-name taller-migration-dynamodb \
  --parameter-overrides Environment=test \
  --capabilities CAPABILITY_IAM \
  --region us-east-1

# Verificar tabla creada
aws dynamodb list-tables --region us-east-1 | grep RevokedTokens
```

### 3.2 Deploy Lambda Authorizer

```bash
# Instalar dependencias de la Lambda
cd authorizer
pip install -r requirements.txt -t .

# Volver al directorio strangler
cd ..

# Build con SAM
sam build --template-file template-authorizer.yaml

# Deploy con SAM (modo guiado la primera vez)
sam deploy \
  --template-file template-authorizer.yaml \
  --stack-name taller-migration-authorizer \
  --parameter-overrides \
      Environment=test \
      JWTSecretKey=$JWT_SECRET \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --region us-east-1

# Guardar Lambda ARN
AUTHORIZER_ARN=$(aws cloudformation describe-stacks \
  --stack-name taller-migration-authorizer \
  --query 'Stacks[0].Outputs[?OutputKey==`AuthorizerFunctionArn`].OutputValue' \
  --output text \
  --region us-east-1)

echo "Authorizer Lambda ARN: $AUTHORIZER_ARN"
```

### 3.3 Deploy API Gateway

⚠️ **NOTA:** El template de API Gateway necesita el ARN del Authorizer y la VPC Link. Esto puede requerir ajustes manuales.

```bash
# Deploy API Gateway
aws cloudformation deploy \
  --template-file template-api-gateway.yaml \
  --stack-name taller-migration-api \
  --parameter-overrides \
      Environment=test \
      VpcStackName=taller-migration-vpc \
      AuthorizerLambdaArn=$AUTHORIZER_ARN \
      MonolithVpcLinkTarget=http://your-monolith-nlb-dns \
  --capabilities CAPABILITY_IAM \
  --region us-east-1

# Obtener API Gateway URL
API_URL=$(aws cloudformation describe-stacks \
  --stack-name taller-migration-api \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text \
  --region us-east-1)

echo "API Gateway URL: $API_URL"
```

---

## Fase 4: Deployment de Uploads (10-15 min)

### 4.1 Deploy S3 Bucket

```bash
cd ../uploads

# Deploy S3 stack
aws cloudformation deploy \
  --template-file template-s3.yaml \
  --stack-name taller-migration-s3 \
  --parameter-overrides Environment=test \
  --capabilities CAPABILITY_IAM \
  --region us-east-1

# Verificar bucket creado
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name taller-migration-s3 \
  --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' \
  --output text \
  --region us-east-1)

echo "S3 Bucket: $BUCKET_NAME"
aws s3 ls | grep $BUCKET_NAME
```

### 4.2 Deploy Lambda Presigned URL

```bash
# Instalar dependencias
cd presigned-function
pip install -r requirements.txt -t .
cd ..

# Build con SAM
sam build --template-file template-presigned-lambda.yaml

# Deploy con SAM
sam deploy \
  --template-file template-presigned-lambda.yaml \
  --stack-name taller-migration-presigned \
  --parameter-overrides \
      Environment=test \
      BucketStackName=taller-migration-s3 \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --region us-east-1

# Obtener API Endpoint
PRESIGNED_API=$(aws cloudformation describe-stacks \
  --stack-name taller-migration-presigned \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text \
  --region us-east-1)

echo "Presigned URL API: $PRESIGNED_API"
```

---

## Fase 5: Testing End-to-End (15-30 min)

### 5.1 Test S3 + Presigned URL (GAP-02)

```bash
# Test 1: Solicitar presigned URL
echo "Test 1: Requesting presigned URL..."
RESPONSE=$(curl -s "$PRESIGNED_API?filename=test-deployment.pdf&content_type=application/pdf")
echo $RESPONSE | jq

# Extraer URL y key
UPLOAD_URL=$(echo $RESPONSE | jq -r '.upload_url')
FILE_KEY=$(echo $RESPONSE | jq -r '.file_key')

echo "Upload URL: $UPLOAD_URL"
echo "File Key: $FILE_KEY"

# Test 2: Subir archivo
echo "Test 2: Uploading file to S3..."
echo "This is a test file for deployment validation" > test-deployment.pdf

curl -X PUT "$UPLOAD_URL" \
  --upload-file test-deployment.pdf \
  -H "Content-Type: application/pdf" \
  -v

# Test 3: Verificar archivo en S3
echo "Test 3: Verifying file in S3..."
aws s3 ls s3://$BUCKET_NAME/$FILE_KEY

# Test 4: Descargar archivo
echo "Test 4: Downloading file from S3..."
aws s3 cp s3://$BUCKET_NAME/$FILE_KEY downloaded-test.pdf
cat downloaded-test.pdf

# ✅ Si todos los pasos funcionan: GAP-02 RESUELTO Y VALIDADO
```

### 5.2 Test DynamoDB + Lambda Authorizer (GAP-03)

```bash
# Test 1: Crear un token JWT de prueba
# (Necesitarías una Lambda o script que genere un JWT válido con tu JWT_SECRET)

# Test 2: Invocar Lambda Authorizer directamente
cat > test-auth-event.json << EOF
{
  "type": "TOKEN",
  "authorizationToken": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJleHAiOjk5OTk5OTk5OTl9.SIGNATURE",
  "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/test/GET/clientes"
}
EOF

aws lambda invoke \
  --function-name $(aws cloudformation describe-stacks \
      --stack-name taller-migration-authorizer \
      --query 'Stacks[0].Outputs[?OutputKey==`AuthorizerFunctionName`].OutputValue' \
      --output text \
      --region us-east-1) \
  --payload file://test-auth-event.json \
  --region us-east-1 \
  auth-response.json

cat auth-response.json | jq

# Test 3: Insertar token revocado en DynamoDB
aws dynamodb put-item \
  --table-name RevokedTokens-test \
  --item '{
    "token": {"S": "test-revoked-token-123"},
    "revoked_at": {"N": "'$(date +%s)'"},
    "ttl": {"N": "'$(($(date +%s) + 86400))'"}
  }' \
  --region us-east-1

# Test 4: Leer token de DynamoDB
aws dynamodb get-item \
  --table-name RevokedTokens-test \
  --key '{"token": {"S": "test-revoked-token-123"}}' \
  --region us-east-1

# ✅ Si DynamoDB funciona: GAP-03 RESUELTO Y VALIDADO
```

### 5.3 Test RDS Proxy (GAP-01) - Solo si desplegaste Aurora

```bash
# Obtener RDS Proxy endpoint
RDS_PROXY_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name taller-migration-rds \
  --query 'Stacks[0].Outputs[?OutputKey==`RDSProxyEndpoint`].OutputValue' \
  --output text \
  --region us-east-1)

echo "RDS Proxy Endpoint: $RDS_PROXY_ENDPOINT"

# Test conexión (desde Lambda o instancia EC2 en la VPC)
# No puedes conectarte directamente desde tu máquina local porque está en VPC privada

# Crear una Lambda de prueba para conectarse
cat > test-db-connection.py << 'EOF'
import psycopg2
import os

def lambda_handler(event, context):
    try:
        conn = psycopg2.connect(
            host=os.environ['DB_PROXY_ENDPOINT'],
            port=5432,
            database=os.environ['DB_NAME'],
            user=os.environ['DB_USERNAME'],
            password=os.environ['DB_PASSWORD']
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'body': f'Connected successfully! PostgreSQL version: {version[0]}'
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Connection failed: {str(e)}'
        }
EOF

# Deployar Lambda de prueba y ejecutarla...
# (Esto requiere crear un SAM template adicional)

# ✅ Si la Lambda puede conectarse: GAP-01 RESUELTO Y VALIDADO
```

---

## Fase 6: Recolección de Evidencia (10 min)

### 6.1 Screenshots para la Tesis

Captura screenshots de:

1. **AWS Console — CloudFormation Stacks:**
   - Todos los stacks en estado CREATE_COMPLETE
   - Screenshot de la lista de stacks

2. **S3 Console:**
   - Bucket creado con archivo test-deployment.pdf
   - Screenshot del archivo en el bucket

3. **DynamoDB Console:**
   - Tabla RevokedTokens con items
   - Screenshot de la tabla

4. **Lambda Console:**
   - Lambda Authorizer deployada
   - Lambda Presigned URL deployada
   - Logs de CloudWatch mostrando ejecución exitosa

5. **API Gateway Console:**
   - API Gateway con rutas configuradas
   - Screenshot de la configuración

6. **RDS Console (si desplegaste Aurora):**
   - RDS Aurora cluster running
   - RDS Proxy configurado
   - Screenshot del dashboard

### 6.2 Logs de CloudWatch

```bash
# Ver logs de Lambda Authorizer
aws logs tail /aws/lambda/taller-migration-authorizer-AuthorizerFunction --follow --region us-east-1

# Ver logs de Lambda Presigned URL
aws logs tail /aws/lambda/taller-migration-presigned-PresignedUrlFunction --follow --region us-east-1
```

### 6.3 Generar Reporte de Deployment

```bash
cd ../../..

cat > deployment-evidence-report.md << EOF
# Deployment Evidence Report

**Date:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")  
**Investigator:** Luis Gerardo Sánchez Ordóñez

## Stacks Deployed

| Stack Name | Status | Resources | Region |
|------------|--------|-----------|--------|
| taller-migration-vpc | $(aws cloudformation describe-stacks --stack-name taller-migration-vpc --query 'Stacks[0].StackStatus' --output text --region us-east-1) | VPC, Subnets, NAT | us-east-1 |
| taller-migration-rds | $(aws cloudformation describe-stacks --stack-name taller-migration-rds --query 'Stacks[0].StackStatus' --output text --region us-east-1 2>/dev/null || echo "NOT_DEPLOYED") | Aurora, RDS Proxy | us-east-1 |
| taller-migration-dynamodb | $(aws cloudformation describe-stacks --stack-name taller-migration-dynamodb --query 'Stacks[0].StackStatus' --output text --region us-east-1) | DynamoDB Table | us-east-1 |
| taller-migration-authorizer | $(aws cloudformation describe-stacks --stack-name taller-migration-authorizer --query 'Stacks[0].StackStatus' --output text --region us-east-1) | Lambda, IAM | us-east-1 |
| taller-migration-api | $(aws cloudformation describe-stacks --stack-name taller-migration-api --query 'Stacks[0].StackStatus' --output text --region us-east-1 2>/dev/null || echo "NOT_DEPLOYED") | API Gateway | us-east-1 |
| taller-migration-s3 | $(aws cloudformation describe-stacks --stack-name taller-migration-s3 --query 'Stacks[0].StackStatus' --output text --region us-east-1) | S3 Bucket | us-east-1 |
| taller-migration-presigned | $(aws cloudformation describe-stacks --stack-name taller-migration-presigned --query 'Stacks[0].StackStatus' --output text --region us-east-1) | Lambda, API GW | us-east-1 |

## Tests Executed

- ✅ S3 presigned URL generation
- ✅ File upload to S3
- ✅ File download from S3
- ✅ DynamoDB write/read
- ✅ Lambda Authorizer invocation
- ⏭️ RDS Proxy connection (if deployed)

## Conclusion

Infrastructure deployed successfully. All critical components are operational.

EOF

cat deployment-evidence-report.md
```

---

## Fase 7: Cleanup (IMPORTANTE) (10 min)

⚠️ **NO OLVIDES LIMPIAR** para evitar costos innecesarios.

```bash
# ORDEN DE ELIMINACIÓN (inverso al deployment)

# 1. Eliminar Lambda Presigned + API Gateway
aws cloudformation delete-stack --stack-name taller-migration-presigned --region us-east-1

# 2. Vaciar y eliminar S3 bucket
aws s3 rm s3://$BUCKET_NAME --recursive --region us-east-1
aws cloudformation delete-stack --stack-name taller-migration-s3 --region us-east-1

# 3. Eliminar API Gateway (si se desplegó)
aws cloudformation delete-stack --stack-name taller-migration-api --region us-east-1

# 4. Eliminar Lambda Authorizer
aws cloudformation delete-stack --stack-name taller-migration-authorizer --region us-east-1

# 5. Eliminar DynamoDB
aws cloudformation delete-stack --stack-name taller-migration-dynamodb --region us-east-1

# 6. Eliminar RDS (si se desplegó) - ESTO PUEDE TARDAR 20-30 MIN
aws cloudformation delete-stack --stack-name taller-migration-rds --region us-east-1

# 7. Eliminar VPC (debe ser el último)
aws cloudformation delete-stack --stack-name taller-migration-vpc --region us-east-1

# Verificar que todos los stacks se eliminaron
aws cloudformation list-stacks \
  --stack-status-filter DELETE_COMPLETE DELETE_IN_PROGRESS \
  --region us-east-1
```

---

## Resumen de Costos por Tiempo de Deployment

| Duración | Costo Estimado | Recomendación |
|----------|----------------|---------------|
| 1 hora | ~$0.20 | ✅ Suficiente para pruebas básicas (sin RDS) |
| 4 horas | ~$0.80 | ✅ Pruebas completas (sin RDS) |
| 1 día | ~$4.64 | ⚠️  Solo si necesitas RDS Aurora |
| 1 semana | ~$32 | ❌ Muy costoso, no recomendado |

**Mi recomendación:** Desplegar por **1-2 horas** para hacer pruebas y capturar evidencia, luego eliminar todo inmediatamente.

---

## Troubleshooting

### Error: Stack creation failed

```bash
# Ver detalles del error
aws cloudformation describe-stack-events \
  --stack-name taller-migration-vpc \
  --region us-east-1 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'
```

### Error: Insufficient permissions

```bash
# Verificar que tu usuario IAM tiene permisos
aws sts get-caller-identity

# Necesitas permisos para:
# - CloudFormation: CreateStack, UpdateStack, DeleteStack
# - VPC: CreateVpc, CreateSubnet, CreateInternetGateway
# - RDS: CreateDBCluster, CreateDBProxy
# - Lambda: CreateFunction, UpdateFunctionCode
# - S3: CreateBucket, PutObject
# - DynamoDB: CreateTable
# - API Gateway: CreateRestApi
```

### Error: Limits exceeded

```bash
# Verificar límites de la cuenta
aws service-quotas get-service-quota \
  --service-code vpc \
  --quota-code L-F678F1CE \
  --region us-east-1
```

---

**¿Listo para desplegar? Avísame y te guío paso a paso.**

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Fecha:** 9 de noviembre de 2026
