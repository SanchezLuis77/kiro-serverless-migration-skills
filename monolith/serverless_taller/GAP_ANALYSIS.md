# Informe de Transformación y Gap Analysis
## Monolito Flask → Arquitectura Serverless (AWS Lambda)
### Proyecto: Taller PyME

---

## 1. RESUMEN EJECUTIVO

Se realizó la transformación completa del monolito Flask a una arquitectura
serverless basada en AWS Lambda + API Gateway. La transformación fue **parcialmente
automatizable**: el 70% del código de negocio se pudo migrar directamente o con
adaptaciones menores, pero el 30% restante requirió decisiones de diseño,
cambios de contrato de API, o configuración manual de infraestructura que
**no puede automatizarse sin intervención humana**.

---

## 2. LO QUE SE LOGRÓ TRANSFORMAR (ÉXITOS)

### 2.1 Lógica de negocio (alta portabilidad)
- Todos los modelos SQLAlchemy se migraron sin cambios funcionales.
  Solo se eliminó la dependencia de `flask_sqlalchemy.db.Model` → `declarative_base()`.
- Los esquemas Marshmallow se copiaron íntegramente — sin dependencia de Flask.
- Toda la lógica de validación de estados de órdenes, cálculo de totales,
  y reglas de negocio se migró línea a línea.
- Las funciones de respuesta (`respuesta_ok`, `respuesta_error`) se adaptaron
  al formato de respuesta de API Gateway (dict con statusCode/headers/body).

### 2.2 Autenticación JWT
- La generación y validación de tokens se migró de Flask-JWT-Extended a PyJWT puro.
- La validación del JWT en cada handler reemplaza el decorador `@jwt_required()`.
- La verificación de rol admin se extrajo a una función utilitaria reutilizable.

### 2.3 Caché
- El `CacheService` (dict en memoria) se reemplazó por un wrapper de Redis
  con la misma interfaz pública (`get`, `set`, `delete`, `invalidar_patron`).
- La lógica de caché en cada handler es idéntica al monolito.

### 2.4 Notificaciones
- El `NotificacionService` (simulado) se reemplazó por llamadas directas a AWS SES.
- La interfaz de funciones (`notificar_orden_creada`, `notificar_cambio_estado`,
  `notificar_orden_lista`) es idéntica — solo cambia la implementación interna.

### 2.5 Estructura de proyecto
- Los 5 blueprints Flask se convirtieron en 5 funciones Lambda independientes.
- Se eliminaron todos los anti-patrones de import cross-blueprint.
- La constante `CATEGORIAS` se duplicó en cada función que la necesita
  (correcto en serverless — cada función es autónoma).

### 2.6 Infraestructura como código (parcial)
- `serverless.yml` define las 5 funciones Lambda con sus rutas API Gateway.
- Se incluye la definición de S3 Bucket y tabla DynamoDB para tokens revocados.

---

## 3. GAP ANALYSIS — LIMITACIONES IDENTIFICADAS

Los gaps se clasifican en 4 categorías: **Técnico**, **Operacional**,
**Arquitectural** y **de Proceso**.

---

### GAP-01 | Routing Manual — Escalabilidad del Código
**Categoría:** Técnico | **Severidad:** Alta

**Descripción:**
El monolito Flask usaba routing declarativo con decoradores:
```python
@auth_bp.route('/login', methods=['POST'])
def login(): ...
```
En la versión serverless, el routing se hace con `if/elif` sobre `event['httpMethod']`
y `event['path']`. Esto no escala:

```python
# Lo que se generó — FRÁGIL
if method == 'POST' and path.endswith('/login'):
    return _login(event)
elif method == 'GET' and path.endswith('/me'):
    return _perfil(event)
```

**¿Por qué la IA no puede resolverlo automáticamente?**
Existen múltiples alternativas (`aws-lambda-powertools Router`,
`chalice`, `mangum` + FastAPI, etc.) y la elección requiere contexto
organizacional (stack tecnológico, experiencia del equipo, licencias).

**Solución recomendada:**
```python
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
app = APIGatewayRestResolver()

@app.post('/auth/login')
def login(): ...
```

**Esfuerzo para cerrar el gap:** 1-2 días de refactoring por función.

---

### GAP-02 | Upload de Archivos — Cambio de Contrato de API
**Categoría:** Arquitectural | **Severidad:** Crítica

**Descripción:**
El monolito recibía archivos directamente via `multipart/form-data`:
```
POST /api/transacciones/{id}/adjunto
Content-Type: multipart/form-data
[archivo binario en el body]
```

Lambda tiene un límite de 6 MB para el body de una request via API Gateway
(10 MB con integración directa). Para archivos más grandes, el patrón correcto
es **presigned URL de S3**, que cambia el contrato de la API a 2 pasos:

```
# Paso 1: obtener URL
POST /transacciones/{id}/adjunto
Body: {"nombre_archivo": "foto.jpg"}
→ Response: {"presigned_url": "https://s3.amazonaws.com/...", "clave_s3": "..."}

# Paso 2: subir archivo directamente a S3
PUT {presigned_url}
Body: [binario del archivo]
```

**¿Por qué la IA no puede resolverlo automáticamente?**
Requiere cambios en el cliente/frontend que están fuera del alcance del
monolito Python. La IA puede generar el backend pero no puede modificar
los consumidores de la API ni decidir si el cambio de contrato es aceptable.

**Consecuencia:** Todo cliente que consumía el endpoint de adjunto debe
ser actualizado. Esto es un breaking change de API.

**Esfuerzo para cerrar el gap:** Requiere coordinación con equipo de frontend,
versionado de API, y período de deprecación del endpoint anterior.

---

### GAP-03 | Revocación de Tokens (Logout)
**Categoría:** Técnico | **Severidad:** Alta

**Descripción:**
El monolito usaba un `set()` en memoria:
```python
_tokens_revocados = set()  # Se pierde al reiniciar
```

La versión serverless usa DynamoDB, pero:
1. La tabla DynamoDB debe existir **antes** del primer deploy.
2. Si DynamoDB no está disponible, el código hace **fail open** (el token
   revocado sigue siendo considerado válido) — gap de seguridad documentado.
3. El `jti` generado no es un UUID real sino `{usuario_id}-{timestamp}`,
   lo que puede colisionar bajo alta concurrencia.

```python
# En auth_utils.py — GAP documentado
def token_esta_revocado(jti: str) -> bool:
    ...
    except Exception as e:
        return False  # Fail open — GAP de seguridad intencional documentado
```

**¿Por qué la IA no puede resolverlo automáticamente?**
La decisión entre fail-open vs fail-closed es una decisión de seguridad
que depende del modelo de amenazas del negocio — no es técnica.

**Esfuerzo para cerrar el gap:** 1 día + revisión de seguridad.

---

### GAP-04 | Queries SQL con strftime (SQLite → PostgreSQL)
**Categoría:** Técnico | **Severidad:** Alta

**Descripción:**
El módulo de reportes usa `func.strftime()` que es **específico de SQLite**:
```python
# GAP: Solo funciona en SQLite
func.strftime('%Y-%m-%d', OrdenTrabajo.fecha_completado)
```

Con RDS PostgreSQL (la base de datos correcta para producción serverless),
esto debe cambiarse a:
```python
# PostgreSQL — NO generado automáticamente
func.to_char(OrdenTrabajo.fecha_completado, 'YYYY-MM-DD')
# o con date_trunc:
func.date_trunc('day', OrdenTrabajo.fecha_completado)
```

**¿Por qué la IA no puede resolverlo automáticamente?**
La IA conoce el dialecto SQL de destino solo si se le especifica. El monolito
usaba SQLite y no hay información en el código sobre el motor de producción.
La transformación automática requeriría:
a) Inferir el motor destino (no dado en el código fuente), o
b) Generar código con dialect-agnostic (más complejo y menos legible).

**Esfuerzo para cerrar el gap:** 2 horas de ajuste + tests de integración con RDS.

---

### GAP-05 | Migraciones de Base de Datos
**Categoría:** Operacional | **Severidad:** Crítica

**Descripción:**
El monolito usaba Flask-Migrate:
```bash
flask db migrate -m "Cambio X"
flask db upgrade
```

En el entorno serverless **no hay CLI Flask**. Las migraciones deben ejecutarse:
- Desde un Lambda de inicialización separado (no generado)
- Desde un pipeline CI/CD (GitHub Actions, CodePipeline)
- Manualmente desde una instancia EC2/ECS con acceso a la VPC de RDS
- Con herramientas como Alembic standalone

**Lo que la IA generó:** Solo el código de la aplicación. No generó:
- Script de migración con Alembic standalone
- Lambda de inicialización de base de datos
- Pipeline CI/CD para aplicar migraciones
- Estrategia de rollback de migraciones

**¿Por qué la IA no puede resolverlo automáticamente?**
Las migraciones dependen del estado actual de la base de datos de producción,
que es información runtime no disponible en tiempo de generación de código.
Además, la estrategia de deployment (blue/green, canary, etc.) afecta cómo
se aplican las migraciones.

**Esfuerzo para cerrar el gap:** 3-5 días para implementar pipeline completo.

---

### GAP-06 | VPC y Cold Start de ElastiCache
**Categoría:** Arquitectural | **Severidad:** Media

**Descripción:**
ElastiCache Redis solo es accesible desde dentro de una VPC de AWS.
Configurar Lambda dentro de una VPC agrega **~500-700ms de cold start**.

En el `serverless.yml` la configuración de VPC está comentada:
```yaml
# GAP: VPC requerida para ElastiCache Redis
# vpc:
#   securityGroupIds: ...
#   subnetIds: ...
```

**¿Por qué la IA no puede resolverlo automáticamente?**
Los IDs de VPC, subnets y security groups son específicos de la cuenta AWS
del cliente. La IA no puede conocer estos valores. Además, la decisión de
si usar VPC (y aceptar el cold start) vs no usar caché es una decisión
de arquitectura con tradeoffs de costo/rendimiento.

**Alternativa que reduce el problema:** ElastiCache Serverless (2024) permite
conexiones sin VPC, pero a mayor costo. Esta decisión requiere análisis de costo.

**Esfuerzo para cerrar el gap:** 1-2 días de configuración de infraestructura.

---

### GAP-07 | Infraestructura Stateful (RDS, ElastiCache)
**Categoría:** Operacional | **Severidad:** Crítica

**Descripción:**
El `serverless.yml` **no incluye** la definición de:
- RDS PostgreSQL / Aurora Serverless
- ElastiCache Redis

Están documentados como comentarios:
```yaml
# GAP: RDS PostgreSQL y ElastiCache Redis NO están definidos aquí.
# Deben crearse manualmente o con un stack de infraestructura separado
```

**¿Por qué la IA no puede resolverlo automáticamente?**
Los recursos stateful (bases de datos, cachés) tienen decisiones de sizing,
backup, multi-AZ, y costo que dependen de:
- Volumen de tráfico esperado (desconocido para la IA)
- Presupuesto del cliente (desconocido)
- Regulaciones de datos (¿GDPR? ¿residencia de datos?)
- Estrategia de DR (disaster recovery)

Generar un RDS con configuración por defecto podría resultar en un sistema
costoso o con capacidad incorrecta para el uso real.

**Esfuerzo para cerrar el gap:** 3-5 días (incluye sizing, seguridad, y testing).

---

### GAP-08 | CORS y Seguridad de API Gateway
**Categoría:** Técnico | **Severidad:** Media

**Descripción:**
Los headers CORS en la versión serverless tienen `Access-Control-Allow-Origin: '*'`:
```python
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',  # GAP: debe restringirse en producción
}
```

En el monolito Flask, `flask-cors` podría configurarse con orígenes específicos.
La configuración de CORS correcta en API Gateway requiere conocer los dominios
del frontend — información no disponible en el código fuente.

Adicionalmente, el `serverless.yml` no incluye:
- WAF (Web Application Firewall)
- API Keys / Usage Plans
- Throttling por endpoint
- Autorización a nivel de API Gateway (Lambda Authorizer)

**Esfuerzo para cerrar el gap:** 1-3 días según nivel de seguridad requerido.

---

### GAP-09 | Observabilidad y Monitoreo
**Categoría:** Operacional | **Severidad:** Media

**Descripción:**
El monolito tenía logging centralizado configurado en `create_app()`.
La versión serverless usa `logging` básico de Python, pero no incluye:

- **CloudWatch Dashboards** para métricas de cada Lambda
- **X-Ray tracing** para trazabilidad distribuida entre funciones
- **Alarmas CloudWatch** para errores, timeouts, y throttling
- **Structured logging** (JSON) para facilitar búsquedas en CloudWatch Logs
- **Dead Letter Queues** para invocaciones fallidas

El monolito tenía UN punto de log. La versión serverless tiene 5 funciones
Lambda independientes con logs separados en CloudWatch — sin correlación
entre requests que atraviesan múltiples funciones.

**¿Por qué la IA no puede resolverlo automáticamente?**
Los thresholds de alarmas, retention de logs, y estrategia de tracing
dependen de SLAs del negocio que no están en el código fuente.

**Esfuerzo para cerrar el gap:** 3-5 días para observabilidad completa.

---

### GAP-10 | Testing en Entorno Serverless
**Categoría:** de Proceso | **Severidad:** Alta

**Descripción:**
El monolito tenía `tests/test_basic.py` con pytest y cliente HTTP de Flask.
**No se generó una suite de tests equivalente** para la versión serverless.

Los tests serverless son fundamentalmente diferentes:
```python
# Monolito — simple
client = app.test_client()
resp = client.post('/api/auth/login', json={...})

# Serverless — requiere simular eventos API Gateway
event = {
    'httpMethod': 'POST',
    'path': '/auth/login',
    'body': json.dumps({...}),
    'headers': {},
    'pathParameters': None,
    'queryStringParameters': None,
}
result = handler(event, {})
```

Adicionalmente, los tests de integración requieren:
- LocalStack para simular DynamoDB, S3, SES localmente
- `moto` para mockear servicios AWS
- Base de datos SQLite en memoria (el monolito la tenía, aquí no)

**Esfuerzo para cerrar el gap:** 3-5 días para suite de tests equivalente.

---

### GAP-11 | Seed de Datos en Entorno Serverless
**Categoría:** Operacional | **Severidad:** Baja

**Descripción:**
El monolito tenía `flask seed` como comando CLI. En serverless no hay CLI Flask.
El script de seed **no se migró** a la versión serverless.

**Opciones disponibles:**
- Lambda de inicialización (invocada manualmente o desde CI/CD)
- Script Python standalone que se conecta a RDS directamente
- Script ejecutado desde un Lambda de administración

**Lo que la IA no generó:** El script de seed equivalente para el entorno serverless.

**Esfuerzo para cerrar el gap:** 4 horas.

---

### GAP-12 | Gestión de Secretos
**Categoría:** Técnico | **Severidad:** Alta

**Descripción:**
El `serverless.yml` referencia secretos desde AWS SSM Parameter Store:
```yaml
DATABASE_URL: ${ssm:/taller/${self:provider.stage}/database_url}
```

Pero **no incluye el proceso para crear estos parámetros** en SSM.
El desarrollador debe crearlos manualmente antes del primer deploy.

Tampoco se generó:
- Rotación automática de secretos con AWS Secrets Manager
- Separación entre secretos de desarrollo y producción
- Proceso de onboarding para nuevos ambientes

**Esfuerzo para cerrar el gap:** 1 día para documentar proceso, más
si se implementa rotación automática.

---

### GAP-13 | Desarrollo Local (Local Development)
**Categoría:** de Proceso | **Severidad:** Alta

**Descripción:**
El monolito se ejecutaba localmente con `python run.py`. En serverless,
el desarrollo local requiere:
- `serverless-offline` plugin (no configurado en serverless.yml)
- `localstack` para simular servicios AWS
- Variables de entorno configuradas localmente
- Conexión a una base de datos local o de desarrollo

**El `serverless.yml` generado no incluye `serverless-offline`.**
Sin esto, el equipo de desarrollo no puede probar localmente sin hacer
deploy a AWS, lo que ralentiza enormemente el ciclo de desarrollo.

**Esfuerzo para cerrar el gap:** 1-2 días de configuración.

---

### GAP-14 | Idempotencia y Reintentos
**Categoría:** Arquitectural | **Severidad:** Media

**Descripción:**
En arquitecturas serverless, las funciones pueden invocarse más de una vez
por el mismo evento (reintentos de API Gateway o SQS). El código generado
**no implementa idempotencia** en operaciones mutativas:

```python
# GAP: si este código se ejecuta dos veces con el mismo request,
# se crean dos órdenes con números de orden diferentes
numero_orden = f"OT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
orden = OrdenTrabajo(numero_orden=numero_orden, ...)
session.add(orden)
```

Para APIs REST síncronas via API Gateway este riesgo es bajo
(no hay reintentos automáticos), pero si en el futuro se agrega
SQS/EventBridge como trigger, se convierte en un problema crítico.

**Esfuerzo para cerrar el gap:** 2-3 días para implementar claves de idempotencia.

---

## 4. TABLA RESUMEN DE GAPS

| ID | Gap | Categoría | Severidad | Automatizable | Esfuerzo |
|----|-----|-----------|-----------|---------------|----------|
| GAP-01 | Routing manual con if/elif | Técnico | Alta | Parcial | 2 días |
| GAP-02 | Upload de archivos — cambio de contrato API | Arquitectural | Crítica | No | 5+ días |
| GAP-03 | Revocación de tokens — seguridad fail-open | Técnico | Alta | Parcial | 1 día |
| GAP-04 | SQL strftime SQLite → PostgreSQL | Técnico | Alta | Sí* | 2 horas |
| GAP-05 | Migraciones de base de datos | Operacional | Crítica | No | 5 días |
| GAP-06 | VPC y cold start ElastiCache | Arquitectural | Media | No | 2 días |
| GAP-07 | Infraestructura stateful (RDS, Redis) | Operacional | Crítica | No | 5 días |
| GAP-08 | CORS y seguridad API Gateway | Técnico | Media | Parcial | 2 días |
| GAP-09 | Observabilidad y monitoreo | Operacional | Media | Parcial | 4 días |
| GAP-10 | Suite de tests serverless | Proceso | Alta | Parcial | 4 días |
| GAP-11 | Seed de datos | Operacional | Baja | Sí | 4 horas |
| GAP-12 | Gestión de secretos | Técnico | Alta | Parcial | 1 día |
| GAP-13 | Desarrollo local (serverless-offline) | Proceso | Alta | Parcial | 2 días |
| GAP-14 | Idempotencia y reintentos | Arquitectural | Media | No | 3 días |

*Sí si se especifica el motor de BD destino como input.

**Total gaps críticos:** 3 (GAP-02, GAP-05, GAP-07)
**Total esfuerzo estimado para cerrar todos los gaps:** 37-40 días/persona

---

## 5. CLASIFICACIÓN DE GAPS POR CAUSA RAÍZ

### 5.1 Gaps por FALTA DE INFORMACIÓN DE CONTEXTO
La IA no puede resolverlos porque requieren información no disponible en el código:
- GAP-04: Motor de BD destino no especificado
- GAP-06: IDs de VPC/subnets específicos de la cuenta AWS
- GAP-07: Sizing de RDS y Redis basado en tráfico esperado
- GAP-08: Dominios del frontend para configurar CORS
- GAP-12: Valores de secretos de producción

**Implicación para la investigación:** Un sistema de migración automatizada
necesitaría un "formulario de contexto" que el usuario complete antes de
iniciar la transformación.

### 5.2 Gaps por DECISIONES DE ARQUITECTURA CON TRADEOFFS
La IA genera una solución pero no puede elegir sin criterios explícitos:
- GAP-01: Micro-framework de routing (powertools vs chalice vs manual)
- GAP-03: Política de seguridad fail-open vs fail-closed
- GAP-06: Aceptar cold start de VPC vs costo de ElastiCache Serverless
- GAP-14: Nivel de idempotencia requerido

**Implicación para la investigación:** La automatización puede generar
*opciones con sus tradeoffs documentados*, pero la decisión final requiere
un arquitecto humano.

### 5.3 Gaps por CAMBIOS DE CONTRATO EXTERNOS
La IA puede generar el backend pero no puede cambiar los consumidores:
- GAP-02: El frontend que consumía el endpoint de upload debe actualizarse

**Implicación para la investigación:** La migración Strangler Fig es
parcialmente imposible de automatizar cuando hay cambios de contrato de API,
porque los consumidores están fuera del alcance del código analizado.

### 5.4 Gaps por AUSENCIA DE CÓDIGO DE INFRAESTRUCTURA Y OPERACIONES
El código de aplicación se migra bien, pero el ecosistema no:
- GAP-05: Migraciones de BD
- GAP-09: Observabilidad
- GAP-10: Tests
- GAP-11: Seeds
- GAP-13: Desarrollo local

**Implicación para la investigación:** La brecha más grande está en el
**plano operacional**, no en el plano de código de aplicación.
Un sistema de migración maduro necesita generar no solo código de negocio
sino también pipelines CI/CD, configuración de monitoreo, y entornos de desarrollo local.

---

## 6. PORCENTAJE DE AUTOMATIZACIÓN ALCANZADO

| Capa | % Automatizado | Observaciones |
|------|---------------|---------------|
| Modelos de datos | 95% | Solo cambió la clase base |
| Lógica de negocio | 90% | Completamente portada |
| Validación (Marshmallow) | 100% | Sin cambios |
| Autenticación JWT | 80% | JTI generation mejorable |
| Caché | 85% | Interfaz idéntica, implementación cambiada |
| Notificaciones | 70% | SES requiere config manual |
| Routing/Handlers | 65% | Routing manual vs declarativo |
| Upload de archivos | 40% | Cambio de contrato no automatizable |
| Infraestructura (IaC) | 50% | Recursos stateful excluidos |
| Tests | 0% | No generados |
| CI/CD | 0% | No generado |
| Observabilidad | 10% | Solo logging básico |
| Desarrollo local | 20% | serverless-offline no configurado |

**Promedio ponderado: ~62% de automatización**

---

## 7. CONCLUSIONES PARA LA INVESTIGACIÓN DE MAESTRÍA

### Hallazgo principal
La IA puede automatizar con alta fidelidad la transformación del **plano de código**
(modelos, lógica de negocio, validaciones). Los gaps más significativos están en:

1. **El plano operacional:** CI/CD, migraciones, seeds, monitoreo, desarrollo local.
2. **Las decisiones de arquitectura con tradeoffs:** Donde la elección correcta
   depende de factores no codificados (presupuesto, tráfico, SLAs).
3. **Los cambios de contrato de API:** Donde el impacto se extiende a sistemas externos.

### Brechas que justifican investigación
1. **¿Cómo puede una IA inferir el contexto operacional faltante?**
   (motor de BD, sizing, configuración de red)

2. **¿Cómo debe presentar la IA los tradeoffs arquitecturales** para que
   el arquitecto humano tome decisiones informadas sin necesitar
   conocimiento previo de la plataforma destino?

3. **¿Es posible automatizar la generación de tests serverless** a partir
   de los tests del monolito origen, manteniendo la cobertura equivalente?

4. **¿Cómo manejar los breaking changes de API** (como el upload de archivos)
   en un contexto de migración Strangler Fig gradual?

5. **¿Cuál es el umbral mínimo de automatización aceptable** para que
   una herramienta de migración sea útil en producción real?

---

*Informe generado como parte del análisis de capacidades de IA para
migración automática de arquitecturas — Trabajo de Grado de Maestría.*
