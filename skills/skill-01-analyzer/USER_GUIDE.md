# User Guide — Skill 01: Analizador de Monolito

**Version:** 1.0.0  
**Audience:** Developers, DevOps Engineers, Solutions Architects

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Usage Scenarios](#usage-scenarios)
4. [Understanding the Output](#understanding-the-output)
5. [Troubleshooting](#troubleshooting)
6. [Best Practices](#best-practices)
7. [FAQ](#faq)

---

## Introduction

### What is the Analizador de Monolito?

The **Analizador de Monolito** (Monolith Analyzer) is an intelligent static analysis tool that examines your Flask monolithic application and generates a comprehensive migration plan for AWS serverless architectures.

### What does it do?

- 🔍 **Discovers** all API endpoints in your Flask application
- 🎯 **Recommends** AWS compute targets (Lambda, Fargate, App Runner) per endpoint
- ⚠️ **Detects** anti-patterns that block serverless migration
- 📊 **Classifies** migration complexity for each endpoint
- 🗺️ **Generates** a phased migration sequence using Strangler Fig pattern
- 📦 **Suggests** Lambda Layer architecture for shared code

### Why use it?

Manual migration planning is time-consuming and error-prone. This tool:
- ✅ Saves weeks of analysis work
- ✅ Catches migration blockers early
- ✅ Provides actionable recommendations
- ✅ Enables incremental migration strategy
- ✅ Works without external dependencies (privacy-first)

---

## Getting Started

### Prerequisites

- **Python:** 3.9 or higher
- **Operating System:** Windows, macOS, or Linux
- **Flask Monolith:** Using blueprint-based architecture

### Installation

No installation required! The analyzer is a single Python script using only standard library.

### Verifying Your Monolith Structure

The analyzer works best with Flask applications organized like this:

```
my-flask-app/
├── app/
│   ├── __init__.py          # Contains register_blueprint calls
│   └── blueprints/
│       ├── auth/
│       │   ├── __init__.py
│       │   └── routes.py    # Blueprint routes
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py
│       └── ...
├── requirements.txt
└── run.py
```

**Key requirements:**
- Blueprints registered in `app/__init__.py`
- Route definitions in `routes.py` files
- Decorators: `@bp.route(...)`, `@jwt_required()`, etc.

---

## Usage Scenarios

### Scenario 1: First-Time Analysis

**Goal:** Get an initial migration assessment.

```bash
# Navigate to analyzer directory
cd skills/skill-01-analyzer/scripts

# Run analyzer
python analyze_monolith.py --path /path/to/your/flask-app
```

**What happens:**
1. Analyzer discovers all blueprints
2. Extracts all endpoints with metadata
3. Detects anti-patterns
4. Classifies compute targets
5. Generates `migration-manifest.json` in your app directory

**Time:** ~1-5 seconds for typical applications

---

### Scenario 2: Reviewing Migration Blockers

**Goal:** Identify critical issues before migration.

```bash
python analyze_monolith.py --path ../monolith
```

**After analysis, check:**

```bash
# View summary in console output (last section)
# Or open the manifest
cat ../monolith/migration-manifest.json | jq '.summary.anti_pattern_summary'
```

**Look for:**
- `critical_blockers`: Count of endpoints with critical anti-patterns
- Anti-patterns with severity "critical" (e.g., `AP-local-filesystem`)

**Example output:**
```json
{
  "AP-local-filesystem": 1,
  "AP-token-blacklist": 3
}
```

**Action:** Address critical anti-patterns first (see [Anti-Pattern Guide](#anti-pattern-remediation-guide)).

---

### Scenario 3: Planning Migration Phases

**Goal:** Determine migration order.

```bash
python analyze_monolith.py --path ../monolith
```

**Review the `migration_sequence` section:**

```bash
cat ../monolith/migration-manifest.json | jq '.migration_sequence'
```

**Example:**
```json
[
  {
    "phase": 1,
    "module": "servicios",
    "justification": "Menor acoplamiento (isolation=high)...",
    "prerequisites": []
  },
  {
    "phase": 2,
    "module": "auth",
    "justification": "Establece el autorizador Lambda compartido...",
    "prerequisites": ["Completar Fase 1"]
  }
]
```

**Use this to:**
- Schedule migration sprints
- Communicate timeline to stakeholders
- Identify dependencies between modules

---

### Scenario 4: Comparing Before/After Refactoring

**Goal:** Measure improvement after fixing anti-patterns.

```bash
# Before refactoring
python analyze_monolith.py --path ../monolith --output before.json

# ... make code changes ...

# After refactoring
python analyze_monolith.py --path ../monolith --output after.json

# Compare
diff <(jq '.summary' before.json) <(jq '.summary' after.json)
```

**Metrics to track:**
- `critical_blockers` count (should decrease)
- Anti-pattern occurrences
- Migration complexity distribution

---

### Scenario 5: CI/CD Integration

**Goal:** Automatically validate migration readiness in CI pipeline.

**`.github/workflows/migration-check.yml`:**

```yaml
name: Migration Readiness Check

on: [pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Analyze Monolith
        run: |
          python skills/skill-01-analyzer/scripts/analyze_monolith.py \
            --path ./monolith \
            --output migration-manifest.json
      
      - name: Check for Critical Blockers
        run: |
          BLOCKERS=$(jq '.summary.critical_blockers' migration-manifest.json)
          if [ "$BLOCKERS" -gt 0 ]; then
            echo "❌ Found $BLOCKERS critical migration blocker(s)"
            exit 1
          fi
          echo "✅ No critical blockers"
```

---

## Understanding the Output

### Console Output

The analyzer provides real-time progress updates:

```
📂 Analizando monolito en: /path/to/app
🔍 Descubriendo blueprints Flask...
  ✓ 5 blueprint(s) descubierto(s): auth_bp, clientes_bp, servicios_bp...
📝 Extrayendo endpoints...
  ✓ auth: 5 endpoint(s)
  ✓ clientes: 6 endpoint(s)
  Total: 29 endpoint(s) extraídos
🔬 Analizando anti-patrones...
  ⚠ auth: 5 anti-patrón(es) detectado(s)
📦 Construyendo migration-manifest.json...
💾 Escribiendo manifiesto en: /path/migration-manifest.json
✓ Manifiesto escrito

======================================================================
✅ Análisis completado exitosamente
======================================================================
Total de endpoints:          29
  → Lambda:                  29
  → Fargate:                 0
  → App Runner:              0
  → Requiere transformación: 0
Bloqueadores críticos:       0

Anti-patrones detectados:
  • AP-token-blacklist: 5
  • AP-cross-blueprint: 12
======================================================================
```

### Manifest File Structure

#### Top-Level Sections

1. **`metadata`** — Analysis information
2. **`summary`** — Aggregated metrics
3. **`modules`** — Per-module analysis
4. **`lambda_layers`** — Recommended shared layers
5. **`migration_sequence`** — Phased migration plan

#### Key Metrics to Review

**In `summary`:**

| Metric | Meaning | What to Look For |
|--------|---------|------------------|
| `total_endpoints` | Total API endpoints | Should match your API |
| `lambda_candidates` | Ready for Lambda | Higher is better |
| `requires_transformation` | Needs architecture changes | Lower is better |
| `critical_blockers` | Must-fix issues | Should be 0 |

**In each `module`:**

| Field | Meaning | Values |
|-------|---------|--------|
| `cohesion` | Module focus | `high`, `medium`, `low` |
| `isolation` | Module independence | `high`, `medium`, `low` |
| `cross_blueprint_imports` | Coupling count | Fewer is better |

**In each `endpoint`:**

| Field | Meaning | Values |
|-------|---------|--------|
| `compute_target` | AWS service | `lambda`, `fargate`, `app_runner` |
| `migration_complexity` | Effort level | `low`, `medium`, `high`, `very_high` |
| `requires_architectural_transformation` | Needs refactoring | `true`, `false` |

---

## Troubleshooting

### Issue: "No blueprints found"

**Symptoms:**
```json
{
  "error": "NO_BLUEPRINTS_FOUND",
  "message": "No se encontraron blueprints Flask..."
}
```

**Causes:**
1. Not a Flask application
2. No `app/__init__.py` file
3. Blueprints not registered
4. Different directory structure

**Solutions:**
1. Verify `app/__init__.py` contains:
   ```python
   app.register_blueprint(my_bp, url_prefix='/api/...')
   ```

2. Check blueprint files are named `routes.py`

3. If using custom structure, ensure:
   - Blueprint variables are declared: `bp = Blueprint(...)`
   - Route decorators use `@bp.route(...)`

---

### Issue: "Path not found"

**Symptoms:**
```json
{
  "error": "MONOLITH_PATH_NOT_FOUND",
  "message": "El directorio '/path' no existe."
}
```

**Solutions:**
1. Use absolute path: `--path /full/path/to/app`
2. Verify directory exists: `ls -la /path/to/app`
3. Check permissions: `ls -ld /path/to/app`

---

### Issue: "Analysis is slow"

**Expected:** 1-5 seconds for typical apps  
**If slower:**

**Causes:**
- Very large monolith (100+ files)
- Network-mounted filesystem
- Antivirus scanning

**Solutions:**
1. Exclude analyzer from antivirus scans
2. Copy monolith to local disk
3. Check for syntax errors slowing fallback parsing

---

### Issue: "Missing anti-patterns"

**Symptoms:** You know there's a file upload but `AP-local-filesystem` isn't detected.

**Causes:**
- Non-standard code patterns
- Complex AST structure

**Diagnostic steps:**
1. Check if the endpoint appears in the manifest
2. Verify the function contains expected pattern:
   ```python
   archivo.save(ruta)
   # or
   os.path.join(UPLOAD_FOLDER, filename)
   ```

3. If using custom wrappers, detector may miss it

**Workaround:**
- Manually add to manifest
- Refactor to standard pattern before migration

---

### Issue: "Wrong module order in migration_sequence"

**Symptoms:** Migration sequence doesn't match your knowledge of dependencies.

**Cause:** Analyzer uses heuristics based on:
- Cross-blueprint imports
- Cohesion scores
- Anti-pattern severity

**Solution:**
- Manually reorder phases in manifest
- Document custom justifications
- Feed corrections back to analyzer (future enhancement)

---

## Best Practices

### Before Analysis

1. ✅ **Clean your codebase**
   - Remove commented code
   - Fix syntax errors
   - Update to latest Flask conventions

2. ✅ **Document custom patterns**
   - Note any custom auth mechanisms
   - List non-standard decorators
   - Document architectural decisions

3. ✅ **Run tests**
   - Ensure application works
   - Fix known bugs
   - Verify all endpoints are reachable

### During Analysis

1. ✅ **Review console output**
   - Check module count matches expectations
   - Verify endpoint count is correct
   - Note any warnings

2. ✅ **Save the output**
   ```bash
   python analyze_monolith.py --path ../monolith 2>&1 | tee analysis.log
   ```

3. ✅ **Version control the manifest**
   ```bash
   git add migration-manifest.json
   git commit -m "chore: add migration manifest"
   ```

### After Analysis

1. ✅ **Review with team**
   - Share manifest with architects
   - Discuss anti-pattern remediation
   - Validate migration phases

2. ✅ **Create remediation tickets**
   - One ticket per critical anti-pattern
   - Prioritize by migration phase
   - Assign clear owners

3. ✅ **Update documentation**
   - Link manifest in README
   - Document architecture decisions
   - Create migration runbook

### Periodic Re-Analysis

Run analyzer regularly to track progress:

```bash
# Weekly during active development
python analyze_monolith.py --path ../monolith --output "manifest-$(date +%Y%m%d).json"

# After major refactorings
python analyze_monolith.py --path ../monolith
```

---

## Anti-Pattern Remediation Guide

### Priority 1: Critical Blockers

#### AP-local-filesystem

**Impact:** Lambda has ephemeral storage; uploaded files are lost.

**Remediation:**
1. Migrate to S3 bucket
2. Implement presigned URL flow:
   ```python
   # Before: archivo.save(local_path)
   
   # After:
   url = generate_presigned_post(bucket, key)
   return {'upload_url': url}  # Client uploads directly
   ```

3. Use Skill 04 for automated generation

**Timeline:** 2-5 days per endpoint

---

#### AP-token-blacklist

**Impact:** Multi-instance Lambda can't share in-memory set.

**Remediation:**
1. Create DynamoDB table: `token-blacklist`
2. Add TTL attribute matching JWT expiry
3. Replace `set()` with DynamoDB calls:
   ```python
   # Before: _tokens_revocados.add(jti)
   
   # After:
   dynamodb.put_item(
       TableName='token-blacklist',
       Item={'jti': jti, 'ttl': expiry_timestamp}
   )
   ```

4. Use Skill 03 for automated generation

**Timeline:** 1-2 days

---

### Priority 2: High Severity

#### AP-strftime-sqlite

**Impact:** PostgreSQL doesn't support SQLite's `strftime`.

**Remediation:**
```python
# Before (SQLite):
func.strftime('%Y-%m-%d', OrdenTrabajo.created_at)

# After (PostgreSQL):
func.to_char(OrdenTrabajo.created_at, 'YYYY-MM-DD')
```

**Timeline:** <1 day (search & replace)

---

#### AP-cross-blueprint

**Impact:** Tight coupling prevents independent deployment.

**Remediation:**
1. Move shared functions to `app/utils/`
2. Package as Lambda Layer
3. Update imports:
   ```python
   # Before:
   from app.blueprints.clientes.routes import verificar_cliente_existe
   
   # After:
   from app.utils.validation import verificar_cliente_existe
   ```

**Timeline:** 2-3 days per dependency

---

### Priority 3: Medium Severity

#### AP-session-flask

**Impact:** Lambda is stateless; session won't persist.

**Remediation:**
1. Move to JWT claims: `get_jwt()['user_id']`
2. Or use ElastiCache for session store
3. Update code:
   ```python
   # Before: session['user_id'] = user.id
   
   # After: Include in JWT at login
   access_token = create_access_token(
       identity=user.id,
       additional_claims={'user_id': user.id}
   )
   ```

**Timeline:** 1-2 days

---

## FAQ

### Q: Does the analyzer execute my code?

**A:** No. It uses AST (Abstract Syntax Tree) parsing to analyze code structure without execution. This is safe and privacy-preserving.

---

### Q: What Flask versions are supported?

**A:** Flask 2.x and 3.x with blueprint-based architecture. Tested on Flask 2.3.3.

---

### Q: Can I use this with Django or FastAPI?

**A:** No, currently Flask-only. The analyzer looks for Flask-specific patterns (`@bp.route`, `@jwt_required`, etc.).

---

### Q: How accurate is the compute target recommendation?

**A:** The classifier uses heuristics based on:
- Request/response patterns
- Execution duration estimates
- State requirements

Review recommendations and adjust based on:
- Your SLA requirements
- Cost optimization goals
- Operational preferences

---

### Q: What if I disagree with the migration_sequence?

**A:** The sequence is a recommendation. You can:
1. Manually reorder modules in manifest
2. Migrate modules in parallel if truly independent
3. Override based on business priorities

---

### Q: How often should I re-analyze?

**A:** 
- **Weekly** during active refactoring
- **Before each migration phase**
- **After major dependency changes**
- **When adding new modules**

---

### Q: Can I extend the anti-pattern detectors?

**A:** Yes! The detector architecture is modular:

1. Create new detector class:
   ```python
   class MyCustomDetector:
       CODE = "AP-my-pattern"
       
       def detect(self, func_node):
           # Your AST logic here
           pass
   ```

2. Add to `AntiPatternRegistry.FUNCTION_DETECTORS`

3. Update catalog in manifest builder

---

### Q: What about microservices architectures?

**A:** If your app is already microservices, analyze each service separately:

```bash
for service in services/*; do
  python analyze_monolith.py --path "$service" --output "${service}/manifest.json"
done
```

---

### Q: How do I integrate with Kiro IDE?

**A:** The manifest format follows Kiro Skill standards. Future Kiro versions will:
1. Auto-discover Skills in `~/.kiro/skills/`
2. Provide UI for manifest review
3. Trigger downstream Skills (02-05) automatically

---

## Next Steps

After generating your manifest:

1. ✅ **Review with team** — Validate findings
2. ✅ **Remediate critical anti-patterns** — Use guides above
3. ✅ **Use Skill 02** — Generate persistence infrastructure
4. ✅ **Use Skill 03** — Generate Strangler Fig orchestration
5. ✅ **Use Skill 04** — Migrate file uploads
6. ✅ **Use Skill 05** — Validate generated code

---

## Support & Feedback

**Project:** Maestría en Ingeniería de Software  
**Institution:** Pontificia Universidad Javeriana Cali  
**Author:** Luis Gerardo Sánchez Ordóñez  
**Director:** Juan Gabriel Quintero Barbosa

For issues or questions:
1. Check [Troubleshooting](#troubleshooting)
2. Review [API Documentation](./API_DOCUMENTATION.md)
3. Consult [Validation Report](./VALIDATION_REPORT.md)

---

**Last Updated:** 2026-08-28  
**Version:** 1.0.0  
**License:** MIT (for academic research)