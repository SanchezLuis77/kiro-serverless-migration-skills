# Deployment Guide — Skill 03: Orquestador Strangler Fig

**Generado:** 2026-11-17T16:22:24.923271
**API Stage:** prod
**Total fases:** 6
**Skill Version:** 1.0.0

---

## 📋 Resumen

Este directorio contiene la infraestructura de orquestación Strangler Fig:

- **API Gateway** con routing por fases
- **Lambda Authorizer** para validación JWT
- **DynamoDB** para token blacklist (resuelve AP-token-blacklist)
- **VPC Link** para acceso privado al monolito
- **CloudWatch Logs** para monitoring

**Endpoints totales:** 29
**Fases de migración:** 6

---

## 🚀 Pasos de Despliegue

### Paso 1: Guardar JWT secret en SSM Parameter Store

⚠️ **CRÍTICO:** El JWT secret DEBE ser el MISMO que usa el monolito Flask.

```bash
aws ssm put-parameter \
  --name /taller/jwt-secret \
  --value "P3HQrPR2kF_YXMsL89RRTosMEJRGQ9ckKVoIk3OHPvE" \
  --type SecureString \
  --description "JWT secret key para Authorizer" \
  --region us-east-1
```

### Paso 2: Desplegar Lambda Authorizer (primero)

```bash
cd authorizer
pip install -r requirements.txt -t .
cd ..

aws cloudformation deploy \
  --template-file template-authorizer.yaml \
  --stack-name taller-authorizer \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      EnvironmentName=taller \
      JWTSecretKey=P3HQrPR2kF_YXMsL89RRTosMEJRGQ9ckKVoIk3OHPvE \
  --region us-east-1
```

**Tiempo estimado:** 2-3 minutos

### Paso 3: Desplegar API Gateway (después de Authorizer)

```bash
aws cloudformation deploy \
  --template-file template-api-gateway.yaml \
  --stack-name taller-api \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      EnvironmentName=taller \
      ApiStageName=prod \
      MonolithURL=<URL_DE_TU_MONOLITO> \
  --region us-east-1
```

**Tiempo estimado:** 5-7 minutos

### Paso 4: Obtener la URL de API Gateway

```bash
aws cloudformation describe-stacks \
  --stack-name taller-api \
  --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
  --output text
```

**Output ejemplo:** `https://abc123def.execute-api.us-east-1.amazonaws.com/prod`

---

## 🧪 Testing (Fase 0: Baseline)

### Test 1: Login (público)

```bash
curl -X POST https://<api-gateway-url>/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "password123"}'
```

**Esperado:** Retorna JWT token (200 OK)

### Test 2: Endpoint protegido

```bash
TOKEN="<token-del-login>"

curl https://<api-gateway-url>/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

**Esperado:** Retorna perfil del usuario (200 OK)

### Test 3: Logout (blacklist)

```bash
curl -X POST https://<api-gateway-url>/api/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

**Esperado:** Token agregado a blacklist (200 OK)

### Test 4: Usar token revocado

```bash
curl https://<api-gateway-url>/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

**Esperado:** Authorizer niega acceso (403 Forbidden)

---

## 🔄 Migración por Fases (Strangler Fig)

### Fase 0: Baseline ✅ (actual)

**Estado:** API Gateway enruta TODO al monolito

**Acción:** Ninguna (ya desplegado)

---

### Fase 1: Migrar primer módulo

**Módulo:** `auth`

**Acciones:**
1. Desplegar Lambdas del módulo (Skill 04 genera las funciones)
2. Actualizar routing en API Gateway:
   ```bash
   python update_routing.py --phase 1
   ```
3. Probar endpoints migrados
4. Monitorear logs y métricas

**Rollback:** Cambiar routing de vuelta a Fase 0

---

## 💰 Estimación de Costos (us-east-1)

### Costos fijos mensuales
- **VPC Link:** $0.025/hora × 730 horas = **~$18/mes**

### Costos variables (por uso)
- **API Gateway:** $3.50 por millón de requests
  - 1M req/mes: $3.50
  - 10M req/mes: $35
  - 100M req/mes: $350
- **Lambda Authorizer:** $0.20 por millón de invocaciones + compute
  - Con cache (5 min), ~90% reducción
  - 1M req/mes → ~100K invocaciones → $0.02
- **DynamoDB:** Pay-per-request
  - 1M reads: $0.25
  - 1M writes: $1.25
- **Data Transfer:** $0.09/GB out

**Total estimado (1M req/mes):** ~$25-30/mes  
**Total estimado (10M req/mes):** ~$60-80/mes

---

## 🛠️ Troubleshooting

### Authorizer retorna 401 para todos los requests

**Causa:** JWT secret diferente entre monolito y Authorizer

**Solución:**
1. Verificar secret en SSM:
   ```bash
   aws ssm get-parameter --name /taller/jwt-secret --with-decryption
   ```
2. Comparar con `.env` del monolito
3. Actualizar stack de Authorizer con el secret correcto

### API Gateway retorna 504 Timeout

**Causa:** VPC Link no puede alcanzar el monolito

**Solución:**
1. Verificar que el NLB tiene targets registrados:
   ```bash
   aws elbv2 describe-target-health --target-group-arn <arn>
   ```
2. Verificar security groups (VPC Link → NLB permitido)

### DynamoDB throttling

**Causa:** Demasiadas escrituras/lecturas concurrentes

**Solución:**
- Ya configurado en On-Demand mode (escala automáticamente)
- Si persiste, verificar que el cache del Authorizer está activo (300s)

---

## 📚 Referencias

- [API Gateway VPC Links](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-private-integration.html)
- [Lambda Authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html)
- [Strangler Fig Pattern](https://martinfowler.com/bliki/StranglerFigApplication.html)

---

**Generado por:** Skill 03 — Orquestador Strangler Fig  
**Autor:** Luis Gerardo Sánchez Ordóñez  
**Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software  
**Institución:** Pontificia Universidad Javeriana Cali
