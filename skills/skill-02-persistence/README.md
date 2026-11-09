# Skill 02 — Migrador de Persistencia

**Estado:** ✅ Implementación completa  
**Versión:** 1.0.0  
**Autor:** Luis Gerardo Sánchez Ordóñez

---

## 🎯 Propósito

Genera automáticamente la infraestructura de persistencia serverless para migrar aplicaciones Flask con SQLite a RDS Aurora Serverless v2 con PostgreSQL, incluyendo toda la configuración de red (VPC, subnets, NAT Gateway, security groups) y RDS Proxy para gestión eficiente de conexiones desde Lambda.

---

## ✨ Características

### Infraestructura Generada

- ✅ **VPC completa** con subnets públicas/privadas en multi-AZ
- ✅ **NAT Gateway** para acceso a internet desde Lambdas
- ✅ **Security Groups** configurados para Lambda → RDS
- ✅ **RDS Aurora Serverless v2** con escalado automático (0.5-2 ACU)
- ✅ **RDS Proxy** con connection pooling (hasta 100 conexiones)
- ✅ **Secrets Manager** para credenciales seguras
- ✅ **Cifrado** en reposo (KMS) y en tránsito (SSL/TLS)
- ✅ **Backup automático** con 7 días de retención

### Análisis de Código

- ✅ **Detección automática** de modelos SQLAlchemy
- ✅ **Identificación de funciones SQLite** no portables (strftime, datetime, julianday)
- ✅ **Recomendaciones** de reemplazo para PostgreSQL

---

## 🚀 Uso Rápido

### Prerrequisitos

1. Ejecutar **Skill 01** primero (genera `migration-manifest.json`)
2. AWS CLI configurado con credenciales válidas
3. Python 3.9+

### Ejecución

```bash
# Básico
python skills/skill-02-persistence/scripts/generate_persistence.py \
  --manifest monolith/migration-manifest.json \
  --monolith monolith/

# Con opciones personalizadas
python skills/skill-02-persistence/scripts/generate_persistence.py \
  --manifest monolith/migration-manifest.json \
  --monolith monolith/ \
  --output ./mi-infra \
  --db-name mi_database \
  --vpc-cidr 10.1.0.0/16
```

### Output

```
serverless-output/persistence/
├── template-vpc.yaml          # VPC + networking
├── template-rds.yaml          # Aurora + RDS Proxy
└── DEPLOYMENT_GUIDE.md        # Guía de despliegue
```

---

## 📦 Despliegue

### Opción 1: AWS CLI (recomendado)

```bash
cd serverless-output/persistence

# 1. Desplegar VPC (3-5 min)
aws cloudformation deploy \
  --template-file template-vpc.yaml \
  --stack-name taller-vpc \
  --capabilities CAPABILITY_IAM

# 2. Desplegar RDS (10-15 min)
aws cloudformation deploy \
  --template-file template-rds.yaml \
  --stack-name taller-rds \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      DBPassword=TU_PASSWORD_SEGURA
```

### Opción 2: AWS Console

1. Ir a CloudFormation → Create Stack
2. Subir `template-vpc.yaml` → Create
3. Esperar a que termine (Status: CREATE_COMPLETE)
4. Subir `template-rds.yaml` → Ingresar DBPassword → Create

---

## 🔧 Configuración de Lambdas

Cada Lambda que use la base de datos debe tener:

### Variables de entorno

```yaml
Environment:
  Variables:
    DB_PROXY_ENDPOINT: <output-de-cloudformation>
    DB_NAME: taller_db
    DB_SECRET_ARN: <output-de-cloudformation>
    DB_PORT: '5432'
```

### VPC Config

```yaml
VpcConfig:
  SecurityGroupIds:
    - Fn::ImportValue: taller-LambdaSG
  SubnetIds:
    - Fn::ImportValue: taller-PrivateSubnet1
    - Fn::ImportValue: taller-PrivateSubnet2
```

### IAM Permissions

```yaml
Policies:
  - Statement:
      - Effect: Allow
        Action:
          - secretsmanager:GetSecretValue
        Resource: !ImportValue taller-DBSecretArn
      - Effect: Allow
        Action:
          - ec2:CreateNetworkInterface
          - ec2:DescribeNetworkInterfaces
          - ec2:DeleteNetworkInterface
        Resource: '*'
```

---

## 💰 Costos Estimados (us-east-1)

| Recurso | Costo | Tipo |
|---------|-------|------|
| RDS Proxy | ~$11/mes | Fijo |
| NAT Gateway | ~$33/mes | Fijo |
| Aurora Serverless v2 (promedio 1 ACU) | ~$88/mes | Variable |
| Storage (primeros 10 GB) | ~$1/mes | Variable |
| **Total estimado** | **~$130-150/mes** | |

💡 **Tip:** Aurora escala a 0.5 ACU mínimo, por lo que en períodos de baja actividad el costo puede reducirse a ~$90/mes.

---

## 🧪 Testing

### Test de conexión desde Python

```python
import psycopg2
import boto3
import json

def test_db_connection():
    # Obtener credenciales de Secrets Manager
    sm = boto3.client('secretsmanager')
    secret = sm.get_secret_value(SecretId='<DBSecretArn>')
    creds = json.loads(secret['SecretString'])
    
    # Conectar a RDS Proxy
    conn = psycopg2.connect(
        host='<DBProxyEndpoint>',
        port=5432,
        database='taller_db',
        user=creds['username'],
        password=creds['password'],
        sslmode='require'
    )
    
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print(f"✅ Conexión exitosa: {cur.fetchone()[0]}")
    conn.close()

if __name__ == "__main__":
    test_db_connection()
```

---

## 🔍 Anti-Patrones Resueltos

### AP-strftime-sqlite

**Problema:** SQLite usa `strftime('%Y-%m', fecha)` que NO existe en PostgreSQL.

**Solución automática:**

| SQLite | PostgreSQL |
|--------|------------|
| `strftime('%Y-%m', col)` | `to_char(col, 'YYYY-MM')` |
| `strftime('%Y', col)` | `EXTRACT(YEAR FROM col)` |
| `datetime('now')` | `NOW()` |
| `julianday(col)` | `EXTRACT(EPOCH FROM col) / 86400` |

El script **detecta automáticamente** estos patrones y los reporta en el output.

---

## 📊 Arquitectura Generada

```
┌─────────────────────────────────────────┐
│              VPC (10.0.0.0/16)          │
│                                         │
│  ┌─────────────┐      ┌─────────────┐  │
│  │ Public AZ-a │      │ Public AZ-b │  │
│  │ 10.0.1.0/24 │      │ 10.0.2.0/24 │  │
│  └──────┬──────┘      └─────────────┘  │
│         │ NAT Gateway                   │
│         ▼                               │
│  ┌─────────────┐      ┌─────────────┐  │
│  │Private AZ-a │      │Private AZ-b │  │
│  │ 10.0.11/24  │      │ 10.0.12/24  │  │
│  │             │      │             │  │
│  │  ┌────┐     │      │     ┌────┐  │  │
│  │  │λλλ │◄────┼──────┼────►│RDS │  │  │
│  │  └────┘     │      │     │ ┌──┤  │  │
│  │             │      │     │ │  │  │  │
│  └─────────────┘      └─────┼─┴──┼──┘  │
│                              │ Aurora   │
│                              └──────┘   │
└─────────────────────────────────────────┘
         │
         ▼
    RDS Proxy (connection pooling)
```

---

## 🛠️ Troubleshooting

### Lambda timeout al conectar a RDS

**Causa:** Lambda no está en las subnets privadas de la VPC.

**Solución:** Verificar `VpcConfig.SubnetIds` apunta a subnets privadas.

### "too many connections"

**Causa:** Lambdas no cierran conexiones correctamente.

**Solución:**
1. Usar RDS Proxy (ya incluido)
2. En código Python:
   ```python
   try:
       conn = get_connection()
       # ... queries
   finally:
       conn.close()
   ```

### Cold start muy alto (>5s)

**Causa:** Lambda descargando dependencias + estableciendo conexión.

**Solución:**
- Usar Provisioned Concurrency (costo adicional)
- Implementar connection pooling a nivel de Lambda
- Considerar migration a Fargate si cold start es crítico

---

## 📚 Integración con Otros Skills

### ⬅️ Consume desde Skill 01:
- `migration-manifest.json` (metadata de módulos)
- Directorio de modelos SQLAlchemy

### ➡️ Produce para Skill 03:
- VPCId, SubnetIds, SecurityGroupIds (para API Gateway VPC Link)
- DBProxyEndpoint (para configurar en Lambdas)
- DBSecretArn (para IAM policies)

### ➡️ Produce para Skills 04-05:
- Infraestructura base para desplegar Lambdas en VPC

---

## 📖 Referencias

- [AWS RDS Aurora Serverless v2](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html)
- [AWS RDS Proxy](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html)
- [Lambda VPC Configuration](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html)
- [PostgreSQL vs SQLite](https://www.postgresql.org/docs/current/index.html)

---

## ✅ Checklist de Validación

Antes de pasar al Skill 03, verifica:

- [ ] Stack `taller-vpc` desplegado exitosamente
- [ ] Stack `taller-rds` desplegado exitosamente
- [ ] RDS Proxy endpoint obtenido
- [ ] Test de conexión exitoso desde Lambda local
- [ ] Modelos SQLAlchemy adaptados si hay funciones SQLite

---

**Siguiente Skill:** [Skill 03 — Orquestador Strangler Fig](../skill-03-strangler/)

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Institución:** Pontificia Universidad Javeriana Cali  
**Director:** Juan Gabriel Quintero Barbosa (AWS Solutions Architecture)  
**Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software
