---
name: "persistence-migrator"
version: "1.0.0"
description: "Genera la infraestructura de persistencia serverless (RDS Aurora Serverless v2, VPC, RDS Proxy) y adapta los modelos SQLAlchemy del monolito a PostgreSQL, consumiendo el migration-manifest.json del Skill 01."
author: "Luis Gerardo Sánchez Ordóñez"
tags: ["aws", "serverless", "rds", "aurora", "postgresql", "vpc", "rds-proxy", "persistence"]
triggers:
  - "migrar persistencia"
  - "generar base de datos"
  - "crear RDS"
  - "migrar a PostgreSQL"
  - "configurar VPC"
  - "migrate persistence"
  - "generate database"
---

# Skill 02 — Migrador de Persistencia

## Cuándo activar este Skill

Activa este Skill cuando el desarrollador necesite alguna de las siguientes acciones:

- Generar la infraestructura de base de datos serverless (RDS Aurora Serverless v2) para el monolito migrado
- Crear la configuración de red (VPC, subnets públicas/privadas, security groups, NAT Gateway)
- Configurar RDS Proxy para gestión eficiente de conexiones desde Lambda
- Adaptar modelos SQLAlchemy de SQLite a PostgreSQL
- Resolver el anti-patrón **AP-strftime-sqlite** (funciones SQLite no portables)
- Generar scripts de migración de esquema con Alembic
- Configurar parámetros de conexión en SSM Parameter Store

**Palabras clave que activan este Skill:** "persistencia", "base de datos", "RDS", "Aurora", "PostgreSQL", "VPC", "RDS Proxy", "migración de esquema", "SQLAlchemy", "database migration"

---

## Instrucciones para el agente

Sigue estos pasos en orden cuando se active el Skill:

### Paso 1 — Validar prerrequisitos

Verifica que existen los siguientes archivos:

1. **migration-manifest.json** — Generado por Skill 01, ubicado en el directorio raíz del monolito
2. **app/models/** — Directorio con los modelos SQLAlchemy del monolito
3. **requirements.txt** — Para detectar la versión de SQLAlchemy y dependencias

Si alguno falta, informa al usuario:
```
⚠️ Prerrequisito faltante: <archivo>
Este Skill requiere que ejecutes primero el Skill 01 (Analizador de Monolito).
```

### Paso 2 — Ejecutar el generador de infraestructura

Ejecuta el script desde la raíz del workspace:

```bash
python skills/skill-02-persistence/scripts/generate_persistence.py --manifest <ruta_manifest> --monolith <ruta_monolito>
```

Parámetros opcionales:
- `--output <directorio>`: Directorio de salida para los templates generados (default: `./serverless-output/persistence/`)
- `--db-name <nombre>`: Nombre de la base de datos (default: extraído del manifest o `taller_db`)
- `--vpc-cidr <cidr>`: CIDR para la VPC (default: `10.0.0.0/16`)

El script generará:
1. **template-vpc.yaml** — VPC + subnets + NAT Gateway + security groups
2. **template-rds.yaml** — RDS Aurora Serverless v2 cluster + RDS Proxy
3. **db-layer/** — Lambda Layer con SQLAlchemy + psycopg2 + modelos adaptados
4. **alembic/** — Scripts de migración de esquema
5. **config-ssm.yaml** — Parámetros de conexión para SSM Parameter Store
6. **DEPLOYMENT_GUIDE.md** — Guía paso a paso para desplegar la infraestructura

### Paso 3 — Presentar el resumen al desarrollador

Presenta la siguiente información de forma estructurada:

1. **Infraestructura generada:**
   - VPC con CIDR `<cidr>`
   - 2 subnets públicas (AZs: us-east-1a, us-east-1b)
   - 2 subnets privadas (AZs: us-east-1a, us-east-1b)
   - NAT Gateway en subnet pública (para acceso a internet desde Lambdas)
   - Security Group para RDS (puerto 5432, tráfico interno VPC)
   - Security Group para Lambdas (tráfico saliente permitido)

2. **Base de datos:**
   - Motor: Aurora PostgreSQL Serverless v2
   - Versión: PostgreSQL 15.x compatible
   - Capacidad mínima: 0.5 ACU (Aurora Capacity Units)
   - Capacidad máxima: 2 ACU
   - Autoscaling: Activado
   - Multi-AZ: Sí (alta disponibilidad)
   - Backup automático: 7 días de retención
   - Cifrado en reposo: Activado (AWS KMS)

3. **RDS Proxy:**
   - Connection pooling: Activado
   - Máximo de conexiones: 100
   - Idle timeout: 1800 segundos
   - Secretos en AWS Secrets Manager

4. **Modelos adaptados:**
   - Total de modelos migrados: `<N>`
   - Funciones SQLite reemplazadas: `<lista>`
   - Tipos de datos convertidos: SQLite → PostgreSQL

5. **Lambda Layer generada:**
   - Nombre: `db-layer`
   - Contenido: SQLAlchemy + psycopg2-binary + modelos adaptados
   - Tamaño estimado: ~15 MB
   - Compatible con: Python 3.11 runtime

### Paso 4 — Guiar el despliegue

Informa al usuario sobre los siguientes pasos:

```markdown
## 📦 Archivos generados

Todos los archivos se encuentran en: `<output_dir>/`

## 🚀 Cómo desplegar la infraestructura

### Opción A: Despliegue automático con AWS SAM

\`\`\`bash
cd <output_dir>
sam build
sam deploy --guided
\`\`\`

### Opción B: Despliegue manual

1. **Desplegar VPC (primero):**
   \`\`\`bash
   aws cloudformation deploy \
     --template-file template-vpc.yaml \
     --stack-name taller-vpc \
     --capabilities CAPABILITY_IAM
   \`\`\`

2. **Desplegar RDS (después de VPC):**
   \`\`\`bash
   aws cloudformation deploy \
     --template-file template-rds.yaml \
     --stack-name taller-rds \
     --capabilities CAPABILITY_IAM \
     --parameter-overrides VPCStackName=taller-vpc
   \`\`\`

3. **Subir Lambda Layer:**
   \`\`\`bash
   cd db-layer
   zip -r db-layer.zip .
   aws lambda publish-layer-version \
     --layer-name taller-db-layer \
     --zip-file fileb://db-layer.zip \
     --compatible-runtimes python3.11
   \`\`\`

4. **Almacenar parámetros en SSM:**
   \`\`\`bash
   aws cloudformation deploy \
     --template-file config-ssm.yaml \
     --stack-name taller-config
   \`\`\`

## ⚙️ Configuración de variables de entorno

Las Lambdas deben incluir estas variables de entorno:

\`\`\`yaml
Environment:
  Variables:
    DB_HOST: !GetAtt RDSProxy.Endpoint
    DB_PORT: 5432
    DB_NAME: taller_db
    DB_SECRET_ARN: !Ref DBSecret
    DB_PROXY_ENDPOINT: !GetAtt RDSProxy.Endpoint
\`\`\`

## 🧪 Validar la conexión

Usa la Lambda de prueba generada:

\`\`\`bash
cd <output_dir>/test
python test_connection.py
\`\`\`

## 📚 Documentación adicional

Consulta `DEPLOYMENT_GUIDE.md` para:
- Cálculo de costos estimados (RDS Proxy: ~$20/mes, Aurora: pay-per-use)
- Troubleshooting de conexión
- Cómo ejecutar las migraciones Alembic
- Cómo poblar datos iniciales (seeds)
```

---

## Prerrequisitos

- Python 3.9 o superior instalado en el sistema
- AWS CLI configurado con credenciales válidas (para validar templates con `aws cloudformation validate-template`)
- El monolito Flask debe estar accesible en el sistema de archivos local
- **migration-manifest.json** generado por Skill 01
- No se requieren dependencias externas para el generador — usa únicamente módulos de la biblioteca estándar de Python

---

## Output generado

### Estructura de directorios

```
<output_dir>/
├── template-vpc.yaml              # CloudFormation: VPC + networking
├── template-rds.yaml              # CloudFormation: Aurora + RDS Proxy
├── config-ssm.yaml                # CloudFormation: SSM Parameter Store
├── db-layer/                      # Lambda Layer con modelos adaptados
│   ├── python/
│   │   ├── sqlalchemy/           # SQLAlchemy 2.x
│   │   ├── psycopg2/             # Driver PostgreSQL
│   │   └── app/
│   │       └── models/           # Modelos adaptados (SQLite → PostgreSQL)
│   └── requirements.txt
├── alembic/                       # Migraciones de esquema
│   ├── versions/
│   │   └── 001_initial_schema.py
│   ├── env.py
│   └── alembic.ini
├── test/
│   └── test_connection.py         # Lambda de prueba de conexión
├── DEPLOYMENT_GUIDE.md            # Guía de despliegue paso a paso
└── MIGRATION_NOTES.md             # Notas sobre adaptaciones SQLite → PostgreSQL
```

---

## Características técnicas

### Resolución de anti-patrones

#### AP-strftime-sqlite
**Problema:** Funciones SQLite como `strftime('%Y-%m', fecha)` no existen en PostgreSQL.

**Solución aplicada:**
```python
# SQLite (monolito):
query = db.session.query(
    func.strftime('%Y-%m', OrdenTrabajo.fecha_ingreso).label('mes'),
    func.count(OrdenTrabajo.id)
)

# PostgreSQL (serverless):
query = db.session.query(
    func.to_char(OrdenTrabajo.fecha_ingreso, 'YYYY-MM').label('mes'),
    func.count(OrdenTrabajo.id)
)
```

El Skill detecta automáticamente estos patrones en los blueprints y genera versiones adaptadas en `db-layer/app/`.

### Optimizaciones aplicadas

1. **RDS Proxy Connection Pooling:**
   - Gestiona hasta 100 conexiones concurrentes
   - Reutiliza conexiones entre invocaciones Lambda
   - Reduce cold start de conexión DB (de ~3s a ~200ms)

2. **Lambda Layer compartida:**
   - Evita empaquetar SQLAlchemy en cada Lambda (ahorro de ~10 MB por función)
   - Modelos centralizados: cambios en el esquema se propagan desde un solo lugar

3. **Secrets Manager para credenciales:**
   - Password de RDS nunca en variables de entorno
   - Rotación automática de credenciales (configurable)

4. **Cifrado en reposo y en tránsito:**
   - RDS: cifrado con AWS KMS
   - Conexiones: SSL/TLS forzado

---

## Integración con otros Skills

### Consume desde Skill 01:
- `migration-manifest.json`: metadata de módulos y endpoints
- `summary.anti_pattern_summary`: detección de AP-strftime-sqlite
- `lambda_layers`: recomendación de db-layer

### Produce para Skill 03:
- `VPCId`: ID de la VPC creada (para API Gateway VPC Link)
- `SubnetIds`: IDs de subnets privadas (para desplegar Lambdas)
- `SecurityGroupId`: ID del security group de Lambdas
- `DBProxyEndpoint`: Endpoint de RDS Proxy (para configurar en Lambdas)
- `DBSecretArn`: ARN del secreto con credenciales (para IAM policies)

### Produce para Skills 04-05:
- Lambda Layer `db-layer` lista para referenciar en templates SAM

---

## Limitaciones conocidas

1. **No migra datos automáticamente**: El Skill genera los scripts de migración de esquema pero NO migra los datos de SQLite a PostgreSQL. El desarrollador debe ejecutar un script de ETL manualmente.

2. **No soporta múltiples bases de datos**: Si el monolito usa múltiples DBs (ej: SQLite principal + Redis), solo migra la DB relacional principal.

3. **Asume PostgreSQL 15**: Si el monolito tiene dependencias de versiones específicas de SQLite (ej: JSON1 extension), puede requerir ajustes manuales.

4. **Costos de RDS Proxy**: RDS Proxy tiene un costo fijo de ~$0.015/hora (~$11/mes). Para monolitos con <100 req/min podría ser más económico conectar directamente a Aurora (requiere configurar `max_connections` más alto).

---

## Troubleshooting

### Error: "Template validation failed"
**Causa:** AWS CLI no configurado o sin permisos.
**Solución:** Ejecuta `aws configure` y valida credenciales.

### Error: "Subnet CIDR overlaps"
**Causa:** La VPC CIDR especificada colisiona con otra VPC existente.
**Solución:** Usa `--vpc-cidr` con un rango diferente (ej: `10.1.0.0/16`).

### Error: "DB connection timeout"
**Causa:** Lambda no puede alcanzar RDS Proxy.
**Solución:** Verifica que:
1. Lambda está en subnets privadas de la VPC
2. Security group de Lambda permite tráfico saliente a puerto 5432
3. Security group de RDS permite tráfico entrante desde security group de Lambda

---

## Referencias

- [AWS RDS Aurora Serverless v2 Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html)
- [AWS RDS Proxy Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html)
- [SQLAlchemy PostgreSQL Dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [Alembic Migrations](https://alembic.sqlalchemy.org/en/latest/)

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software  
**Institución:** Pontificia Universidad Javeriana Cali  
**Director:** Juan Gabriel Quintero Barbosa — Head Solutions Architecture, AWS Colombia
