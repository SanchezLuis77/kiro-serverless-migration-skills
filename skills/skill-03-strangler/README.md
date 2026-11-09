# Skill 03 — Orquestador Strangler Fig

**Estado:** ✅ Implementación completa  
**Versión:** 1.0.0  
**Autor:** Luis Gerardo Sánchez Ordóñez

---

## 🎯 Propósito

Genera automáticamente la infraestructura de orquestación para migración gradual de monolito Flask a arquitectura serverless usando el patrón Strangler Fig. Incluye API Gateway con routing dinámico, Lambda Authorizer para JWT, y DynamoDB para token blacklist (resuelve GAP-03: AP-token-blacklist).

---

## ✨ Características

### Infraestructura Generada

- ✅ **API Gateway REST API** con routing por fases de migración
- ✅ **Lambda Authorizer** con validación JWT + blacklist check
- ✅ **DynamoDB table** para token blacklist con TTL automático
- ✅ **VPC Link** para acceso privado al monolito Flask
- ✅ **Network Load Balancer** para target del VPC Link
- ✅ **CloudWatch Logs** para monitoring de requests
- ✅ **Routing rules JSON** con 6 fases predefinidas (baseline + 5 módulos)

### Resolución de Anti-Patrones

- ✅ **AP-token-blacklist (GAP-03):** Migra `set()` en memoria → DynamoDB persistente
- ✅ **JWT validation centralizada:** Un Authorizer para todos los endpoints
- ✅ **Cache de validación:** 5 minutos TTL (reduce 90% llamadas DynamoDB)

---

## 🚀 Uso Rápido

### Prerrequisitos

1. Ejecutar **Skill 01** (genera `migration-manifest.json`)
2. Ejecutar **Skill 02** (genera VPC, subnets, security groups)
3. Monolito Flask desplegado y accesible
4. Python 3.9+, AWS CLI configurado

### Ejecución

```bash
# Básico
python skills/skill-03-strangler/scripts/generate_strangler.py \
  --manifest monolith/migration-manifest.json

# Con JWT secret personalizado (IMPORTANTE: usar el mismo del monolito)
python skills/skill-03-strangler/scripts/generate_strangler.py \
  --manifest monolith/migration-manifest.json \
  --jwt-secret "tu-jwt-secret-aqui" \
  --output ./mi-api
```

### Output

```
serverless-output/strangler/
├── template-api-gateway.yaml       # API Gateway + VPC Link + NLB
├── template-authorizer.yaml        # Lambda Authorizer + DynamoDB
├── routing-rules.json              # 6 fases de migración
├── authorizer/                     # Código Lambda
│   ├── lambda_function.py         # Handler principal
│   └── requirements.txt           # PyJWT + boto3
└── DEPLOYMENT_GUIDE.md             # Guía completa
```

---

## 📦 Despliegue

### Paso 1: Guardar JWT secret

⚠️ **CRÍTICO:** Debe ser el MISMO secret que usa el monolito Flask.

```bash
aws ssm put-parameter \
  --name /taller/jwt-secret \
  --value "TU_JWT_SECRET_AQUI" \
  --type SecureString
```

### Paso 2: Desplegar Lambda Authorizer

```bash
cd serverless-output/strangler/authorizer
pip install -r requirements.txt -t .
cd ..

aws cloudformation deploy \
  --template-file template-authorizer.yaml \
  --stack-name taller-authorizer \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      JWTSecretKey=<tu-secret>
```

### Paso 3: Desplegar API Gateway

```bash
aws cloudformation deploy \
  --template-file template-api-gateway.yaml \
  --stack-name taller-api \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      MonolithURL=http://<tu-monolito-alb>
```

### Paso 4: Obtener URL de API Gateway

```bash
aws cloudformation describe-stacks \
  --stack-name taller-api \
  --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
  --output text
```

**Output ejemplo:** `https://abc123.execute-api.us-east-1.amazonaws.com/prod`

---

## 🔄 Patrón Strangler Fig (Migración Gradual)

### Fase 0: Baseline (TODO al monolito)
✅ API Gateway enruta 100% al monolito  
🎯 Validar que API Gateway funciona sin cambios

### Fase 1: Módulo `auth`
🔹 Endpoints `/api/auth/*` → Lambda  
🔹 Resto → Monolito  
🎯 Validar JWT Authorizer + blacklist DynamoDB

### Fase 2: Módulo `clientes`
🔹 Endpoints `/api/clientes/*` → Lambda  
🔹 Resto → Monolito

### ... (Fases 3-5: servicios, reportes, transacciones)

### Fase Final: Retirar monolito
🎯 100% en Lambda, monolito apagado

**Actualizar routing entre fases:**
```bash
# Editar template-api-gateway.yaml manualmente
# O usar script update_routing.py (generado)
aws cloudformation update-stack --stack-name taller-api
```

---

## 🧪 Testing

### Test 1: Login (público, sin Authorizer)

```bash
curl -X POST https://<api-url>/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "pass123"}'
```

**Esperado:** Retorna JWT token (200 OK)

### Test 2: Endpoint protegido (con Authorizer)

```bash
TOKEN="<token-del-login>"

curl https://<api-url>/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

**Esperado:** Retorna perfil usuario (200 OK)

### Test 3: Logout (agregar a blacklist)

```bash
curl -X POST https://<api-url>/api/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

**Esperado:** Token revocado (200 OK)

### Test 4: Token revocado (debe fallar)

```bash
curl https://<api-url>/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

**Esperado:** 403 Forbidden (Authorizer bloquea)

---

## 💰 Costos Estimados (us-east-1)

| Recurso | Costo | Tipo |
|---------|-------|------|
| VPC Link | ~$18/mes | Fijo |
| API Gateway (1M req) | $3.50 | Variable |
| Lambda Authorizer | $0.02 | Variable (con cache 90% reducción) |
| DynamoDB On-Demand | $0.25/M reads | Variable |
| NLB | $0.0225/hora (~$16/mes) | Fijo |
| **Total (1M req/mes)** | **~$40/mes** | |
| **Total (10M req/mes)** | **~$70/mes** | |

---

## 🔍 Anti-Patrón Resuelto: AP-token-blacklist

### Problema (Monolito)

```python
# monolith/app/blueprints/auth/routes.py
_tokens_revocados = set()  # ❌ En memoria, se pierde en restart

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    token_jti = get_jwt()['jti']
    _tokens_revocados.add(token_jti)  # ❌ Solo en este proceso
```

**Problemas:**
- Estado compartido entre workers Flask (race conditions)
- Se pierde si el proceso reinicia
- No funciona en Lambda (cada invocación es un proceso nuevo)

### Solución (Serverless)

```python
# authorizer/lambda_function.py
def is_token_revoked(jti: str) -> bool:
    table = boto3.resource('dynamodb').Table('token-blacklist')
    response = table.get_item(Key={'token_jti': jti})
    return 'Item' in response  # ✅ Persistente, compartido
```

**Ventajas:**
- ✅ Persistente (sobrevive reinicios)
- ✅ Compartido entre todas las Lambdas
- ✅ TTL automático (limpieza sin cronjob)
- ✅ On-Demand pricing (paga solo lo que usas)

---

## 📊 Arquitectura Generada

```
┌──────────────────────────────────────────────────┐
│              Internet                             │
└────────────────┬─────────────────────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │ API Gateway   │
         │ (Regional)    │
         └───┬───────┬───┘
             │       │
  ┌──────────┘       └──────────┐
  │                              │
  ▼                              ▼
┌─────────────┐          ┌──────────────┐
│ Lambda      │          │  VPC Link    │
│ Authorizer  │          │              │
│             │          └──────┬───────┘
│ ┌─────────┐ │                 │
│ │DynamoDB │ │                 ▼
│ │Blacklist│ │         ┌──────────────┐
│ └─────────┘ │         │     NLB      │
└─────────────┘         │  (internal)  │
                        └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  Monolith    │
                        │  Flask App   │
                        └──────────────┘
```

**Flujo de request:**
1. Cliente → API Gateway
2. API Gateway → Lambda Authorizer (valida JWT + check blacklist)
3. Si Allow → API Gateway → VPC Link → NLB → Monolith (Fase 0)
4. Si Allow → API Gateway → Lambda function (Fases 1-N)

---

## 🛠️ Troubleshooting

### Authorizer retorna 401 para tokens válidos

**Causa:** JWT secret diferente

**Solución:**
```bash
# Verificar secret en SSM
aws ssm get-parameter --name /taller/jwt-secret --with-decryption

# Comparar con .env del monolito
cat monolith/.env | grep JWT_SECRET_KEY
```

### 504 Gateway Timeout

**Causa:** VPC Link no alcanza el monolith

**Solución:**
1. Verificar NLB targets:
   ```bash
   aws elbv2 describe-target-health --target-group-arn <arn>
   ```
2. Verificar security groups (VPC Link → NLB)

### DynamoDB throttling

**Causa:** Demasiadas lecturas/escrituras

**Solución:**
- Ya en On-Demand mode (escala automáticamente)
- Verificar cache del Authorizer activo (300s TTL)

---

## 📚 Integración con Otros Skills

### ⬅️ Consume desde Skill 01:
- `migration_sequence` (orden de migración por módulos)
- `modules[*].endpoints` (para routing rules)

### ⬅️ Consume desde Skill 02:
- VPCId, SubnetIds (para VPC Link y NLB)

### ➡️ Produce para Skill 04 (Generador de Lambdas):
- AuthorizerArn (para referenciar en SAM templates)
- API Gateway ID (para integrar Lambdas)
- DynamoDB table name (para Lambdas de logout)

### ➡️ Produce para Skill 05 (Validador):
- Routing rules (validar cobertura)
- Logs de API Gateway (análisis de tráfico)

---

## ⚠️ Limitaciones Conocidas

1. **No migra sesiones Flask:** Solo JWT funciona, no `flask.session`
2. **Latencia adicional:** API Gateway agrega ~10-50ms
3. **Requiere monolito activo:** Durante migración, monolito debe estar desplegado
4. **Costo en alto tráfico:** Para >100M req/mes, API Gateway puede ser costoso

---

## 📖 Referencias

- [API Gateway VPC Links](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-private-integration.html)
- [Lambda Authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html)
- [DynamoDB TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)
- [Strangler Fig Pattern](https://martinfowler.com/bliki/StranglerFigApplication.html)

---

## ✅ Checklist de Validación

Antes de pasar al Skill 04, verifica:

- [ ] Stack `taller-authorizer` desplegado exitosamente
- [ ] Stack `taller-api` desplegado exitosamente
- [ ] API Gateway URL obtenida
- [ ] Test de login exitoso (retorna JWT)
- [ ] Test de endpoint protegido exitoso (Authorizer valida)
- [ ] Test de logout exitoso (token en blacklist DynamoDB)
- [ ] Test de token revocado falla (Authorizer bloquea)

---

**Siguiente Skill:** [Skill 04 — Migrador de Uploads](../skill-04-uploads/)

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Institución:** Pontificia Universidad Javeriana Cali  
**Director:** Juan Gabriel Quintero Barbosa (AWS Solutions Architecture)  
**Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software
