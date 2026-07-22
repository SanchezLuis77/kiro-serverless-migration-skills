# Guía de Desarrollo de Agent Skills

## Estándar Agent Skills

Cada Skill sigue el estándar abierto agentskills.io y se estructura así:

```
skills/skill-XX-nombre/
├── SKILL.md          # Instrucciones del Skill (metadatos YAML + Markdown)
├── scripts/          # Scripts Python de análisis estático (AST)
├── templates/        # Plantillas IaC AWS SAM (.yaml)
└── README.md         # Documentación de uso
```

### Formato SKILL.md obligatorio

```yaml
---
name: "nombre-del-skill"
version: "1.0.0"
description: "Descripción concisa"
author: "Luis Gerardo Sánchez Ordóñez"
tags: ["aws", "serverless", "migration", "flask"]
triggers:
  - "migrar"
  - "serverless"
  - "lambda"
---

# [Nombre del Skill]

## Cuándo activar este Skill
...

## Instrucciones para el agente
...
```

## Los 5 Skills — Responsabilidades y Gaps que Cierran

### Skill 1: Analizador de Monolito (`skill-01-analyzer`)
- **Gaps que cierra:** Base para todos los demás
- **Input:** Código fuente del monolito Flask
- **Output:** `migration-manifest.json` con:
  - Lista de endpoints con recomendación (Lambda / Fargate / App Runner)
  - Anti-patrones detectados por AST
  - Criterios de decisión: duración estimada, patrón de invocación, estado requerido
- **Script principal:** `scripts/analyze_monolith.py` (análisis AST con `ast` module)
- **Criterios de decisión Lambda vs Fargate vs App Runner:**
  - Lambda: duración < 15min, sin estado, orientado a eventos
  - Fargate: larga duración, estado temporal, procesamiento batch
  - App Runner: tráfico HTTP continuo, latencia consistente requerida

### Skill 2: Migrador de Persistencia (`skill-02-persistence`)
- **Gaps que cierra:** GAP-04, GAP-05, GAP-07
- **Input:** `migration-manifest.json` + modelos SQLAlchemy del monolito
- **Output:**
  - Template SAM con RDS Aurora Serverless v2, VPC, subnets, security groups, RDS Proxy
  - Script Alembic standalone para migraciones (reemplaza Flask-Migrate)
  - Adaptaciones ORM: `strftime` → `func.to_char()` para PostgreSQL
  - Lambda de inicialización de BD
- **Template principal:** `templates/rds-infrastructure.yaml`

### Skill 3: Orquestador Strangler Fig (`skill-03-strangler`)
- **Gaps que cierra:** GAP-01, GAP-03, GAP-06, GAP-08
- **Input:** `migration-manifest.json` + configuración JWT del monolito
- **Output:**
  - Template SAM con API Gateway + Lambda Authorizer compartido
  - Configuración de coexistencia monolito-Lambda (routing por módulo)
  - Solución JWT compatible: tokens generados por monolito válidos en Lambda
  - DynamoDB para blacklist de tokens (reemplaza `set()` en memoria) — fail-closed
  - Configuración CORS parametrizable
- **Patrón:** `aws-lambda-powertools Router` para reemplazar routing if/elif

### Skill 4: Migrador de Uploads (`skill-04-uploads`)
- **Gaps que cierra:** GAP-02
- **Input:** Endpoints con `multipart/form-data` detectados por Skill 1
- **Output:**
  - Endpoint de generación de presigned URL (paso 1)
  - Lambda de confirmación post-upload (paso 2)
  - Template SAM con S3 bucket + políticas
  - Guía de migración del cliente/frontend (breaking change documentado)
- **Estrategias evaluadas:** presigned URL vs CloudFront vs Transfer Acceleration

### Skill 5: Validador Post-Generación (`skill-05-validator`)
- **Gaps que cierra:** GAP-09, GAP-10, GAP-11, GAP-12, GAP-13
- **Input:** Output completo generado por Kiro (directorio serverless)
- **Output:**
  - Reporte de completitud: checklist de todos los gaps conocidos
  - Template CloudWatch: dashboards + alarmas por Lambda
  - Configuración X-Ray tracing
  - Skeleton de tests con `moto` para cada Lambda
  - Configuración `serverless-offline` para desarrollo local
  - Script de seed standalone (reemplaza `flask seed`)
  - Proceso de creación de secretos en SSM Parameter Store

## Principios de Diseño de los Skills

1. **Privacy by design:** Los scripts AST operan exclusivamente en memoria local, sin transmitir código fuente a servicios externos
2. **IaC con AWS SAM exclusivamente** (no CDK, no Terraform, no Serverless Framework)
3. **Parámetros configurables:** Todos los templates SAM usan `Parameters` para valores de cuenta/región
4. **Mínimo privilegio por defecto:** Roles IAM con permisos mínimos necesarios
5. **Well-Architected Framework:** Las plantillas siguen los 6 pilares de AWS WAF
6. **Output siempre desplegable:** El objetivo es >80% de tasa de deploy exitoso en primer intento

## Orden de Construcción (Fase 3 del proyecto)

```
Skill 1 (análisis) → Skill 2 (persistencia) → Skill 3 (strangler) → Skill 4 (uploads) → Skill 5 (validador)
```

Cada Skill depende del output del anterior. El `migration-manifest.json` generado por Skill 1 es el contrato de datos entre Skills.
