# Monolito PyME - Caso de Estudio de Migración Serverless

Proyecto de investigación de maestría: transformación automatizada de arquitecturas monolíticas a serverless usando IA.

## 📋 Descripción del Proyecto

Este repositorio contiene:

1. **Monolito Flask** (`/app`, `/seeds`, `/tests`) - Aplicación original de gestión de taller de reparaciones
2. **Versión Serverless** (`/serverless_taller`) - Transformación completa a AWS Lambda + API Gateway
3. **Gap Analysis** (`/serverless_taller/GAP_ANALYSIS.md`) - Análisis detallado de limitaciones de automatización

## 🏗️ Arquitecturas

### Monolito (Original)
- **Framework:** Flask 2.3.3 + Flask-SQLAlchemy
- **Base de datos:** SQLite (dev)
- **Autenticación:** Flask-JWT-Extended + Bcrypt
- **Estructura:** 5 blueprints (auth, clientes, servicios, transacciones, reportes)
- **Estado:** Caché en memoria, sesiones Flask, archivos en disco local

### Serverless (Transformado)
- **Compute:** AWS Lambda (5 funciones independientes)
- **API:** API Gateway REST
- **Base de datos:** RDS PostgreSQL
- **Caché:** ElastiCache Redis
- **Archivos:** S3 + presigned URLs
- **Notificaciones:** AWS SES
- **Auth:** JWT con revocación en DynamoDB

## 🚀 Quick Start

### Monolito Flask

```bash
# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Inicializar BD y poblar datos
flask init-db
flask seed

# 4. Ejecutar
python run.py
```

Credenciales de prueba:
- Admin: `admin@taller.com` / `admin123`
- Técnico: `juan.perez@taller.com` / `tecnico123`

### Serverless (Despliegue a AWS)

```bash
cd serverless_taller

# 1. Instalar Serverless Framework
npm install -g serverless
npm install --save-dev serverless-python-requirements

# 2. Configurar secretos en AWS SSM Parameter Store
aws ssm put-parameter --name /taller/dev/database_url --value "postgresql://..." --type SecureString
aws ssm put-parameter --name /taller/dev/jwt_secret --value "..." --type SecureString
aws ssm put-parameter --name /taller/dev/redis_url --value "redis://..." --type SecureString
aws ssm put-parameter --name /taller/dev/ses_sender --value "noreply@taller.com" --type String

# 3. Desplegar
serverless deploy --stage dev
```

**⚠️ Nota:** Requiere RDS PostgreSQL y ElastiCache Redis pre-existentes. Ver [GAP_ANALYSIS.md](serverless_taller/GAP_ANALYSIS.md) para detalles.

## 📊 Resultados del Análisis

### Automatización Alcanzada: ~62%

| Capa | % Automatizado |
|------|---------------|
| Modelos de datos | 95% |
| Lógica de negocio | 90% |
| Autenticación | 80% |
| Infraestructura | 50% |
| Tests | 0% |
| CI/CD | 0% |

### 14 Gaps Identificados

Los gaps críticos que requieren intervención humana:

1. **Upload de archivos** - Cambio de contrato de API (1 request → 2 requests con S3 presigned URLs)
2. **Migraciones de BD** - Flask-Migrate no existe en Lambda, requiere pipeline CI/CD
3. **Infraestructura stateful** - Sizing de RDS/Redis depende de información runtime

Ver análisis completo en [`serverless_taller/GAP_ANALYSIS.md`](serverless_taller/GAP_ANALYSIS.md)

## 📚 Casos de Uso del Dominio

El sistema gestiona un taller de reparaciones electrónicas:

- **Clientes** - Registro de personas que traen equipos a reparar
- **Servicios** - Catálogo de tipos de reparaciones con precios base
- **Órdenes de Trabajo** - Entidad transaccional central con estados:
  ```
  pendiente → en_diagnostico → en_reparacion → completado
                                              ↘ cancelado
  ```
- **Usuarios** - Técnicos y administradores del taller
- **Reportes** - KPIs de negocio (ingresos, rendimiento de técnicos, servicios más solicitados)

## 🔬 Objetivos de Investigación

Este proyecto es parte de un trabajo de grado de maestría que investiga:

1. ¿Hasta qué punto puede automatizarse la migración de monolitos a serverless con IA?
2. ¿Cuáles son las brechas sistemáticas que requieren intervención humana?
3. ¿Qué información de contexto adicional necesita la IA para mejorar la automatización?
4. ¿Cómo presentar tradeoffs arquitecturales para decisiones informadas?

## 📁 Estructura del Proyecto

```
monolito_pyme/
├── app/                        # Monolito Flask
│   ├── blueprints/
│   │   ├── auth/
│   │   ├── clientes/
│   │   ├── servicios/
│   │   ├── transacciones/
│   │   └── reportes/
│   ├── models/
│   ├── services/
│   └── utils/
├── serverless_taller/          # Versión serverless
│   ├── functions/              # 5 Lambda handlers
│   ├── shared/                 # Código compartido
│   ├── serverless.yml          # Infraestructura como código
│   └── GAP_ANALYSIS.md         # Análisis de gaps
├── seeds/                      # Datos de prueba
├── tests/                      # Suite de tests (monolito)
├── requirements.txt
└── run.py
```

## 🛠️ Tecnologías

**Monolito:**
- Flask 2.3.3, SQLAlchemy, Flask-Migrate
- JWT, Bcrypt, Marshmallow
- SQLite (dev), PostgreSQL (prod recomendado)

**Serverless:**
- AWS Lambda (Python 3.11)
- API Gateway, RDS PostgreSQL, ElastiCache Redis
- S3, SES, DynamoDB
- Serverless Framework

## 📖 Documentación Adicional

- [Endpoints del monolito](endpoints.md)
- [Ejemplos cURL](curl_examples.sh)
- [Gap Analysis completo](serverless_taller/GAP_ANALYSIS.md)
- [README serverless](serverless_taller/README.md)

## 🤝 Contribuciones

Este es un proyecto de investigación académica. Si encuentras bugs o tienes sugerencias
para mejorar el análisis de gaps, abre un issue.

## 📝 Licencia

MIT - Ver LICENSE para detalles

## ✍️ Autor

Trabajo de Grado de Maestría - 2026

---

**Para citar este trabajo:**
```
[Pendiente de publicación]
```
