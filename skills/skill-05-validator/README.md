# Skill 05 — Validador de Infraestructura

**Estado:** ✅ Completado  
**Versión:** 1.0.0  
**Última actualización:** 9 de noviembre de 2026

---

## Descripción

Valida la completitud y correctitud de la infraestructura serverless generada por Skills 1-4. Genera reportes de validación, checklists de deployment readiness, y detecta gaps de cobertura antes del despliegue en AWS.

### ¿Qué valida este Skill?

1. **Existencia de templates CloudFormation/SAM:**
   - Skills 2-4 generan 7 templates en total
   - Verifica que todos existen antes de deployment

2. **Sintaxis básica de YAML:**
   - `AWSTemplateFormatVersion` presente
   - Sección `Resources` obligatoria
   - Sección `Outputs` recomendada

3. **Código Lambda sin errores:**
   - Sintaxis Python válida (parsing con AST)
   - Función `lambda_handler` presente
   - Imports comunes (boto3) verificados

4. **Cobertura de endpoints:**
   - 100% de endpoints del manifest cubiertos por infraestructura

5. **Resolución de gaps críticos:**
   - GAP-01 (Connection pooling) → RDS Proxy
   - GAP-02 (Local filesystem) → S3 presigned URLs
   - GAP-03 (Token blacklist) → DynamoDB TTL

6. **Deployment readiness:**
   - Todos los templates válidos
   - Anti-patrones críticos resueltos
   - Documentación completa

---

## Uso

### Prerrequisitos

- Python 3.9 o superior
- **migration-manifest.json** generado por Skill 01
- **serverless-output/** con templates generados por Skills 2-4
- AWS CLI configurado (opcional, para validación avanzada)

### Ejecución

```bash
# Desde la raíz del workspace
python skills/skill-05-validator/scripts/validate_infrastructure.py \
  --manifest monolith/migration-manifest.json

# Con verbose output
python skills/skill-05-validator/scripts/validate_infrastructure.py \
  --manifest monolith/migration-manifest.json \
  --verbose

# Con directorio de salida personalizado
python skills/skill-05-validator/scripts/validate_infrastructure.py \
  --manifest monolith/migration-manifest.json \
  --output ./validation-reports
```

### Parámetros

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--manifest` | Ruta al migration-manifest.json | (requerido) |
| `--output` | Directorio de salida de reportes | `serverless-output/validation/` |
| `--verbose` | Mostrar detalles de cada validación | `False` |

### Output generado

```
<output_dir>/
├── validation-report.json         # Reporte en JSON (procesable)
├── validation-report.md           # Reporte legible para humanos
├── deployment-checklist.md        # Checklist de deployment
└── gap-coverage.json              # Gaps cubiertos vs pendientes
```

---

## Exit Codes

El script retorna diferentes exit codes según el resultado:

| Exit Code | Significado | Acción recomendada |
|-----------|-------------|-------------------|
| **0** | ✅ Validación exitosa | Proceder con deployment |
| **1** | ⚠️  Warnings encontrados | Revisar warnings, luego deployar |
| **2** | ❌ Errores encontrados | Regenerar templates, NO deployar |

---

## Estructura del Reporte JSON

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
      "skill": "skill-02",
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
    "critical_resolved": ["GAP-01", "GAP-02", "GAP-03"],
    "critical_pending": []
  },
  "deployment_ready": true
}
```

---

## Validaciones Realizadas

### 1. Validación de Existencia

Verifica que existen los siguientes archivos:

**Skill 02 (Persistence):**
- `serverless-output/persistence/template-vpc.yaml`
- `serverless-output/persistence/template-rds.yaml`

**Skill 03 (Strangler Fig):**
- `serverless-output/strangler/template-api-gateway.yaml`
- `serverless-output/strangler/template-authorizer.yaml`
- `serverless-output/strangler/template-dynamodb.yaml`
- `serverless-output/strangler/authorizer-function/lambda_function.py`

**Skill 04 (Uploads):**
- `serverless-output/uploads/template-s3.yaml`
- `serverless-output/uploads/template-presigned-lambda.yaml`
- `serverless-output/uploads/presigned-function/lambda_function.py`

### 2. Validación de Sintaxis YAML

```yaml
# Elementos verificados:
AWSTemplateFormatVersion: '2010-09-09'  # Obligatorio
Description: ...                         # Recomendado
Resources:                               # Obligatorio
  ...
Outputs:                                 # Recomendado
  ...
```

### 3. Validación de Código Lambda

```python
# Verificaciones:
- Sintaxis Python válida (ast.parse)
- Función lambda_handler definida
- Import boto3 presente (warning si falta)
- No SyntaxErrors
```

### 4. Cobertura de Endpoints

```python
# Cálculo:
coverage_percentage = (covered_endpoints / total_endpoints) * 100

# Esperado: 100% (todos los endpoints cubiertos)
```

### 5. Resolución de Gaps Críticos

| Gap ID | Resuelto por | Verificación |
|--------|--------------|--------------|
| GAP-01 | RDS Proxy | Busca `DBProxy` en `template-rds.yaml` |
| GAP-02 | S3 bucket | Busca `AWS::S3::Bucket` en `template-s3.yaml` |
| GAP-03 | DynamoDB TTL | Busca `AWS::DynamoDB::Table` en `template-dynamodb.yaml` |

---

## Deployment Checklist

El validador genera un checklist interactivo con:

### Pre-Deployment
- [ ] Todos los templates CloudFormation validados
- [ ] AWS CLI configurado con credenciales válidas
- [ ] SAM CLI instalado
- [ ] Permisos IAM verificados

### Deployment Sequence
- [ ] Fase 1: VPC + RDS
- [ ] Fase 2: API Gateway + Authorizer + DynamoDB
- [ ] Fase 3: S3 + Lambda presigned URLs

### Post-Deployment
- [ ] Smoke tests ejecutados
- [ ] CloudWatch Logs configurado
- [ ] Endpoints públicos documentados

---

## Ejemplos de Uso

### Caso 1: Validación exitosa

```bash
$ python skills/skill-05-validator/scripts/validate_infrastructure.py \
    --manifest monolith/migration-manifest.json

======================================================================
Skill 05 — Validador de Infraestructura
Versión: 1.0.0
======================================================================

📄 Cargando manifest: monolith/migration-manifest.json
✅ Manifest cargado: 29 endpoints

🔍 Validando templates CloudFormation...
✅ Todos los templates validados correctamente

📊 Analizando cobertura de endpoints...
✅ Cobertura: 29/29 endpoints (100.0%)

🔧 Analizando resolución de gaps...
✅ Gaps críticos resueltos: 3/3

📝 Generando reportes...
💾 Escribiendo reportes en: serverless-output/validation
   📄 validation-report.json
   📄 validation-report.md
   📄 deployment-checklist.md
   📄 gap-coverage.json

✅ Reportes generados en: serverless-output/validation

======================================================================
✅ Validación EXITOSA
======================================================================

🎉 Infraestructura lista para desplegar!
   • 9 templates validados
   • 100.0% cobertura de endpoints
   • 3/3 gaps críticos resueltos

📚 Próximos pasos:
   1. Revisa serverless-output/validation/deployment-checklist.md
   2. Ejecuta los comandos de deployment en orden
   3. Prueba los endpoints migrados

Exit Code: 0
```

### Caso 2: Validación con warnings

```bash
$ python skills/skill-05-validator/scripts/validate_infrastructure.py \
    --manifest monolith/migration-manifest.json

...

⚠️  Validación CON WARNINGS
...
✅ No hay errores bloqueantes, pero hay 2 warnings.
   Revisa serverless-output/validation/validation-report.md para detalles.

Exit Code: 1
```

### Caso 3: Validación fallida

```bash
$ python skills/skill-05-validator/scripts/validate_infrastructure.py \
    --manifest monolith/migration-manifest.json

...

❌ Validación FALLIDA
...
⚠️  Se encontraron 3 errores.
   Revisa serverless-output/validation/validation-report.md para detalles.

🔧 Acciones recomendadas:
   1. Lee los errores específicos en el reporte
   2. Regenera los templates problemáticos
   3. Vuelve a ejecutar la validación

Exit Code: 2
```

---

## Integración con CI/CD

### GitHub Actions Example

```yaml
name: Validate Infrastructure

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Generate infrastructure
        run: |
          python skills/skill-02-persistence/scripts/generate_persistence.py --manifest monolith/migration-manifest.json
          python skills/skill-03-strangler/scripts/generate_strangler.py --manifest monolith/migration-manifest.json
          python skills/skill-04-uploads/scripts/generate_uploads.py --manifest monolith/migration-manifest.json
      
      - name: Validate infrastructure
        run: |
          python skills/skill-05-validator/scripts/validate_infrastructure.py --manifest monolith/migration-manifest.json
      
      - name: Upload validation report
        uses: actions/upload-artifact@v3
        with:
          name: validation-report
          path: serverless-output/validation/
```

---

## Integración con otros Skills

### ⬅️ Consume desde Skill 01:
- `migration-manifest.json`: total de endpoints, anti-patterns, gaps

### ⬅️ Consume desde Skill 02:
- Templates de persistencia (VPC + RDS)

### ⬅️ Consume desde Skill 03:
- Templates de Strangler Fig (API Gateway + Authorizer + DynamoDB)

### ⬅️ Consume desde Skill 04:
- Templates de uploads (S3 + Lambda)

### ➡️ Produce para:
- **CI/CD Pipelines:** `validation-report.json` con exit codes
- **Deployment Scripts:** `deployment-checklist.md`
- **Project Management:** `gap-coverage.json` para tracking

---

## Limitaciones conocidas

1. **Validación sintáctica solamente:** No despliega infraestructura, solo verifica sintaxis y existencia de archivos.

2. **Validación de IAM policies limitada:** No verifica que las policies IAM sean suficientes para el deployment real.

3. **No valida runtime behavior:** No prueba que una Lambda funcione correctamente, solo que el código compile.

4. **Dependencias entre stacks:** No valida el orden correcto de deployment (debe seguirse el deployment-checklist.md).

5. **Validación YAML simplificada:** Usa parsing de strings, no un parser YAML completo (evita dependencias externas).

---

## Tests

```bash
# Test 1: Validación exitosa (todos los Skills generados)
python skills/skill-05-validator/scripts/validate_infrastructure.py \
  --manifest monolith/migration-manifest.json
# Esperado: exit code 0

# Test 2: Validación con templates faltantes
# (sin ejecutar Skills 2-3-4 primero)
python skills/skill-05-validator/scripts/validate_infrastructure.py \
  --manifest monolith/migration-manifest.json
# Esperado: exit code 2, errores de templates no encontrados

# Test 3: Validación con verbose output
python skills/skill-05-validator/scripts/validate_infrastructure.py \
  --manifest monolith/migration-manifest.json \
  --verbose
# Esperado: mostrar ✅ por cada template validado
```

---

## Troubleshooting

### Error: "Template not found"

**Causa:** Un Skill previo (2, 3, o 4) no se ejecutó

**Solución:**
```bash
# Regenerar el template faltante
python skills/skill-02-persistence/scripts/generate_persistence.py --manifest <manifest>
python skills/skill-03-strangler/scripts/generate_strangler.py --manifest <manifest>
python skills/skill-04-uploads/scripts/generate_uploads.py --manifest <manifest>

# Volver a validar
python skills/skill-05-validator/scripts/validate_infrastructure.py --manifest <manifest>
```

### Warning: "Output section missing"

**Causa:** Template no exporta outputs (recomendado para inter-stack references)

**Solución:** Agregar sección Outputs al template (no bloqueante)

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
- [AWS CloudFormation Best Practices](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html)

---

## Siguientes pasos

1. ✅ Generar infraestructura con Skills 2-4
2. ✅ Ejecutar validador
3. ⏭️ Revisar validation-report.md
4. ⏭️ Seguir deployment-checklist.md
5. ⏭️ Desplegar en AWS
6. ⏭️ Probar endpoints E2E

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software  
**Institución:** Pontificia Universidad Javeriana Cali  
**Director:** Juan Gabriel Quintero Barbosa — Head Solutions Architecture, AWS Colombia
