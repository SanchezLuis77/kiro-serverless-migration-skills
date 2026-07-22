# Taller PyME — Versión Serverless (AWS Lambda + API Gateway)

Transformación del monolito Flask a arquitectura serverless usando AWS Lambda,
API Gateway, RDS (PostgreSQL), ElastiCache (Redis), S3 y SNS/SES.

## 🏗️ Arquitectura

```
Cliente HTTP
     │
     ▼
API Gateway (REST API)
     │
     ├── /auth/*         → Lambda: auth_handler
     ├── /clientes/*     → Lambda: clientes_handler
     ├── /servicios/*    → Lambda: servicios_handler
     ├── /transacciones/*→ Lambda: transacciones_handler
     └── /reportes/*     → Lambda: reportes_handler
           │
           ├── RDS PostgreSQL (datos persistentes)
           ├── ElastiCache Redis (caché distribuido)
           ├── S3 (archivos adjuntos)
           └── SES (notificaciones email)
```

## 📁 Estructura del Proyecto

```
serverless_taller/
├── shared/                    # Código compartido entre funciones
│   ├── db.py                  # Conexión RDS con connection pooling
│   ├── models.py              # Modelos SQLAlchemy (sin Flask)
│   ├── auth_utils.py          # Validación JWT sin Flask-JWT-Extended
│   ├── response.py            # Helpers de respuesta HTTP para Lambda
│   ├── cache.py               # Cliente Redis para ElastiCache
│   └── notificaciones.py      # Cliente SES para emails
├── functions/                 # Handlers Lambda (1 por módulo)
│   ├── auth/handler.py
│   ├── clientes/handler.py
│   ├── servicios/handler.py
│   ├── transacciones/handler.py
│   └── reportes/handler.py
├── serverless.yml             # Infraestructura como código
├── requirements.txt           # Dependencias Python
├── GAP_ANALYSIS.md            # Análisis de limitaciones
└── .env.example               # Template de configuración
```

## 🚀 Despliegue

### Prerequisitos

1. **Cuenta AWS** con permisos de IAM para Lambda, API Gateway, S3, DynamoDB
2. **Node.js** (para Serverless Framework)
3. **Python 3.11**
4. **AWS CLI** configurado (`aws configure`)

### Paso 1: Instalar Serverless Framework

```bash
npm install -g serverless
npm install --save-dev serverless-python-requirements
```

### Paso 2: Crear Infraestructura Stateful (MANUAL)

⚠️ **GAP CRÍTICO:** RDS y ElastiCache **no se crean automáticamente**. Debes crearlos antes del deploy.

#### Opción A: Via AWS Console
1. RDS PostgreSQL (o Aurora Serverless v2)
   - Motor: PostgreSQL 14+
   - Instancia: db.t3.micro (dev) / db.t3.medium (prod)
   - Habilitar acceso desde Lambda (security group)
2. ElastiCache Redis
   - Motor: Redis 7.x
   - Nodo: cache.t3.micro (dev)
   - Habilitar acceso desde Lambda (security group)

#### Opción B: Via Terraform/CDK (recomendado para producción)
```hcl
# Ejemplo Terraform (no incluido)
resource "aws_db_instance" "taller" {
  engine         = "postgres"
  instance_class = "db.t3.micro"
  # ... resto de configuración
}
```

### Paso 3: Configurar Secretos en AWS Systems Manager

```bash
# Database
aws ssm put-parameter \
  --name /taller/dev/database_url \
  --value "postgresql://usuario:password@host.rds.amazonaws.com:5432/taller_db" \
  --type SecureString

# JWT Secret
aws ssm put-parameter \
  --name /taller/dev/jwt_secret \
  --value "$(openssl rand -hex 32)" \
  --type SecureString

# Redis
aws ssm put-parameter \
  --name /taller/dev/redis_url \
  --value "redis://taller-cache.xxxxx.cache.amazonaws.com:6379" \
  --type SecureString

# SES Sender (verificar email en SES primero)
aws ssm put-parameter \
  --name /taller/dev/ses_sender \
  --value "noreply@taller.com" \
  --type String
```

### Paso 4: Verificar Email en SES

```bash
aws ses verify-email-identity --email-address noreply@taller.com
# Verificar el email en la bandeja de entrada del remitente
```

### Paso 5: Desplegar

```bash
cd serverless_taller
serverless deploy --stage dev --region us-east-1
```

**Salida esperada:**
```
Service Information
service: taller-pyme-serverless
stage: dev
region: us-east-1
stack: taller-pyme-serverless-dev
endpoints:
  POST - https://abc123xyz.execute-api.us-east-1.amazonaws.com/dev/auth/login
  GET  - https://abc123xyz.execute-api.us-east-1.amazonaws.com/dev/clientes
  ...
functions:
  auth: taller-pyme-serverless-dev-auth
  clientes: taller-pyme-serverless-dev-clientes
  ...
```

### Paso 6: Ejecutar Migraciones (MANUAL)

⚠️ **GAP:** No hay equivalente a `flask db migrate` en Lambda.

**Opción A:** Desde una instancia EC2 con acceso a la VPC de RDS
```bash
# En EC2 dentro de la VPC
pip install alembic
alembic init migrations
# ... configurar alembic.ini con DATABASE_URL de RDS
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

**Opción B:** Crear Lambda de administración (no incluida)
```python
# Función Lambda separada que ejecuta:
from shared.db import Base, get_engine
Base.metadata.create_all(get_engine())
```

### Paso 7: Poblar Datos de Prueba

```bash
# Ejecutar script de seed (no generado — adaptar desde monolito)
python scripts/seed_rds.py
```

## 🧪 Probar la API

```bash
# Login
curl -X POST https://abc123xyz.execute-api.us-east-1.amazonaws.com/dev/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@taller.com","password":"admin123"}'

# Guardar token
export TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

# Listar clientes
curl https://abc123xyz.execute-api.us-east-1.amazonaws.com/dev/clientes \
  -H "Authorization: Bearer $TOKEN"
```

## 🔍 Monitoreo

### Ver logs
```bash
serverless logs -f auth --tail
serverless logs -f transacciones --tail --stage dev
```

### CloudWatch Dashboards (no generado automáticamente)
Crear dashboard con métricas:
- Invocations, Duration, Errors por función
- API Gateway 4xx/5xx rate
- RDS CPU/Connections
- Redis cache hit rate

## 🚧 Gaps Conocidos (Ver GAP_ANALYSIS.md)

### Críticos
1. **Upload de archivos** — Usa presigned URLs de S3 (2 requests en lugar de 1)
2. **Migraciones de BD** — Requiere proceso manual o Lambda de admin
3. **VPC para Redis** — Aumenta cold start ~500ms, debe configurarse manualmente

### Medios
4. **Tests** — No hay suite de tests equivalente al monolito
5. **Desarrollo local** — Requiere `serverless-offline` (no configurado)
6. **Observabilidad** — Solo logging básico, sin X-Ray ni alarmas CloudWatch

## 📊 Diferencias vs Monolito

| Aspecto | Monolito | Serverless |
|---------|----------|-----------|
| Base de datos | SQLite (dev) | RDS PostgreSQL |
| Caché | dict en memoria | ElastiCache Redis |
| Archivos | Filesystem local | S3 + presigned URLs |
| Notificaciones | Simuladas (logs) | AWS SES (emails reales) |
| Sesión Flask | session[] en memoria | No existe (solo JWT) |
| Routing | Decoradores `@bp.route()` | if/elif manual (GAP-01) |
| JWT revocado | set en memoria | DynamoDB con TTL |
| Migraciones | `flask db migrate` | Manual (GAP-05) |

## 🛠️ Desarrollo Local (Limitado)

```bash
# Instalar plugin (no configurado en serverless.yml)
npm install --save-dev serverless-offline

# Agregar a serverless.yml:
# plugins:
#   - serverless-offline

# Ejecutar localmente
serverless offline --stage dev

# Requiere:
# - PostgreSQL local o túnel SSH a RDS
# - Redis local o túnel SSH a ElastiCache
# - LocalStack para simular S3/SES/DynamoDB
```

## 📝 Despliegue Continuo (Recomendado)

```yaml
# .github/workflows/deploy.yml (no incluido)
name: Deploy to AWS
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to AWS
        run: |
          npm install -g serverless
          cd serverless_taller
          serverless deploy --stage prod
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## 🔐 Seguridad

- **CORS:** Por defecto `Access-Control-Allow-Origin: *` — RESTRINGIR en producción
- **API Keys:** No configuradas — agregar usage plan en API Gateway
- **WAF:** No configurado — agregar reglas básicas en producción
- **Secrets:** Usar AWS Secrets Manager con rotación automática (no SSM)
- **IAM:** Aplicar principio de least privilege por función

## 💰 Costos Estimados (us-east-1)

| Recurso | Configuración | Costo mensual (aprox) |
|---------|--------------|----------------------|
| Lambda | 5 funciones, 1M requests/mes | $5 |
| API Gateway | 1M requests/mes | $3.50 |
| RDS db.t3.micro | Single-AZ, 20GB | $15 |
| ElastiCache cache.t3.micro | Single-node | $12 |
| S3 | 10GB storage, 1K requests | $0.30 |
| DynamoDB | On-demand, 1K writes | $1 |
| **TOTAL** | | **~$37/mes** |

Tráfico bajo. Con 10M requests/mes: ~$120/mes.

## 🐛 Troubleshooting

### "Token inválido" en todos los endpoints
- Verificar que `JWT_SECRET_KEY` sea el mismo en auth y otras funciones
- Verificar formato del header: `Authorization: Bearer <token>` (con espacio)

### Cold start >3 segundos
- Lambda en VPC agrega ~500ms
- Primera invocación incluye carga de dependencias (~1.5s)
- Usar Lambda Layers para dependencias reduce tamaño del deployment

### "Cannot connect to database"
- Verificar security group de RDS permite conexiones desde Lambda
- Verificar que Lambda esté en la misma VPC que RDS
- Verificar DATABASE_URL en SSM Parameter Store

### "Redis connection timeout"
- ElastiCache solo es accesible desde VPC
- Descomentar sección `vpc:` en serverless.yml
- Verificar security group de ElastiCache

## 🔄 Rollback

```bash
# Ver deployments
serverless deploy list

# Rollback al anterior
serverless rollback --timestamp <timestamp>
```

## 🗑️ Eliminar Stack

```bash
serverless remove --stage dev
```

⚠️ **Esto NO elimina RDS ni ElastiCache** (stateful resources).

---

**Más información:** Ver [GAP_ANALYSIS.md](GAP_ANALYSIS.md) para análisis detallado de limitaciones.
