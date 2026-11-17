# Deployment Guide — Skill 02: Migrador de Persistencia

**Generado:** 2026-11-17T16:22:13.471876
**Base de datos:** taller_db
**VPC CIDR:** 10.0.0.0/16
**Skill Version:** 1.0.0

---

## 📋 Resumen

Este directorio contiene la infraestructura de persistencia serverless para tu aplicación Flask migrada:

- **VPC** con subnets públicas/privadas, NAT Gateway, security groups
- **RDS Aurora Serverless v2** (PostgreSQL 15.x)
- **RDS Proxy** para connection pooling desde Lambdas
- **Secrets Manager** para credenciales seguras

**Modelos migrados:** 5
**Patrones SQLite detectados:** 0

---

## 🚀 Pasos de Despliegue

### Paso 1: Desplegar VPC (primero)

```bash
aws cloudformation deploy \
  --template-file template-vpc.yaml \
  --stack-name taller-vpc \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

**Tiempo estimado:** 3-5 minutos

**Validar:** Verifica que la VPC y subnets se crearon:
```bash
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=taller-vpc"
```

### Paso 2: Desplegar RDS Aurora (después de VPC)

⚠️ **IMPORTANTE:** Debes proporcionar una contraseña segura para el usuario master.

```bash
aws cloudformation deploy \
  --template-file template-rds.yaml \
  --stack-name taller-rds \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      EnvironmentName=taller \
      DBName=taller_db \
      DBUsername=admin \
      DBPassword=TU_PASSWORD_SEGURA_AQUI \
  --region us-east-1
```

**Tiempo estimado:** 10-15 minutos

**Validar:** Verifica que el cluster Aurora se creó:
```bash
aws rds describe-db-clusters --db-cluster-identifier taller-aurora-cluster
```

### Paso 3: Obtener endpoints

```bash
# Aurora Cluster Endpoint (conexión directa, no recomendada desde Lambda)
aws cloudformation describe-stacks \
  --stack-name taller-rds \
  --query "Stacks[0].Outputs[?OutputKey=='DBClusterEndpoint'].OutputValue" \
  --output text

# RDS Proxy Endpoint (USAR ESTE en Lambdas)
aws cloudformation describe-stacks \
  --stack-name taller-rds \
  --query "Stacks[0].Outputs[?OutputKey=='DBProxyEndpoint'].OutputValue" \
  --output text
```

---

## 🔧 Configuración de Lambdas

### Variables de entorno requeridas

Cada Lambda que acceda a la base de datos debe tener estas variables:

```yaml
Environment:
  Variables:
    DB_PROXY_ENDPOINT: <valor del output DBProxyEndpoint>
    DB_NAME: taller_db
    DB_SECRET_ARN: <valor del output DBSecretArn>
    DB_PORT: '5432'
```

### VPC Configuration

Las Lambdas DEBEN desplegarse en las subnets privadas de la VPC:

```yaml
VpcConfig:
  SecurityGroupIds:
    - Fn::ImportValue: taller-LambdaSG
  SubnetIds:
    - Fn::ImportValue: taller-PrivateSubnet1
    - Fn::ImportValue: taller-PrivateSubnet2
```

### IAM Policy requerida

```yaml
Policies:
  - Statement:
      - Effect: Allow
        Action:
          - secretsmanager:GetSecretValue
        Resource: !ImportValue taller-DBSecretArn
      - Effect: Allow
        Action:
          - rds-db:connect
        Resource: '*'
      - Effect: Allow
        Action:
          - ec2:CreateNetworkInterface
          - ec2:DescribeNetworkInterfaces
          - ec2:DeleteNetworkInterface
        Resource: '*'
```

---

## 💾 Migración de Datos

### Opción A: Export/Import manual

1. **Exportar datos de SQLite:**
```bash
sqlite3 monolith/instance/taller.db .dump > dump.sql
```

2. **Editar dump.sql:** Reemplazar sintaxis SQLite por PostgreSQL

3. **Importar a Aurora:**
```bash
psql -h <DBProxyEndpoint> -U admin -d taller_db -f dump.sql
```

### Opción B: ETL programático (recomendado para producción)

Crear un script Python que:
1. Lee de SQLite con SQLAlchemy
2. Escribe en PostgreSQL con SQLAlchemy
3. Maneja conversiones de tipos y funciones

---

## 🧪 Testing de Conexión

### Test desde Lambda local

```python
import psycopg2
import boto3
import json

def get_db_credentials():
    secrets_client = boto3.client('secretsmanager')
    secret_arn = "<DBSecretArn>"
    response = secrets_client.get_secret_value(SecretId=secret_arn)
    return json.loads(response['SecretString'])

def test_connection():
    creds = get_db_credentials()
    conn = psycopg2.connect(
        host="<DBProxyEndpoint>",
        port=5432,
        database="taller_db",
        user=creds['username'],
        password=creds['password']
    )
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print(cur.fetchone())
    conn.close()

if __name__ == "__main__":
    test_connection()
```

---

## 💰 Estimación de Costos (us-east-1)

### Costos fijos mensuales
- **RDS Proxy:** ~$0.015/hora × 730 horas = **~$11/mes**
- **NAT Gateway:** ~$0.045/hora × 730 horas = **~$33/mes**
- **NAT Gateway data:** ~$0.045/GB procesado

### Costos variables (pago por uso)
- **Aurora Serverless v2:** ~$0.12/ACU-hora (0.5-2 ACU configurados)
  - Mínimo (~0.5 ACU 24/7): ~$44/mes
  - Promedio (~1 ACU): ~$88/mes
  - Pico (~2 ACU): ~$175/mes
- **Storage:** $0.10/GB-mes
- **Backup storage:** $0.021/GB-mes

**Total estimado:** $90-150/mes para carga baja/media

---

## 🛠️ Troubleshooting

### Lambda no puede conectar a RDS

**Síntomas:** `Timeout` o `Connection refused`

**Causas comunes:**
1. Lambda no está en subnets privadas de la VPC
2. Security group de Lambda no tiene egress en puerto 5432
3. Security group de RDS no permite ingress desde SG de Lambda

**Solución:**
```bash
# Verificar configuración VPC de Lambda
aws lambda get-function-configuration --function-name <nombre> --query VpcConfig

# Verificar security groups
aws ec2 describe-security-groups --group-ids <LambdaSG>
aws ec2 describe-security-groups --group-ids <RDSSG>
```

### Error "too many connections"

**Causa:** Lambdas están abriendo conexiones sin cerrarlas

**Solución:**
- Usa RDS Proxy (ya configurado)
- Asegúrate de cerrar conexiones en finally blocks
- Configura `max_overflow=0` en SQLAlchemy Engine

### Cold start alto (>3 segundos)

**Causa:** Lambda descargando Layer + estableciendo conexión DB

**Solución:**
- Usa Provisioned Concurrency (costo adicional)
- Mantén conexiones DB warm con keepalive queries
- Considera connection pooling en la Lambda (no en el handler)

---

## ⚠️ Patrones SQLite Detectados

Los siguientes archivos usan funciones SQLite que NO son compatibles con PostgreSQL:

