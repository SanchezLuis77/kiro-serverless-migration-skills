# Skill 01 — Analizador de Monolito Flask

**Versión:** 1.0.0  
**Autor:** Luis Gerardo Sánchez Ordóñez  
**Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software, Pontificia Universidad Javeriana Cali  

---

## Descripción

El Skill 01 examina el código fuente de un monolito Flask mediante análisis estático del Árbol de Sintaxis Abstracta (AST) y produce el archivo **`migration-manifest.json`** — el contrato de datos que los Skills 02 al 05 consumen como insumo para generar la infraestructura serverless en AWS.

El análisis opera **exclusivamente en memoria local**: ningún fragmento del código fuente es transmitido a servicios externos. Usa únicamente módulos de la biblioteca estándar de Python (`ast`, `os`, `json`, `pathlib`, `re`, `datetime`, `argparse`).

### ¿Qué es `migration-manifest.json`?

Es un archivo JSON que describe:

| Sección | Contenido |
|---|---|
| `metadata` | Fecha de análisis, ruta del monolito, versión del analizador, advertencias |
| `modules` | Cada blueprint Flask con sus endpoints, anti-patrones detectados, cohesión e aislamiento |
| `lambda_layers` | Lambda Layers recomendadas derivadas del análisis de dependencias compartidas |
| `migration_sequence` | Secuencia de migración por fases siguiendo el patrón Strangler Fig |
| `summary` | Contadores agregados: total de endpoints, candidatos por destino de cómputo, bloqueadores críticos |

---

## Instalación

### En Kiro IDE (nivel de workspace)

Copia el directorio del Skill al directorio de Skills del workspace:

```bash
# Desde la raíz del workspace
cp -r skills/skill-01-analyzer .kiro/skills/
```

O bien, si el directorio ya está en `skills/skill-01-analyzer/` dentro del workspace, Kiro lo detecta automáticamente al leer `SKILL.md`.

### Verificar instalación

Abre Kiro IDE y escribe en el chat: "analizar monolito". Kiro debe reconocer el trigger y activar el Skill.

---

## Uso desde Kiro IDE

El Skill se activa por lenguaje natural. Ejemplos de prompts que lo disparan:

```
"Analiza el monolito Flask en monolith/"
"Genera el manifiesto de migración para comenzar la migración a serverless"
"Detecta anti-patrones de migración en mi aplicación Flask"
"Quiero migrar mi monolito a AWS Lambda, ¿por dónde empiezo?"
"Analiza el monolito y dame la secuencia de migración Strangler Fig"
```

El agente ejecutará el script automáticamente, leerá el manifiesto generado y presentará un resumen estructurado con los hallazgos.

---

## Uso desde terminal

### Caso básico — analizar el monolito de referencia

```bash
python skills/skill-01-analyzer/scripts/analyze_monolith.py --path monolith/
```

El manifiesto se escribe en `monolith/migration-manifest.json`.

### Especificar ruta de salida personalizada

```bash
python skills/skill-01-analyzer/scripts/analyze_monolith.py \
  --path /ruta/al/monolito \
  --output /ruta/manifiesto.json
```

### Verificar el resultado

```bash
# Ver el resumen del manifiesto
python -c "import json; m=json.load(open('monolith/migration-manifest.json')); print(json.dumps(m['summary'], indent=2))"

# Ver la secuencia de migración
python -c "import json; m=json.load(open('monolith/migration-manifest.json')); [print(f'Fase {p[\"phase\"]}: {p[\"module\"]}') for p in m['migration_sequence']]"
```

### Códigos de salida

| Código | Condición |
|---|---|
| `0` | Análisis completado exitosamente; manifiesto escrito |
| `1` | El directorio `--path` no existe |
| `2` | No se encontraron blueprints Flask en el directorio |
| `3` | Error de escritura del manifiesto (se intenta fallback a `cwd`) |

---

## Estructura del `migration-manifest.json`

### `metadata`

```json
{
  "analyzed_at": "2026-08-01T10:30:00Z",
  "monolith_path": "/workspace/monolith",
  "total_endpoints": 29,
  "analyzer_version": "1.0.0",
  "skill_version": "1.0.0",
  "warnings": []
}
```

### `modules`

Array de objetos, uno por blueprint Flask. Cada objeto contiene:

- `name`: nombre del módulo (p. ej., `"auth"`)
- `blueprint_variable`: nombre de la variable blueprint en el código (p. ej., `"auth_bp"`)
- `blueprint_prefix`: prefijo URL (p. ej., `"/api/auth"`)
- `routes_file`: ruta relativa al archivo de rutas
- `cohesion`: `"high"` | `"medium"` | `"low"`
- `isolation`: `"high"` | `"medium"` | `"low"`
- `anti_patterns`: array de anti-patrones detectados a nivel de módulo
- `cross_blueprint_imports`: array de dependencias entre blueprints (p. ej., `"transacciones → clientes"`)
- `endpoints`: array de endpoints (ver estructura de endpoint abajo)

**Estructura de un endpoint:**

```json
{
  "id": "transacciones.subir_adjunto",
  "method": "POST",
  "path": "/api/transacciones/{orden_id}/adjunto",
  "relative_path": "/<int:orden_id>/adjunto",
  "function_name": "subir_adjunto",
  "auth_required": true,
  "admin_required": false,
  "compute_target": "lambda",
  "requires_architectural_transformation": true,
  "migration_complexity": "very_high",
  "anti_patterns": ["AP-local-filesystem"],
  "gap_ids": ["GAP-02"]
}
```

### `lambda_layers`

Lista de Lambda Layers recomendadas, derivada del análisis de dependencias compartidas:

```json
[
  {
    "name": "taller-db-layer",
    "description": "Modelos SQLAlchemy refactorizados e inicialización de conexión a RDS Proxy",
    "consumed_by": ["auth", "clientes", "servicios", "transacciones", "reportes"]
  }
]
```

### `migration_sequence`

Fases de migración ordenadas por complejidad de acoplamiento creciente (patrón Strangler Fig):

```json
[
  {
    "phase": 1,
    "module": "servicios",
    "justification": "Menor acoplamiento; 3 endpoints públicos permiten validación sin autenticación",
    "prerequisites": ["taller-db-layer", "taller-utils-layer"]
  }
]
```

### `summary`

```json
{
  "total_endpoints": 29,
  "lambda_candidates": 28,
  "fargate_candidates": 0,
  "app_runner_candidates": 0,
  "requires_transformation": 1,
  "critical_blockers": 1,
  "anti_pattern_summary": {
    "AP-token-blacklist": 1,
    "AP-local-filesystem": 1,
    "AP-strftime-sqlite": 1,
    "AP-session-flask": 2,
    "AP-order-num-ts": 1,
    "AP-cross-blueprint": 8,
    "AP-in-memory-singleton": 4
  }
}
```

**Invariantes verificables:**

```
summary.total_endpoints == Σ len(módulo.endpoints) para todo módulo   [I-1]
lambda_candidates + fargate_candidates + app_runner_candidates + requires_transformation == total_endpoints   [I-2]
```

---

## Anti-patrones detectados

El Analizador detecta los siguientes anti-patrones que bloquean o dificultan la migración a serverless:

| Código | Descripción | GAP ID | Severidad |
|---|---|---|---|
| `AP-local-filesystem` | Almacenamiento de archivos en el sistema de archivos local del servidor (`archivo.save(ruta)`, `os.path.join(UPLOAD_FOLDER, ...)`) | GAP-02 | critical |
| `AP-token-blacklist` | Lista negra de tokens JWT almacenada en un `set()` en memoria del proceso (`_tokens_revocados = set()`) | GAP-03 | high |
| `AP-strftime-sqlite` | Uso de `func.strftime()` de SQLAlchemy, función exclusiva del dialecto SQLite, incompatible con PostgreSQL/Aurora | GAP-04 | high |
| `AP-session-flask` | Uso de `session[...]` de Flask como mecanismo de autenticación, incompatible con el modelo stateless de Lambda | GAP-06 | medium |
| `AP-order-num-ts` | Generación de identificadores únicos basada en `datetime.utcnow()`, susceptible a colisiones bajo concurrencia | GAP-14 | medium |
| `AP-cross-blueprint` | Importación directa entre blueprints (`from app.blueprints.A.routes import func`), genera acoplamiento lateral incompatible con Lambdas independientes | — | high |
| `AP-in-memory-singleton` | Singletons o estado compartido en memoria del proceso (p. ej., `CacheService`, `_cache = {}`) incompatibles con el modelo multi-instancia de Lambda | — | medium |

### Recomendaciones de remediación

| Anti-patrón | Remediación serverless |
|---|---|
| `AP-local-filesystem` | Migrar a flujo de S3 presigned URL (Skill 04) |
| `AP-token-blacklist` | Reemplazar `set()` con tabla DynamoDB para blacklist fail-closed (Skill 03) |
| `AP-strftime-sqlite` | Reemplazar `func.strftime` por `func.to_char` para PostgreSQL (Skill 02) |
| `AP-session-flask` | Eliminar uso de `session[]`; usar exclusivamente JWT stateless |
| `AP-order-num-ts` | Reemplazar `datetime.utcnow()` con `uuid.uuid4()` para identificadores únicos |
| `AP-cross-blueprint` | Mover funciones compartidas a Lambda Layer (`taller-utils-layer`) |
| `AP-in-memory-singleton` | Reemplazar con ElastiCache, DynamoDB o instanciación por invocación |

---

## Prerrequisitos

- **Python 3.9 o superior** — el script usa `typing.TypedDict` y `dataclasses` disponibles desde Python 3.9
- **Sin dependencias adicionales** — no se requiere `pip install` para el caso de uso básico (solo biblioteca estándar de Python)
- **Para tests de propiedad** (opcional, solo desarrollo): `pip install hypothesis pytest`

---

## Compatibilidad

| Componente | Versión compatible |
|---|---|
| Python | 3.9+ |
| Flask | 2.x |
| Flask-SQLAlchemy | 3.x |
| Flask-JWT-Extended | 4.x |
| Flask-Migrate | 4.x |
| Marshmallow | 3.x |
| Sistema operativo | Linux, macOS, Windows |

---

## Integración con el pipeline de Skills

```
Skill 01 (Analizador) ──► migration-manifest.json
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             Skill 02         Skill 03        Skill 04
          (Persistencia)    (Strangler)      (Uploads)
          RDS + VPC + IaC   API GW + Auth   S3 presigned
                    │               │               │
                    └───────────────┴───────────────┘
                                    │
                                    ▼
                             Skill 05 (Validador)
                          Completitud + Observabilidad
```

---

## Licencia

MIT License — Proyecto de investigación académica, Pontificia Universidad Javeriana Cali.
