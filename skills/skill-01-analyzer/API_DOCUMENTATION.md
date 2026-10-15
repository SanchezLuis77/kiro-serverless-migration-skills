# API Documentation — Skill 01: Analizador de Monolito

**Version:** 1.0.0  
**Author:** Luis Gerardo Sánchez Ordóñez  
**Project:** Trabajo de Grado — Maestría en Ingeniería de Software

---

## Table of Contents

1. [Overview](#overview)
2. [Command-Line Interface](#command-line-interface)
3. [Output Format](#output-format)
4. [Python API](#python-api)
5. [Error Codes](#error-codes)
6. [Anti-Pattern Catalog](#anti-pattern-catalog)
7. [Examples](#examples)

---

## Overview

The **Analizador de Monolito** is a static analysis tool that examines Flask monoliths via Abstract Syntax Tree (AST) parsing and generates comprehensive migration manifests for AWS serverless architectures.

### Key Features

- ✅ **Zero dependencies** — Uses only Python 3.9+ standard library
- ✅ **Fast** — Analyzes typical monoliths in < 2 seconds
- ✅ **Privacy-first** — No code execution, all analysis in-memory
- ✅ **Fault-tolerant** — Handles syntax errors gracefully
- ✅ **Deterministic** — Same input always produces same output

### Input

- Flask monolith directory with blueprint-based architecture

### Output

- `migration-manifest.json` — Complete migration specification

---

## Command-Line Interface

### Basic Usage

```bash
python analyze_monolith.py --path <monolith_directory>
```

### Full Syntax

```bash
python analyze_monolith.py --path <monolith_directory> [--output <manifest_path>]
```

### Arguments

#### `--path <monolith_directory>` (required)

Absolute or relative path to the Flask monolith root directory.

**Example:**
```bash
python analyze_monolith.py --path /home/user/my-flask-app
python analyze_monolith.py --path ../monolith
```

#### `--output <manifest_path>` (optional)

Path where the migration manifest will be written.

**Default:** `<path>/migration-manifest.json`

**Example:**
```bash
python analyze_monolith.py --path ../monolith --output /tmp/manifest.json
```

### Exit Codes

| Code | Meaning | When |
|------|---------|------|
| 0 | Success | Analysis completed, manifest written |
| 1 | Path Not Found | `--path` directory doesn't exist |
| 2 | No Blueprints Found | No Flask blueprints discovered |
| 3 | Write Failed | Cannot write manifest (after fallback) |

---

## Output Format

### Manifest Structure

```json
{
  "metadata": { /* Analysis metadata */ },
  "summary": { /* Aggregated metrics */ },
  "modules": [ /* Per-module analysis */ ],
  "lambda_layers": [ /* Recommended Lambda Layers */ ],
  "migration_sequence": [ /* Ordered migration phases */ ]
}
```

### Section: `metadata`

```json
{
  "analyzed_at": "2026-08-28T15:30:00.123456+00:00",
  "monolith_path": "/absolute/path/to/monolith",
  "total_endpoints": 29,
  "analyzer_version": "1.0.0",
  "skill_version": "1.0.0",
  "warnings": []
}
```

**Fields:**

- `analyzed_at` (string, ISO 8601 UTC): Timestamp of analysis
- `monolith_path` (string): Absolute path to analyzed monolith
- `total_endpoints` (integer): Total endpoint count
- `analyzer_version` (string): Version of analyzer script
- `skill_version` (string): Version of Skill 01
- `warnings` (array of strings): Non-fatal warnings during analysis

### Section: `summary`

```json
{
  "total_endpoints": 29,
  "lambda_candidates": 28,
  "fargate_candidates": 0,
  "app_runner_candidates": 0,
  "requires_transformation": 1,
  "critical_blockers": 1,
  "anti_pattern_summary": {
    "AP-token-blacklist": 5,
    "AP-cross-blueprint": 12
  }
}
```

**Fields:**

- `total_endpoints` (integer): Total endpoints analyzed
- `lambda_candidates` (integer): Endpoints recommended for Lambda (without transformation)
- `fargate_candidates` (integer): Endpoints recommended for Fargate
- `app_runner_candidates` (integer): Endpoints recommended for App Runner
- `requires_transformation` (integer): Endpoints needing architectural changes
- `critical_blockers` (integer): Endpoints with critical anti-patterns
- `anti_pattern_summary` (object): Anti-pattern occurrence counts

**Invariants:**

- `I-1`: `total_endpoints == Σ len(m["endpoints"]) ∀m ∈ modules`
- `I-2`: `lambda_candidates + fargate_candidates + app_runner_candidates + requires_transformation == total_endpoints`

### Section: `modules`

Array of module objects:

```json
{
  "name": "auth",
  "url_prefix": "/api/auth",
  "cohesion": "high",
  "isolation": "medium",
  "cross_blueprint_imports": ["auth → clientes"],
  "endpoints": [ /* Array of endpoint objects */ ]
}
```

**Module Fields:**

- `name` (string): Module/blueprint name
- `url_prefix` (string): URL prefix for all module endpoints
- `cohesion` (string): `"high"` | `"medium"` | `"low"`
- `isolation` (string): `"high"` | `"medium"` | `"low"`
- `cross_blueprint_imports` (array of strings): Cross-module dependencies
- `endpoints` (array): Endpoint analysis results

**Endpoint Object:**

```json
{
  "id": "auth.login",
  "method": "POST",
  "path": "/api/auth/login",
  "auth_required": false,
  "admin_required": false,
  "compute_target": "lambda",
  "migration_complexity": "low",
  "requires_architectural_transformation": false,
  "anti_patterns": [ /* Array of anti-pattern matches */ ]
}
```

**Endpoint Fields:**

- `id` (string): Unique identifier `<module>.<function>`
- `method` (string): HTTP method — one of `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`
- `path` (string): Full URL path with parameters as `{param}`
- `auth_required` (boolean): Requires JWT authentication
- `admin_required` (boolean): Requires admin role
- `compute_target` (string): `"lambda"` | `"fargate"` | `"app_runner"`
- `migration_complexity` (string): `"low"` | `"medium"` | `"high"` | `"very_high"`
- `requires_architectural_transformation` (boolean): Needs pattern refactoring
- `anti_patterns` (array): Detected anti-patterns

**Anti-Pattern Object:**

```json
{
  "code": "AP-token-blacklist",
  "description": "Lista negra de tokens JWT almacenada en memoria...",
  "gap_ids": ["GAP-03"],
  "severity": "high",
  "location": "variable '_tokens_revocados' = set() a nivel de módulo"
}
```

### Section: `lambda_layers`

```json
[
  {
    "name": "db-layer",
    "description": "Modelos SQLAlchemy, conexión a RDS Proxy...",
    "consumed_by": ["all_modules"]
  }
]
```

### Section: `migration_sequence`

```json
[
  {
    "phase": 1,
    "module": "servicios",
    "justification": "Menor acoplamiento (isolation=high)...",
    "prerequisites": []
  }
]
```

---

## Python API

### Importing Components

```python
import sys
from pathlib import Path

# Add analyzer to path
sys.path.insert(0, str(Path(__file__).parent / "skills/skill-01-analyzer/scripts"))

from analyze_monolith import (
    BlueprintDiscoverer,
    EndpointExtractor,
    AntiPatternRegistry,
    ComplexityScorer,
    ComputeTargetClassifier,
    ManifestBuilder
)
```

### Component: BlueprintDiscoverer

**Purpose:** Discover Flask blueprints in a monolith.

```python
from pathlib import Path

monolith_path = Path("/path/to/monolith")
discoverer = BlueprintDiscoverer(monolith_path)
blueprints = discoverer.discover()

# blueprints: dict[str, BlueprintInfo]
# BlueprintInfo = TypedDict with keys: prefix, routes_file, module_name, bp_variable
```

**Returns:**

- `dict[str, BlueprintInfo]` — Maps blueprint variable names to their metadata

### Component: EndpointExtractor

**Purpose:** Extract endpoints from a blueprint's routes.py file.

```python
routes_file = Path("/path/to/routes.py")
blueprint_info = blueprints["auth_bp"]

extractor = EndpointExtractor(routes_file, blueprint_info)
endpoints = extractor.extract()

# endpoints: list[EndpointNode]
# EndpointNode has: func_node, method, full_path, auth_required, etc.
```

**Returns:**

- `list[EndpointNode]` — One node per (function, HTTP method) combination

### Component: AntiPatternRegistry

**Purpose:** Detect anti-patterns in a module.

```python
import ast

with open(routes_file, "r") as f:
    source = f.read()
module_tree = ast.parse(source)

registry = AntiPatternRegistry()
result = registry.analyze_module(module_tree, endpoints, "auth")

# result: ModuleAnalysisResult
# Has: endpoint_antipatterns, module_antipatterns, cross_blueprint_imports
```

**Returns:**

- `ModuleAnalysisResult` — Anti-patterns detected per endpoint and module-wide

### Component: ComplexityScorer

**Purpose:** Assign migration complexity to an endpoint.

```python
anti_patterns = result.endpoint_antipatterns.get(endpoint.endpoint_id, [])
complexity = ComplexityScorer.score(endpoint, anti_patterns)

# complexity: "low" | "medium" | "high" | "very_high"
```

### Component: ComputeTargetClassifier

**Purpose:** Classify compute target for an endpoint.

```python
compute_target, requires_transformation = ComputeTargetClassifier.classify(
    endpoint, 
    anti_patterns, 
    all_endpoints_in_module
)

# compute_target: "lambda" | "fargate" | "app_runner"
# requires_transformation: bool
```

### Component: ManifestBuilder

**Purpose:** Build and write the complete manifest.

```python
builder = ManifestBuilder(
    monolith_path=monolith_path,
    blueprints=blueprints,
    endpoints_by_module=endpoints_by_module,
    analysis_by_module=analysis_by_module,
    all_warnings=all_warnings
)

manifest = builder.build()
builder.write(manifest, output_path)
```

---

## Error Codes

### Exit Code 1: MONOLITH_PATH_NOT_FOUND

**Cause:** The `--path` directory doesn't exist.

**Error Output (stderr):**

```json
{
  "error": "MONOLITH_PATH_NOT_FOUND",
  "message": "El directorio '/path/to/monolith' no existe."
}
```

**Resolution:**
- Verify the path is correct
- Check file permissions
- Use absolute path if relative path fails

### Exit Code 2: NO_BLUEPRINTS_FOUND

**Cause:** No Flask blueprints discovered in the directory.

**Error Output (stderr):**

```json
{
  "error": "NO_BLUEPRINTS_FOUND",
  "message": "No se encontraron blueprints Flask en '/path/to/monolith'...",
  "warnings": [
    "BlueprintDiscoverer: no se encontró app/__init__.py...",
    "BlueprintDiscoverer: usando fallback heurístico..."
  ]
}
```

**Resolution:**
- Verify the directory contains a Flask application
- Check for `app/__init__.py` with `register_blueprint` calls
- Ensure blueprint files are named `routes.py`

### Exit Code 3: MANIFEST_WRITE_FAILED

**Cause:** Cannot write manifest file (after fallback to cwd fails).

**Error Output (stderr):**

```json
{
  "error": "MANIFEST_WRITE_FAILED",
  "message": "No se pudo escribir en '/path/output.json' ni en '/fallback/migration-manifest.json'.",
  "primary_exception": "PermissionError: ...",
  "fallback_exception": "PermissionError: ..."
}
```

**Resolution:**
- Check write permissions on output directory
- Specify writable output path with `--output`
- Run with appropriate file system permissions

---

## Anti-Pattern Catalog

### AP-local-filesystem

**Code:** `AP-local-filesystem`  
**Severity:** Critical  
**GAP ID:** GAP-02

**Description:**  
Almacenamiento de archivos en el sistema de archivos local. Incompatible con Lambda's ephemeral storage.

**Detection:**  
- Calls to `archivo.save(path)`
- `os.path.join(UPLOAD_FOLDER, filename)`

**Remediation:**  
Migrate to S3 with presigned URL flow (Skill 04).

---

### AP-strftime-sqlite

**Code:** `AP-strftime-sqlite`  
**Severity:** High  
**GAP ID:** GAP-04

**Description:**  
SQLite-specific `strftime` function calls incompatible with PostgreSQL.

**Detection:**  
- `func.strftime('%Y-%m-%d', column)`

**Remediation:**  
Replace with PostgreSQL `func.to_char(column, 'YYYY-MM-DD')`.

---

### AP-token-blacklist

**Code:** `AP-token-blacklist`  
**Severity:** High  
**GAP ID:** GAP-03

**Description:**  
In-memory token blacklist using `set()`. Incompatible with multi-instance Lambda.

**Detection:**  
- Module-level `_tokens_revocados = set()`
- Calls to `.add()` in route functions

**Remediation:**  
Externalize to DynamoDB with TTL attribute (Skill 03).

---

### AP-session-flask

**Code:** `AP-session-flask`  
**Severity:** Medium  
**GAP ID:** GAP-06

**Description:**  
Flask session usage (`session['key']`) requires server-side session store.

**Detection:**  
- `session['key']` access
- `session.clear()` calls

**Remediation:**  
Migrate to JWT claims or ElastiCache.

---

### AP-cross-blueprint

**Code:** `AP-cross-blueprint`  
**Severity:** High  
**GAP ID:** —

**Description:**  
Direct imports from other blueprint's `routes.py`, creating tight coupling.

**Detection:**  
- `from app.blueprints.<other>.routes import ...`

**Remediation:**  
Refactor shared code into Lambda Layer (Skill 03).

---

### AP-order-num-ts

**Code:** `AP-order-num-ts`  
**Severity:** Medium  
**GAP ID:** GAP-14

**Description:**  
Timestamp-based ID generation without collision handling.

**Detection:**  
- `datetime.utcnow()` used in ID generation
- f-strings with timestamps

**Remediation:**  
Use UUID or DynamoDB auto-increment.

---

### AP-in-memory-singleton

**Code:** `AP-in-memory-singleton`  
**Severity:** Medium  
**GAP ID:** —

**Description:**  
In-memory singleton pattern or module-level caches.

**Detection:**  
- `__new__` method with `cls._instancia`
- Module-level `_cache = {}` or `_historial = []`

**Remediation:**  
Externalize to ElastiCache or DynamoDB.

---

## Examples

### Example 1: Basic Analysis

```bash
$ python analyze_monolith.py --path ./my-flask-app

📂 Analizando monolito en: /home/user/my-flask-app
🔍 Descubriendo blueprints Flask...
  ✓ 3 blueprint(s) descubierto(s): auth_bp, api_bp, admin_bp
📝 Extrayendo endpoints...
  ✓ auth: 4 endpoint(s)
  ✓ api: 8 endpoint(s)
  ✓ admin: 3 endpoint(s)
  Total: 15 endpoint(s) extraídos
🔬 Analizando anti-patrones...
  ⚠ auth: 2 anti-patrón(es) detectado(s)
📦 Construyendo migration-manifest.json...
💾 Escribiendo manifiesto en: /home/user/my-flask-app/migration-manifest.json
✓ Manifiesto escrito

======================================================================
✅ Análisis completado exitosamente
======================================================================
Total de endpoints:          15
  → Lambda:                  14
  → Fargate:                 0
  → App Runner:              1
  → Requiere transformación: 0
Bloqueadores críticos:       0

Anti-patrones detectados:
  • AP-token-blacklist: 2
======================================================================
```

### Example 2: Custom Output Path

```bash
$ python analyze_monolith.py --path ../monolith --output /tmp/manifest.json
```

### Example 3: Error Handling

```bash
$ python analyze_monolith.py --path /nonexistent/path

{
  "error": "MONOLITH_PATH_NOT_FOUND",
  "message": "El directorio '/nonexistent/path' no existe."
}

$ echo $?
1
```

### Example 4: Python API Usage

```python
#!/usr/bin/env python3
from pathlib import Path
from analyze_monolith import BlueprintDiscoverer, EndpointExtractor

# Discover blueprints
monolith = Path("./my-flask-app")
discoverer = BlueprintDiscoverer(monolith)
blueprints = discoverer.discover()

print(f"Found {len(blueprints)} blueprints:")
for bp_var, bp_info in blueprints.items():
    print(f"  • {bp_var}: {bp_info['prefix']}")
    
    # Extract endpoints from this blueprint
    extractor = EndpointExtractor(bp_info["routes_file"], bp_info)
    endpoints = extractor.extract()
    
    print(f"    → {len(endpoints)} endpoints")
    for ep in endpoints:
        print(f"      [{ep.method}] {ep.full_path}")
```

---

## Integration with Skills 02-05

The `migration-manifest.json` produced by this analyzer is consumed by:

- **Skill 02:** Persistence migration (RDS, VPC, migrations)
- **Skill 03:** Strangler Fig orchestration (API Gateway, Lambda Authorizer)
- **Skill 04:** Upload migration (S3, presigned URLs)
- **Skill 05:** Post-generation validation (tests, observability)

---

## Support

**Author:** Luis Gerardo Sánchez Ordóñez  
**Project:** Maestría en Ingeniería de Software — Pontificia Universidad Javeriana Cali  
**Director:** Juan Gabriel Quintero Barbosa (AWS Solutions Architecture)

---

**Last Updated:** 2026-08-28  
**Version:** 1.0.0