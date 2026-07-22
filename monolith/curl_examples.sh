#!/bin/bash
# =============================================================================
# Ejemplos de uso de la API — Taller PyME
# Ejecutar con: bash curl_examples.sh
# Requiere que la aplicación esté corriendo en http://localhost:5000
# =============================================================================

BASE_URL="http://localhost:5000"

echo "======================================"
echo " TALLER PyME — Ejemplos de API"
echo "======================================"

# ------------------------------------------------------------------------------
# 1. AUTENTICACIÓN
# ------------------------------------------------------------------------------
echo ""
echo "--- 1. LOGIN (obtener token JWT) ---"
TOKEN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@taller.com", "password": "admin123"}')
echo $TOKEN_RESPONSE | python3 -m json.tool 2>/dev/null || echo $TOKEN_RESPONSE

# Extraer token (requiere python3 o jq)
TOKEN=$(echo $TOKEN_RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['datos']['access_token'])" 2>/dev/null)
echo ""
echo "Token obtenido: ${TOKEN:0:50}..."

echo ""
echo "--- Registro de nuevo usuario ---"
curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Nuevo",
    "apellido": "Tecnico",
    "email": "nuevo.tecnico@taller.com",
    "password": "tecnico123",
    "rol": "tecnico"
  }' | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Perfil del usuario autenticado ---"
curl -s -X GET "$BASE_URL/api/auth/me" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

# ------------------------------------------------------------------------------
# 2. CLIENTES
# ------------------------------------------------------------------------------
echo ""
echo "======================================"
echo "--- 2. CLIENTES ---"

echo ""
echo "--- Listar clientes (paginado) ---"
curl -s -X GET "$BASE_URL/api/clientes/?pagina=1&por_pagina=5" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Buscar clientes por nombre ---"
curl -s -X GET "$BASE_URL/api/clientes/?q=Ana" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Crear cliente ---"
curl -s -X POST "$BASE_URL/api/clientes/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Marcelo",
    "apellido": "Venegas",
    "telefono": "+56911223344",
    "email": "marcelo.venegas@test.com",
    "direccion": "Av. Independencia 1000, Santiago"
  }' | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Obtener cliente por ID ---"
curl -s -X GET "$BASE_URL/api/clientes/1" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Actualizar cliente ---"
curl -s -X PUT "$BASE_URL/api/clientes/1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"telefono": "+56999000111", "direccion": "Nueva dirección 123"}' \
  | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Historial de órdenes del cliente 1 ---"
curl -s -X GET "$BASE_URL/api/clientes/1/historial" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

# ------------------------------------------------------------------------------
# 3. SERVICIOS (algunos públicos)
# ------------------------------------------------------------------------------
echo ""
echo "======================================"
echo "--- 3. SERVICIOS ---"

echo ""
echo "--- Listar servicios (público, sin token) ---"
curl -s -X GET "$BASE_URL/api/servicios/" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Filtrar por categoría: computacion ---"
curl -s -X GET "$BASE_URL/api/servicios/?categoria=computacion" \
  | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Categorías disponibles (público, cacheado) ---"
curl -s -X GET "$BASE_URL/api/servicios/categorias" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Obtener servicio por ID (público) ---"
curl -s -X GET "$BASE_URL/api/servicios/1" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Crear nuevo servicio (requiere token) ---"
curl -s -X POST "$BASE_URL/api/servicios/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Cambio de teclado laptop",
    "descripcion": "Reemplazo de teclado dañado o con teclas faltantes",
    "precio_base": 35000,
    "tiempo_estimado_horas": 1.0,
    "categoria": "computacion"
  }' | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Actualizar servicio ---"
curl -s -X PUT "$BASE_URL/api/servicios/1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"precio_base": 18000}' | python3 -m json.tool 2>/dev/null

# ------------------------------------------------------------------------------
# 4. TRANSACCIONES (órdenes de trabajo)
# ------------------------------------------------------------------------------
echo ""
echo "======================================"
echo "--- 4. TRANSACCIONES ---"

echo ""
echo "--- Listar todas las órdenes ---"
curl -s -X GET "$BASE_URL/api/transacciones/" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Filtrar órdenes pendientes ---"
curl -s -X GET "$BASE_URL/api/transacciones/?estado=pendiente" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Crear orden de trabajo ---"
ORDEN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/transacciones/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cliente_id": 2,
    "tecnico_id": 2,
    "descripcion_problema": "La pantalla parpadea y a veces se apaga sola sin motivo aparente.",
    "tipo_equipo": "Laptop",
    "marca_equipo": "Dell",
    "modelo_equipo": "Inspiron 15 3000",
    "detalles": [
      {"servicio_id": 1, "precio_unitario": 15000, "cantidad": 1},
      {"servicio_id": 2, "precio_unitario": 85000, "cantidad": 1}
    ]
  }')
echo $ORDEN_RESPONSE | python3 -m json.tool 2>/dev/null || echo $ORDEN_RESPONSE
ORDEN_ID=$(echo $ORDEN_RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['datos']['id'])" 2>/dev/null)

echo ""
echo "--- Obtener orden $ORDEN_ID (completa con detalles) ---"
curl -s -X GET "$BASE_URL/api/transacciones/$ORDEN_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Cambiar estado a en_diagnostico ---"
curl -s -X PATCH "$BASE_URL/api/transacciones/$ORDEN_ID/estado" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"estado": "en_diagnostico", "notas_tecnico": "Se recibe equipo, pantalla con daño físico visible."}' \
  | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Subir archivo adjunto (foto del equipo) ---"
# Crear archivo de prueba temporal
echo "Foto simulada del equipo dañado" > /tmp/foto_equipo.txt
curl -s -X POST "$BASE_URL/api/transacciones/$ORDEN_ID/adjunto" \
  -H "Authorization: Bearer $TOKEN" \
  -F "archivo=@/tmp/foto_equipo.txt;type=text/plain" \
  | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Actualizar orden ---"
curl -s -X PUT "$BASE_URL/api/transacciones/$ORDEN_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notas_tecnico": "Diagnóstico: pantalla LCD fracturada internamente."}' \
  | python3 -m json.tool 2>/dev/null

# ------------------------------------------------------------------------------
# 5. REPORTES (solo admin)
# ------------------------------------------------------------------------------
echo ""
echo "======================================"
echo "--- 5. REPORTES (admin) ---"

echo ""
echo "--- Resumen del negocio ---"
curl -s -X GET "$BASE_URL/api/reportes/resumen" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Ingresos últimos 30 días (agrupado por día) ---"
curl -s -X GET "$BASE_URL/api/reportes/ingresos?agrupacion=dia" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Ingresos con rango de fechas personalizado ---"
curl -s -X GET "$BASE_URL/api/reportes/ingresos?desde=2024-01-01&hasta=2024-12-31&agrupacion=mes" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Rendimiento de técnicos ---"
curl -s -X GET "$BASE_URL/api/reportes/tecnicos" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Top 5 servicios más solicitados ---"
curl -s -X GET "$BASE_URL/api/reportes/servicios-top?limite=5" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "--- Estado del caché en memoria ---"
curl -s -X GET "$BASE_URL/api/reportes/estado-cache" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null

echo ""
echo "======================================"
echo " Ejemplos completados"
echo "======================================"
