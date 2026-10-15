---
name: "monolith-analyzer"
version: "1.0.0"
description: "Analiza estáticamente un monolito Flask mediante AST y genera migration-manifest.json con la recomendación de destino AWS por endpoint, anti-patrones detectados y secuencia de migración Strangler Fig."
author: "Luis Gerardo Sánchez Ordóñez"
tags: ["aws", "serverless", "migration", "flask", "analyzer", "ast"]
triggers:
  - "analizar monolito"
  - "migrar a serverless"
  - "analizar flask"
  - "generar manifiesto de migración"
  - "detectar anti-patrones"
  - "analyze monolith"
  - "serverless migration"
---

# Skill 01 — Analizador de Monolito Flask

## Cuándo activar este Skill

Activa este Skill cuando el desarrollador necesite alguna de las siguientes acciones:

- Analizar un monolito Flask para planificar su migración a serverless en AWS
- Generar el `migration-manifest.json` que será consumido por los Skills 02 al 05
- Detectar anti-patrones de migración serverless en el código fuente Flask (blacklist en memoria, uploads a filesystem, `strftime` SQLite, etc.)
- Obtener la recomendación de destino de cómputo AWS (Lambda / Fargate / App Runner) para cada endpoint
- Iniciar el pipeline completo de migración con los 5 Skills
- Conocer la secuencia óptima de migración siguiendo el patrón Strangler Fig

**Palabras clave que activan este Skill:** "analizar", "migrar", "monolito", "serverless", "lambda", "manifiesto", "anti-patrones", "Strangler Fig", "analyze", "migration manifest", "flask migration"

---

## Instrucciones para el agente

Sigue estos pasos en orden cuando se active el Skill:

### Paso 1 — Localizar el directorio del monolito

Determina la ruta del directorio raíz del monolito Flask:

1. Si el usuario especificó una ruta explícita, usa esa ruta.
2. Si no, busca el directorio `monolith/` en la raíz del workspace actual.
3. Si no existe `monolith/`, pregunta al usuario: "¿Cuál es la ruta al directorio raíz de tu aplicación Flask?"

### Paso 2 — Ejecutar el Analizador

Ejecuta el script desde la raíz del workspace:

```bash
python skills/skill-01-analyzer/scripts/analyze_monolith.py --path <ruta_al_monolito>
```

Si el usuario desea un destino personalizado para el manifiesto:

```bash
python skills/skill-01-analyzer/scripts/analyze_monolith.py --path <ruta_al_monolito> --output <ruta_manifiesto.json>
```

Verifica que el proceso termina con código de salida `0`. Si termina con código `1`, el directorio no existe. Si termina con código `2`, no se encontraron blueprints Flask.

### Paso 3 — Leer el manifiesto generado

Lee el archivo `migration-manifest.json` producido (ubicado por defecto en el directorio raíz del monolito) usando las herramientas de lectura de archivos disponibles.

### Paso 4 — Presentar el resumen al desarrollador

Presenta la siguiente información de forma estructurada y legible:

1. **Total de endpoints descubiertos** — número entero de `summary.total_endpoints`

2. **Distribución por módulo** — tabla con columnas: Módulo | Endpoints | Cohesión | Aislamiento, usando los datos de `modules[*].{name, endpoints.length, cohesion, isolation}`

3. **Anti-patrones detectados** — lista de anti-patrones encontrados con su código, descripción breve y GAP IDs asociados, extrayendo de `modules[*].anti_patterns`

4. **Distribución de destino de cómputo** — tabla con: Lambda (directos) | Lambda (requieren transformación) | Fargate | App Runner, usando `summary.{lambda_candidates, requires_transformation, fargate_candidates, app_runner_candidates}`

5. **Secuencia de migración sugerida** — lista numerada de las fases de `migration_sequence[*].{phase, module, justification}`

6. **Bloqueadores críticos** — si `summary.critical_blockers > 0`, listar los endpoints con `requires_architectural_transformation: true` indicando que requieren transformación arquitectónica antes del despliegue (GAP-02: migración de uploads a S3 presigned URL)

### Paso 5 — Indicar disponibilidad del manifiesto

Informa al desarrollador que el archivo `migration-manifest.json` ha sido generado y está listo para ser consumido por los Skills 02 al 05:

- **Skill 02** (Migrador de Persistencia): usa el manifiesto + modelos SQLAlchemy para generar templates SAM con RDS Aurora Serverless v2
- **Skill 03** (Orquestador Strangler Fig): usa el manifiesto + configuración JWT para generar API Gateway + Lambda Authorizer
- **Skill 04** (Migrador de Uploads): usa los endpoints con `requires_architectural_transformation: true` para generar el flujo de presigned URLs con S3
- **Skill 05** (Validador Post-Generación): usa el manifiesto para validar la completitud del output generado

---

## Prerrequisitos

- Python 3.9 o superior instalado en el sistema
- El monolito Flask debe estar accesible en el sistema de archivos local del workspace
- No se requieren dependencias adicionales (`pip install`) para el caso de uso básico — el script utiliza únicamente módulos de la biblioteca estándar de Python
- El análisis opera completamente en memoria local: ningún fragmento del código fuente del monolito es transmitido a servicios externos

---

## Output generado

- **`migration-manifest.json`**: archivo JSON con indentación de 2 espacios, escrito en el directorio raíz del monolito analizado (o en la ruta especificada con `--output`)
