# Monolito de Referencia — Taller PyME API

## Ubicación
`monolith/` — Flask 2.3.3, SQLAlchemy, SQLite (dev) → PostgreSQL (prod)

## Arquitectura del Monolito

### Stack técnico
- **Framework:** Flask 2.3.3 con blueprints
- **ORM:** Flask-SQLAlchemy 3.1.1 + Flask-Migrate 4.0.5
- **Auth:** Flask-JWT-Extended 4.5.3 (tokens + blacklist en memoria)
- **Validación:** Marshmallow 3.20.1
- **BD:** SQLite (desarrollo) → target: PostgreSQL/Aurora Serverless v2

### Módulos y endpoints (29 total)

| Módulo | Endpoints | Auth | Anti-patrones |
|--------|-----------|------|---------------|
| auth | 5 | JWT / público | Blacklist en memoria (`set()`) |
| clientes | 6 | JWT | Ninguno |
| servicios | 6 | JWT / público | Cache en memoria |
| transacciones | 7 | JWT | Upload filesystem local, SQL strftime |
| reportes | 5 | JWT admin | strftime SQLite-específico |

### Modelos de datos (4 tablas)
- `Usuario` — id, nombre, apellido, email, password_hash, rol (tecnico/admin), activo
- `Cliente` — id, nombre, apellido, telefono, email, direccion, documento_identidad, activo
- `Servicio` — id, nombre, precio_base, descripcion, tiempo_estimado_horas, categoria, activo
- `OrdenTrabajo` — id, numero_orden, cliente_id, tecnico_id, estado, descripcion_problema, tipo/marca/modelo_equipo, fecha_*, notas_tecnico, total
- `DetalleOrden` (relación) — orden_id, servicio_id, precio_unitario, cantidad, notas

## Gaps Documentados (Baseline = 62% automatización)

### Gaps CRÍTICOS (bloquean deploy)
| ID | Gap | Causa raíz | Esfuerzo |
|----|-----|-----------|----------|
| GAP-02 | Upload archivos → cambio contrato API (filesystem → S3 presigned URL) | Cambio contrato externo | 5+ días |
| GAP-05 | Migraciones de BD — sin CLI Flask en serverless | Ausencia IaC operacional | 5 días |
| GAP-07 | RDS + ElastiCache no definidos en IaC | Falta contexto de sizing | 5 días |

### Gaps de Alta Severidad
| ID | Gap | Causa raíz |
|----|-----|-----------|
| GAP-01 | Routing manual if/elif (no escalable) | Decisión arquitectural |
| GAP-03 | Revocación tokens fail-open (DynamoDB) | Decisión de seguridad |
| GAP-04 | `strftime` SQLite → PostgreSQL `to_char` | Falta info motor destino |
| GAP-10 | Sin suite de tests serverless | Ausencia código operacional |
| GAP-12 | Gestión de secretos SSM sin proceso | Ausencia IaC operacional |
| GAP-13 | Sin serverless-offline para desarrollo local | Ausencia código operacional |

### Gaps de Severidad Media
GAP-06 (VPC cold start), GAP-08 (CORS producción), GAP-09 (observabilidad), GAP-14 (idempotencia)

### Gaps de Baja Severidad
GAP-11 (seed de datos serverless)

## Resultado del Experimento Previo con Kiro (sin Skills)

| Capa | % Automatizado |
|------|---------------|
| Modelos de datos | 95% |
| Lógica de negocio | 90% |
| Autenticación JWT | 80% |
| Routing/Handlers | 65% |
| Upload de archivos | 40% |
| Infraestructura IaC | 50% |
| Tests | 0% |
| CI/CD | 0% |
| Observabilidad | 10% |
| **Promedio ponderado** | **~62%** |

## Archivos Clave del Monolito

```
monolith/
├── app/__init__.py          # create_app(), registro de blueprints
├── app/config.py            # Configuración por ambiente
├── app/extensions.py        # db, jwt, bcrypt, migrate
├── app/models/              # SQLAlchemy models
├── app/blueprints/          # 5 blueprints Flask
├── app/services/            # cache_service, notificacion_service
├── serverless_taller/       # Output de Kiro sin Skills (baseline)
│   ├── GAP_ANALYSIS.md      # Análisis completo de brechas
│   ├── serverless.yml       # IaC parcial (sin RDS, sin ElastiCache)
│   └── functions/           # 5 Lambdas generadas
└── endpoints.md             # Documentación completa de la API
```
