---
name: "strangler-fig-orchestrator"
version: "1.0.0"
description: "Genera la infraestructura de orquestación Strangler Fig (API Gateway + Lambda Authorizer + DynamoDB token blacklist) para gestionar la coexistencia entre el monolito Flask y las funciones Lambda migradas, consumiendo el migration-manifest.json del Skill 01."
author: "Luis Gerardo Sánchez Ordóñez"
tags: ["aws", "serverless", "api-gateway", "strangler-fig", "lambda-authorizer", "jwt", "dynamodb"]
triggers:
  - "generar api gateway"
  - "orquestador strangler fig"
  - "migrar gradualmente"
  - "coexistencia monolito lambda"
  - "generate api gateway"
  - "strangler fig pattern"
---

# Skill 03 — Orquestador Strangler Fig

## Cuándo activar este Skill

Activa este Skill cuando el desarrollador necesite alguna de las siguientes acciones:

- Generar la infraestructura de orquestación para coexistencia monolito-serverless
- Crear Amazon API Gateway con routing inteligente (fase por fase según Strangler Fig)
- Implementar Lambda Authorizer para validación JWT centralizada
- Migrar el token blacklist de memoria (Python `set()`) a DynamoDB
- Resolver el anti-patrón **AP-token-blacklist** (GAP-03)
- Generar reglas de enrutamiento por fase de migración
- Configurar VPC Link para acceso al monolito desde API Gateway

**Palabras clave que activan este Skill:** "api gateway", "strangler fig", "coexistencia", "routing", "authorizer", "jwt", "token blacklist", "migración gradual", "api orchestration"

---

## Instrucciones para el agente

Sigue estos pasos en orden cuando se active el Skill:

### Paso 1 — Validar prerrequisitos

Verifica que existen los siguientes archivos/outputs:

1. **migration-manifest.json** — Generado por Skill 01
2. **Outputs de Skill 02:**
   - VPCId (Export: `taller-VPCId`)
   - SubnetIds (Exports: `taller-PrivateSubnet1`, `taller-PrivateSubnet2`)
   - DBProxyEndpoint (Export: `taller-DBProxyEndpoint`)
   - DBSecretArn (Export: `taller-DBSecretArn`)

Si faltan, informa al usuario:
```
⚠️ Prerrequisito faltante: <output>
Este Skill requiere que ejecutes primero:
  - Skill 01 (Analizador de Monolito)
  - Skill 02 (Migrador de Persistencia)
```

### Paso 2 — Ejecutar el generador de orquestación

Ejecuta el script desde la raíz del workspace:

```bash
python skills/skill-03-strangler/scripts/generate_strangler.py --manifest <ruta_manifest>
```

Parámetros opcionales:
- `--output <directorio>`: Directorio de salida (default: `./serverless-output/strangler/`)
- `--jwt-secret <secret>`: JWT secret key (default: leer de manifest o generar aleatorio)
- `--api-stage <stage>`: Nombre del stage de API Gateway (default: `prod`)
- `--monolith-url <url>`: URL del monolito Flask (default: `http://internal-monolith-alb.local`)

El script generará:
1. **template-api-gateway.yaml** — API Gateway + VPC Link al monolito
2. **template-authorizer.yaml** — Lambda Authorizer para validación JWT
3. **template-token-blacklist.yaml** — DynamoDB table para tokens revocados
4. **authorizer/** — Código de la Lambda Authorizer (Python)
5. **routing-rules.json** — Reglas de enrutamiento por fase de migración
6. **MIGRATION_PHASES_GUIDE.md** — Guía para ejecutar cada fase de Strangler Fig
7. **DEPLOYMENT_GUIDE.md** — Guía de despliegue paso a paso

### Paso 3 — Presentar el resumen al desarrollador

Presenta la siguiente información de forma estructurada:

1. **Infraestructura generada:**
   - API Gateway REST API con custom domain (opcional)
   - Lambda Authorizer con validación JWT
   - DynamoDB table `token-blacklist` con TTL automático
   - VPC Link para acceso privado al monolito
   - CloudWatch Logs para request/response logging

2. **Fases de migración detectadas:**
   - Total de fases: `<N>` (desde `migration_sequence` del manifest)
   - Fase actual: `<fase_inicial>` (por defecto: Fase 0 — todo al monolito)
   
3. **Routing configurado:**
   - Endpoints al monolito: `<N>`
   - Endpoints a Lambda: `<M>`
   - Endpoints pendientes: `<P>`

4. **Lambda Authorizer:**
   - Valida JWT tokens desde `Authorization: Bearer <token>`
   - Verifica si el token está en blacklist (DynamoDB)
   - Cachea validaciones exitosas (TTL: 5 minutos)
   - Extrae claims (`sub`, `rol`, `email`) y los pasa al backend

5. **Token Blacklist (DynamoDB):**
   - Tabla: `token-blacklist`
   - Partition key: `token_jti` (JWT ID)
   - TTL attribute: `expires_at` (limpieza automática)
   - Capacidad: On-Demand (pay-per-request)

### Paso 4 — Guiar el despliegue por fases

Informa al usuario sobre el flujo de migración:

```markdown
## 🔄 Patrón Strangler Fig: Migración Gradual

### Fase 0: Baseline (TODO al monolito)
**Estado:** API Gateway enruta TODO al monolito Flask (sin cambios)

**Objetivo:** Validar que API Gateway + Authorizer funcionan sin romper el monolito

**Acciones:**
1. Desplegar API Gateway con routing 100% al monolito
2. Desplegar Lambda Authorizer
3. Desplegar DynamoDB token blacklist
4. Probar endpoints existentes (deben funcionar idéntico)
5. Monitorear latencia (overhead de API Gateway: ~10-50ms)

---

### Fase 1: Módulo `<nombre>` (primero en secuencia)
**Estado:** Endpoints de `<módulo>` → Lambda, resto → monolito

**Endpoints migrados:**
- [POST] /api/<modulo>/<endpoint1> → Lambda
- [GET] /api/<modulo>/<endpoint2> → Lambda
- ...

**Acciones:**
1. Desplegar Lambdas del módulo (Skill 04 generará las funciones)
2. Actualizar routing rules en API Gateway
3. Probar endpoints migrados
4. Monitorear errores y latencia
5. Rollback si necesario (cambiar routing de vuelta al monolito)

---

### Fase N: Completar migración
**Estado:** TODOS los endpoints → Lambda, monolito retirado

**Acciones:**
1. Validar que todos los endpoints funcionan en Lambda
2. Desactivar el monolito Flask (no eliminar aún)
3. Monitorear por 7-14 días
4. Eliminar el monolito Flask definitivamente
```

---

## Prerrequisitos

- Python 3.9 o superior instalado en el sistema
- AWS CLI configurado con credenciales válidas
- **migration-manifest.json** generado por Skill 01
- **Outputs de Skill 02** (VPC, RDS, security groups)
- El monolito Flask debe estar desplegado y accesible (ALB o ECS)
- No se requieren dependencias externas para el generador — usa únicamente módulos de la biblioteca estándar de Python

---

## Output generado

### Estructura de directorios

```
<output_dir>/
├── template-api-gateway.yaml          # API Gateway + VPC Link
├── template-authorizer.yaml           # Lambda Authorizer + IAM roles
├── template-token-blacklist.yaml      # DynamoDB table
├── authorizer/                        # Código Lambda Authorizer
│   ├── lambda_function.py            # Handler principal
│   ├── jwt_validator.py              # Lógica de validación JWT
│   ├── blacklist_checker.py          # Cliente DynamoDB
│   └── requirements.txt              # PyJWT, boto3
├── routing-rules.json                 # Reglas por fase (JSON)
├── MIGRATION_PHASES_GUIDE.md          # Guía paso a paso por fase
├── DEPLOYMENT_GUIDE.md                # Guía de despliegue completa
└── test/
    └── test_authorizer.py             # Tests unitarios del Authorizer
```

---

## Características técnicas

### Resolución de anti-patrones

#### AP-token-blacklist
**Problema:** Lista negra de tokens JWT almacenada en `set()` en memoria del proceso Python. Con semántica fail-open: si el proceso reinicia, los tokens revocados vuelven a ser válidos.

**Solución aplicada:**

| Monolito (antes) | Serverless (después) |
|------------------|----------------------|
| `_tokens_revocados = set()` (módulo) | DynamoDB table `token-blacklist` |
| `if token in _tokens_revocados: deny()` | Query DynamoDB por `token_jti` |
| Pérdida de datos en restart | Persistencia + TTL automático |
| Shared state entre workers Flask | State compartido entre todas las Lambdas |

**Código generado (Lambda Authorizer):**
```python
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('token-blacklist')

def is_token_revoked(jti: str) -> bool:
    response = table.get_item(Key={'token_jti': jti})
    return 'Item' in response  # Token está en blacklist
```

**Migración de datos existentes:** El script genera un script de migración one-time que lee `_tokens_revocados` del monolito (si accesible vía API de admin) y los carga a DynamoDB.

### Lambda Authorizer (JWT Validation)

**Input:**
```json
{
  "type": "TOKEN",
  "authorizationToken": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/prod/POST/api/auth/logout"
}
```

**Output (Allow):**
```json
{
  "principalId": "user-123",
  "policyDocument": {
    "Version": "2012-10-17",
    "Statement": [{
      "Action": "execute-api:Invoke",
      "Effect": "Allow",
      "Resource": "arn:aws:execute-api:*:*:*"
    }]
  },
  "context": {
    "userId": "123",
    "userEmail": "user@example.com",
    "userRole": "tecnico"
  }
}
```

**Output (Deny):**
```json
{
  "principalId": "unknown",
  "policyDocument": {
    "Version": "2012-10-17",
    "Statement": [{
      "Action": "execute-api:Invoke",
      "Effect": "Deny",
      "Resource": "*"
    }]
  }
}
```

**Flujo de validación:**
1. Extraer token de `Authorization: Bearer <token>`
2. Decodificar JWT y verificar firma con `JWT_SECRET_KEY`
3. Verificar expiración (`exp` claim)
4. Extraer `jti` (JWT ID) y consultar DynamoDB blacklist
5. Si token NO está en blacklist → Allow (+ cachear 5 min)
6. Si token SÍ está en blacklist → Deny (sin caché)

**Cache configuration:**
```yaml
Authorizer:
  Type: TOKEN
  AuthorizerResultTtlInSeconds: 300  # 5 minutos
```

### Routing Rules (por fase)

**Archivo:** `routing-rules.json`

```json
{
  "phases": [
    {
      "phase": 0,
      "name": "baseline",
      "description": "Todo al monolito — sin migración aún",
      "routes": [
        {
          "path": "/{proxy+}",
          "method": "ANY",
          "target": "monolith"
        }
      ]
    },
    {
      "phase": 1,
      "name": "auth",
      "description": "Migrar módulo auth a Lambda",
      "routes": [
        {"path": "/api/auth/{proxy+}", "method": "ANY", "target": "lambda:auth"},
        {"path": "/{proxy+}", "method": "ANY", "target": "monolith"}
      ]
    },
    {
      "phase": 2,
      "name": "clientes",
      "description": "Migrar módulo clientes a Lambda",
      "routes": [
        {"path": "/api/auth/{proxy+}", "method": "ANY", "target": "lambda:auth"},
        {"path": "/api/clientes/{proxy+}", "method": "ANY", "target": "lambda:clientes"},
        {"path": "/{proxy+}", "method": "ANY", "target": "monolith"}
      ]
    }
  ]
}
```

**Uso:** El desarrollador actualiza manualmente la configuración de API Gateway en cada fase, o usa el script `update_routing.py` generado.

---

## Optimizaciones aplicadas

1. **Caching del Authorizer:**
   - Validaciones exitosas se cachean 5 minutos
   - Reduce llamadas a DynamoDB (de N req/s a ~N/300 req/s)
   - Ahorro estimado: ~90% de costos DynamoDB

2. **VPC Link privado:**
   - El monolito NO necesita ser público durante la migración
   - API Gateway se conecta vía VPC Link a un ALB interno
   - Reduce superficie de ataque

3. **DynamoDB con TTL:**
   - Tokens revocados se eliminan automáticamente al expirar
   - No requiere cronjob de limpieza
   - Ahorro de storage + read capacity

4. **Request/Response logging:**
   - CloudWatch Logs captura todos los requests
   - Útil para debugging de routing durante migración
   - Desactivable en producción para reducir costos

---

## Integración con otros Skills

### ⬅️ Consume desde Skill 01:
- `migration_sequence`: orden de migración por módulos
- `modules[*].endpoints`: paths y métodos de cada endpoint
- `modules[*].url_prefix`: para construir routing rules

### ⬅️ Consume desde Skill 02:
- VPCId, SubnetIds (para VPC Link)
- DBProxyEndpoint (para pasar a Lambdas vía environment variables)

### ➡️ Produce para Skill 04 (Generador de Lambdas):
- AuthorizerArn (para referenciar en templates SAM de Lambdas)
- API Gateway ID (para integrar Lambdas)
- DynamoDB table name (para Lambdas de logout)

### ➡️ Produce para Skill 05 (Validador):
- Routing rules (para validar cobertura de endpoints)
- Logs de API Gateway (para análisis de tráfico)

---

## Limitaciones conocidas

1. **No migra sesiones Flask:** Si el monolito usa `flask.session` (cookies server-side), esas sesiones NO son accesibles desde Lambda. Solo JWT funciona.

2. **Requiere monolito accesible:** Durante la migración, el monolito debe estar desplegado (ECS, EC2, o Lambda contenedor). No se puede migrar desde un monolito "apagado".

3. **Latencia adicional:** API Gateway agrega ~10-50ms de latencia vs. acceso directo al monolito. Para APIs de latencia crítica (<10ms), considerar otras estrategias.

4. **Costo de API Gateway:** $3.50 por millón de requests + $0.09/GB de data transfer. Para apps de muy alto tráfico (>100M req/mes), API Gateway puede ser costoso (~$350/mes).

---

## Troubleshooting

### Authorizer retorna "Unauthorized" para tokens válidos

**Causa 1:** JWT_SECRET_KEY diferente entre monolito y Authorizer

**Solución:**
```bash
# Verificar que sea el MISMO secret
aws ssm get-parameter --name /taller/jwt-secret --with-decryption
# Comparar con el .env del monolito
```

**Causa 2:** Token en formato incorrecto (falta "Bearer " prefix)

**Solución:** El cliente debe enviar `Authorization: Bearer <token>`, NO solo `<token>`.

### Endpoints al monolito devuelven 504 Gateway Timeout

**Causa:** VPC Link no puede alcanzar el monolito (ALB interno)

**Solución:**
1. Verificar que el ALB del monolito está en las mismas subnets que VPC Link
2. Verificar security groups: VPC Link → ALB debe estar permitido

### DynamoDB retorna "Throttling" errors

**Causa:** On-Demand mode tiene límites por defecto (40K RCU/WCU por tabla)

**Solución:**
- Activar Auto Scaling (ya incluido en template)
- O migrar a Provisioned mode con capacidad fija

---

## Referencias

- [AWS API Gateway VPC Links](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-private-integration.html)
- [Lambda Authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html)
- [DynamoDB TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)
- [Strangler Fig Pattern](https://martinfowler.com/bliki/StranglerFigApplication.html)
- [PyJWT Documentation](https://pyjwt.readthedocs.io/)

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software  
**Institución:** Pontificia Universidad Javeriana Cali  
**Director:** Juan Gabriel Quintero Barbosa — Head Solutions Architecture, AWS Colombia
