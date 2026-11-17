---
name: "infrastructure-validator"
version: "1.0.0"
description: "Valida la completitud y correctitud de la infraestructura serverless generada por Skills 1-4. Genera reportes de validación, checklists de deployment readiness, y detecta gaps de cobertura antes del despliegue en AWS."
author: "Luis Gerardo Sánchez Ordóñez"
tags: ["aws", "validation", "cloudformation", "testing", "deployment-readiness", "gap-analysis"]
triggers:
  - "validar infraestructura"
  - "verificar templates"
  - "deployment readiness"
  - "gap coverage"
  - "validate infrastructure"
  - "check templates"
---

# Skill 05 — Validador de Infraestructura

## Cuándo activar este Skill

Activa este Skill cuando el desarrollador necesite alguna de las siguientes acciones:

- Validar que todos los templates CloudFormation fueron generados correctamente
- Verificar la completitud de la migración (coverage de endpoints)
- Detectar gaps de cobertura antes del despliegue
- Generar checklist de deployment readiness
- Probar sintaxis de templates CloudFormation/SAM
- Generar reporte de validación pre-deployment

**Palabras clave que activan este Skill:** "validar", "verificar", "deployment readiness", "gap coverage", "validate", "check", "review infrastructure"

---

## Instrucciones para el agente

Sigue estos pasos en orden cuando se active el Skill:

### Paso 1 — Validar prerrequisitos

Verifica que existen los siguientes archivos:

1. **migration-manifest.json** — Generado por Skill 01
2. **Directorio serverless-output/** — Generado por Skills 2-4

Si faltan archivos, informa al usuario:
```
❌ No se encontró serverless-output/
   Ejecuta primero: python skills/skill-02-persistence/scripts/generate_persistence.py
                    python skills/skill-03-strangler/scripts/generate_strangler.py
                    python skills/skill-04-uploads/scripts/generate_uploads.py
```

### Paso 2 — Ejecutar el validador

Ejecuta el script desde la raíz del workspace:

```bash
python skills/skill-05-validator/scripts/validate_infrastructure.py --manifest <ruta_manifest>
```

Parámetros opcionales:
- `--output <directorio>`: Directorio de salida del reporte (default: `./serverless-output/validation/`)
- `--verbose`: Mostrar detalles de cada validación
- `--skip-syntax`: Omitir validación de sintaxis CloudFormation (requiere AWS CLI)

El script generará:
1. **validation-report.json** — Reporte de validación en formato JSON
2. **validation-report.md** — Reporte en Markdown legible
3. **deployment-checklist.md** — Checklist de deployment readiness
4. **gap-coverage.json** — Análisis de gaps cubiertos vs pendientes
5. **VALIDATION_SUMMARY.md** — Resumen ejecutivo de validación

### Paso 3 — Presentar el resumen al desarrollador

Presenta la siguiente información de forma estructurada:

1. **Estado general de validación:**
   - ✅ Validación exitosa: Todos los templates OK
   - ⚠️  Validación con warnings: Templates OK pero hay warnings
   - ❌ Validación fallida: Errores encontrados

2. **Templates validados:**
   - Skill 02 (Persistencia): 2 templates
     - ✅ template-vpc.yaml
     - ✅ template-rds.yaml
   - Skill 03 (Strangler Fig): 3 templates
     - ✅ template-api-gateway.yaml
     - ✅ template-authorizer.yaml
     - ✅ template-dynamodb.yaml
   - Skill 04 (Uploads): 2 templates
     - ✅ template-s3.yaml
     - ✅ template-presigned-lambda.yaml

3. **Cobertura de endpoints:**
   - Total endpoints en manifest: `<N>`
   - Endpoints cubiertos por infraestructura: `<M>`
   - Cobertura: `<M/N * 100>%`

4. **Gaps resueltos:**
   - GAP-01 (Conexión pooling): ✅ RDS Proxy
   - GAP-02 (Local filesystem): ✅ S3 presigned URLs
   - GAP-03 (Token blacklist): ✅ DynamoDB con TTL
   - Gaps pendientes: `<lista>`

5. **Deployment readiness:**
   - [ ] Todos los templates tienen sintaxis válida
   - [ ] Todos los anti-patrones críticos resueltos
   - [ ] Documentación completa (guides, READMEs)
   - [ ] Lambda code generado
   - [ ] Test skeletons creados

### Paso 4 — Guiar próximos pasos

Informa al usuario sobre las acciones recomendadas:

```markdown
## 🚀 Próximos Pasos

### Si la validación fue exitosa (✅):

1. **Revisar deployment-checklist.md**
   - Verificar cada item antes de desplegar

2. **Desplegar en orden:**
   ```bash
   # Paso 1: Persistencia (VPC + RDS)
   cd serverless-output/persistence
   aws cloudformation deploy --template-file template-vpc.yaml --stack-name vpc-stack
   aws cloudformation deploy --template-file template-rds.yaml --stack-name rds-stack
   
   # Paso 2: Strangler Fig (API Gateway + Authorizer)
   cd ../strangler
   sam build && sam deploy --guided
   
   # Paso 3: Uploads (S3 + Lambda)
   cd ../uploads
   sam build && sam deploy --guided
   ```

3. **Probar endpoints migrados:**
   - Usa Postman/Insomnia para tests E2E
   - Verifica logs en CloudWatch

### Si hubo warnings (⚠️):

1. **Revisar validation-report.md** para ver los warnings
2. **Decidir si son bloqueantes** o pueden ignorarse
3. **Regenerar templates si es necesario**

### Si hubo errores (❌):

1. **Leer validation-report.md** para ver los errores específicos
2. **Regenerar el template problemático:**
   ```bash
   python skills/skill-0X-<nombre>/scripts/generate_<nombre>.py --manifest <manifest>
   ```
3. **Volver a validar**
```

---

## Prerrequisitos

- Python 3.9 o superior instalado en el sistema
- **migration-manifest.json** generado por Skill 01
- **serverless-output/** con templates generados por Skills 2-4
- AWS CLI configurado (opcional, para validación de sintaxis avanzada)
- No se requieren dependencias externas para el validador — usa únicamente módulos de la biblioteca estándar de Python

---

## Output generado

### Estructura de directorios

```
<output_dir>/
├── validation-report.json         # Reporte en JSON (procesable)
├── validation-report.md           # Reporte legible para humanos
├── deployment-checklist.md        # Checklist de deployment
├── gap-coverage.json              # Gaps cubiertos vs pendientes
└── VALIDATION_SUMMARY.md          # Resumen ejecutivo
```

---

## Características técnicas

### Validaciones realizadas

#### 1. Validación de existencia de archivos

```python
# Verifica que los templates esperados existen
EXPECTED_FILES = [
    'serverless-output/persistence/template-vpc.yaml',
    'serverless-output/persistence/template-rds.yaml',
    'serverless-output/strangler/template-api-gateway.yaml',
    'serverless-output/strangler/template-authorizer.yaml',
    'serverless-output/strangler/template-dynamodb.yaml',
    'serverless-output/strangler/authorizer-function/lambda_function.py',
    'serverless-output/uploads/template-s3.yaml',
    'serverless-output/uploads/template-presigned-lambda.yaml',
    'serverless-output/uploads/presigned-function/lambda_function.py',
]
```

#### 2. Validación de sintaxis CloudFormation

```yaml
# Verifica estructura básica de templates
- AWSTemplateFormatVersion: presente
- Description: no vacía
- Resources: al menos 1 recurso definido
- Outputs: recomendado (warning si falta)
```

#### 3. Validación de código Lambda

```python
# Verifica estructura del código Lambda
- lambda_handler function presente
- imports correctos (boto3, json, os)
- No syntax errors (compila con ast.parse)
```

#### 4. Validación de cobertura de endpoints

```python
# Calcula cobertura basada en manifest
total_endpoints = len(manifest['modules'][*]['endpoints'])
covered_endpoints = count_covered_by_infrastructure()
coverage_percentage = (covered_endpoints / total_endpoints) * 100
```

#### 5. Validación de resolución de gaps

```python
# Verifica que cada gap crítico tiene infraestructura asociada
GAPS_TO_INFRASTRUCTURE = {
    'GAP-01': 'RDS Proxy in template-rds.yaml',
    'GAP-02': 'S3 bucket in template-s3.yaml',
    'GAP-03': 'DynamoDB table in template-dynamodb.yaml'
}
```

### Estructura del validation-report.json

```json
{
  "timestamp": "2026-11-09T22:00:00Z",
  "status": "success|warning|error",
  "summary": {
    "total_templates": 7,
    "valid_templates": 7,
    "warnings": 0,
    "errors": 0
  },
  "templates": [
    {
      "path": "serverless-output/persistence/template-vpc.yaml",
      "status": "valid",
      "warnings": [],
      "errors": []
    }
  ],
  "coverage": {
    "total_endpoints": 29,
    "covered_endpoints": 29,
    "percentage": 100.0
  },
  "gaps": {
    "total": 14,
    "resolved": 3,
    "pending": 11,
    "critical_resolved": ["GAP-01", "GAP-02", "GAP-03"]
  },
  "deployment_ready": true
}
```

---

## Deployment Checklist

El validador genera un checklist interactivo:

```markdown
# Deployment Checklist

## Pre-Deployment

- [ ] Todos los templates CloudFormation validados
- [ ] AWS CLI configurado con credenciales válidas
- [ ] SAM CLI instalado (para Lambda deployment)
- [ ] Permisos IAM verificados:
  - [ ] CloudFormation: CreateStack, UpdateStack
  - [ ] EC2: CreateVpc, CreateSubnet (para VPC)
  - [ ] RDS: CreateDBCluster, CreateDBProxy
  - [ ] Lambda: CreateFunction, UpdateFunctionCode
  - [ ] API Gateway: CreateRestApi
  - [ ] S3: CreateBucket, PutBucketPolicy

## Deployment Sequence

### Fase 1: Persistencia
- [ ] Deploy template-vpc.yaml (VPC + subnets)
- [ ] Verificar VPC ID en outputs
- [ ] Deploy template-rds.yaml (Aurora + RDS Proxy)
- [ ] Verificar RDS Proxy endpoint

### Fase 2: Strangler Fig
- [ ] Deploy template-dynamodb.yaml (token blacklist)
- [ ] Verificar DynamoDB table creada
- [ ] Deploy template-authorizer.yaml (Lambda Authorizer)
- [ ] Verificar Lambda Authorizer ARN
- [ ] Deploy template-api-gateway.yaml (API Gateway)
- [ ] Verificar API Gateway URL

### Fase 3: Uploads
- [ ] Deploy template-s3.yaml (S3 bucket)
- [ ] Verificar bucket CORS configurado
- [ ] Deploy template-presigned-lambda.yaml (presigned URLs)
- [ ] Verificar Lambda + API Gateway

## Post-Deployment

- [ ] Smoke tests: cada endpoint responde
- [ ] Test E2E: flujo completo (auth → query → upload)
- [ ] Monitoreo: CloudWatch Logs configurado
- [ ] Alertas: SNS topics configurados (opcional)
- [ ] Documentación: actualizar URLs de producción
```

---

## Gap Coverage Analysis

### Gaps Críticos Resueltos

| Gap ID | Descripción | Resuelto por | Template |
|--------|-------------|--------------|----------|
| GAP-01 | Connection pooling | RDS Proxy | template-rds.yaml |
| GAP-02 | Local filesystem | S3 presigned URLs | template-s3.yaml |
| GAP-03 | Token blacklist in-memory | DynamoDB TTL | template-dynamodb.yaml |

### Gaps No Críticos Pendientes

Los siguientes gaps son **no bloqueantes** pero deben documentarse:

- **AP-cross-blueprint** (12 endpoints): Requiere Lambda Layers o refactoring
- Complejidad: Media
- Impacto: Duplicación de código si no se resuelve
- Recomendación: Implementar en sprint posterior

---

## Optimizaciones aplicadas

### 1. Validación rápida sin AWS CLI

El validador puede funcionar **completamente offline** para validaciones básicas:
- Parseo de YAML con módulos estándar
- Validación de estructura JSON/YAML
- Verificación de existencia de archivos
- No requiere conexión a AWS

### 2. Validación avanzada con AWS CLI (opcional)

Si AWS CLI está disponible:
```bash
# Validar sintaxis CloudFormation
aws cloudformation validate-template --template-body file://template.yaml

# Detectar drift antes de desplegar
aws cloudformation detect-stack-drift --stack-name <stack>
```

### 3. Reporte en múltiples formatos

- **JSON** — Para CI/CD pipelines y procesamiento automatizado
- **Markdown** — Para revisión humana y documentación
- **Exit codes** — Para scripts de deployment:
  - 0: Validación exitosa
  - 1: Warnings (puede desplegarse)
  - 2: Errores (NO desplegar)

---

## Integración con otros Skills

### ⬅️ Consume desde Skill 01:
- `migration-manifest.json`: total de endpoints, anti-patterns, gaps

### ⬅️ Consume desde Skill 02:
- Templates de persistencia (VPC + RDS)
- Validación de conexión string format

### ⬅️ Consume desde Skill 03:
- Templates de Strangler Fig (API Gateway + Authorizer + DynamoDB)
- Validación de routing rules

### ⬅️ Consume desde Skill 04:
- Templates de uploads (S3 + Lambda)
- Validación de CORS configuration

### ➡️ Produce para:
- **CI/CD Pipelines:** validation-report.json con exit codes
- **Deployment Scripts:** deployment-checklist.md
- **Project Management:** gap-coverage.json para tracking

---

## Limitaciones conocidas

1. **Validación sintáctica solamente:** El validador NO despliega infraestructura. Solo verifica sintaxis y existencia de archivos.

2. **Validación de IAM policies limitada:** No verifica que las policies IAM sean suficientes para el deployment real.

3. **No valida runtime behavior:** No prueba que una Lambda funcione correctamente, solo que el código compile.

4. **Dependencias entre stacks:** No valida el orden correcto de deployment (debe seguirse el deployment-checklist.md).

---

## Troubleshooting

### Error: "Template not found"

**Causa:** Un Skill previo (2, 3, o 4) no se ejecutó

**Solución:**
```bash
# Regenerar el template faltante
python skills/skill-0X-<nombre>/scripts/generate_<nombre>.py --manifest <manifest>

# Volver a validar
python skills/skill-05-validator/scripts/validate_infrastructure.py --manifest <manifest>
```

### Warning: "Output section missing"

**Causa:** Template no exporta outputs (recomendado para inter-stack references)

**Solución:**
```yaml
# Agregar sección Outputs al template
Outputs:
  VpcId:
    Description: VPC ID
    Value: !Ref VPC
    Export:
      Name: !Sub '${AWS::StackName}-VpcId'
```

### Error: "Lambda syntax error"

**Causa:** Código Lambda tiene errores de sintaxis Python

**Solución:**
```bash
# Validar sintaxis manualmente
python -m py_compile serverless-output/uploads/presigned-function/lambda_function.py

# Regenerar si es necesario
python skills/skill-04-uploads/scripts/generate_uploads.py --manifest <manifest>
```

---

## Referencias

- [CloudFormation Template Anatomy](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-anatomy.html)
- [SAM CLI Validate](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-validate.html)
- [CFN-Lint](https://github.com/aws-cloudformation/cfn-lint) — Linter avanzado (no usado en este Skill)

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software  
**Institución:** Pontificia Universidad Javeriana Cali  
**Director:** Juan Gabriel Quintero Barbosa — Head Solutions Architecture, AWS Colombia
