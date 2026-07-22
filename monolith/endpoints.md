# Documentación de Endpoints — Taller PyME API

Base URL: `http://localhost:5000`

Todos los endpoints protegidos requieren el header:
```
Authorization: Bearer <jwt_token>
```

---

## Módulo: Autenticación (`/api/auth`)

### POST /api/auth/register
Registra un nuevo usuario (técnico o administrador).
- **Auth**: No requerida
- **Body**:
```json
{
  "nombre": "string",
  "apellido": "string",
  "email": "string",
  "password": "string (min 6 chars)",
  "rol": "tecnico | admin"
}
```
- **Respuesta 201**: `{ "ok": true, "datos": { ...usuario } }`
- **Respuesta 409**: Email ya registrado

---

### POST /api/auth/login
Autentica un usuario y retorna el token JWT.
- **Auth**: No requerida
- **Body**:
```json
{ "email": "string", "password": "string" }
```
- **Respuesta 200**:
```json
{ "ok": true, "datos": { "access_token": "...", "usuario": {...} } }
```
- **Respuesta 401**: Credenciales inválidas

---

### GET /api/auth/me
Retorna el perfil del usuario autenticado.
- **Auth**: JWT requerido
- **Respuesta 200**: `{ "ok": true, "datos": { ...usuario } }`

---

### POST /api/auth/logout
Invalida el token (lista negra en memoria).
- **Auth**: JWT requerido
- **Respuesta 200**: `{ "ok": true, "mensaje": "Sesión cerrada" }`

---

### PUT /api/auth/password
Cambia la contraseña del usuario autenticado.
- **Auth**: JWT requerido
- **Body**:
```json
{ "password_actual": "string", "password_nueva": "string" }
```
- **Respuesta 200**: `{ "ok": true, "mensaje": "Contraseña actualizada" }`

---

## Módulo: Clientes (`/api/clientes`)

### GET /api/clientes/
Lista clientes con paginación y búsqueda.
- **Auth**: JWT requerido
- **Query params**:
  - `q` — búsqueda por nombre/apellido/email/teléfono
  - `pagina` (default: 1)
  - `por_pagina` (default: 20, máx: 100)
  - `activo` (default: true)
- **Respuesta 200**:
```json
{
  "ok": true,
  "datos": {
    "items": [...],
    "total": 7,
    "pagina": 1,
    "por_pagina": 20,
    "paginas": 1
  }
}
```

---

### POST /api/clientes/
Crea un nuevo cliente.
- **Auth**: JWT requerido
- **Body**:
```json
{
  "nombre": "string",
  "apellido": "string",
  "telefono": "string",
  "email": "string (opcional)",
  "direccion": "string (opcional)",
  "documento_identidad": "string (opcional)"
}
```
- **Respuesta 201**: `{ "ok": true, "datos": { ...cliente } }`

---

### GET /api/clientes/:id
Obtiene un cliente por ID.
- **Auth**: JWT requerido
- **Respuesta 200**: `{ "ok": true, "datos": { ...cliente } }`
- **Respuesta 404**: Cliente no encontrado

---

### PUT /api/clientes/:id
Actualiza los datos de un cliente (campos opcionales).
- **Auth**: JWT requerido
- **Body**: Cualquier subconjunto de campos del cliente
- **Respuesta 200**: `{ "ok": true, "datos": { ...cliente } }`

---

### DELETE /api/clientes/:id
Desactiva un cliente (soft delete).
- **Auth**: JWT requerido (rol: admin)
- **Respuesta 200**: `{ "ok": true, "mensaje": "Cliente desactivado" }`
- **Respuesta 403**: No autorizado

---

### GET /api/clientes/:id/historial
Historial completo de órdenes de un cliente.
- **Auth**: JWT requerido
- **Respuesta 200**:
```json
{
  "ok": true,
  "datos": {
    "cliente": {...},
    "ordenes": [...],
    "total_ordenes": 3
  }
}
```

---

## Módulo: Servicios (`/api/servicios`)

### GET /api/servicios/
Lista el catálogo de servicios. **Endpoint público**.
- **Auth**: No requerida
- **Query params**:
  - `categoria` — filtrar por categoría
  - `q` — búsqueda por nombre
  - `pagina`, `por_pagina`
  - `solo_activos` (default: true)

---

### GET /api/servicios/categorias
Lista categorías con cantidad de servicios. **Endpoint público, cacheado**.
- **Auth**: No requerida
- **Respuesta 200**:
```json
{
  "ok": true,
  "datos": [
    { "categoria": "computacion", "cantidad_servicios": 5 },
    ...
  ]
}
```

---

### GET /api/servicios/:id
Obtiene un servicio por ID. **Endpoint público**.
- **Auth**: No requerida
- **Respuesta 200**: `{ "ok": true, "datos": { ...servicio } }`

---

### POST /api/servicios/
Crea un nuevo servicio en el catálogo.
- **Auth**: JWT requerido
- **Body**:
```json
{
  "nombre": "string",
  "precio_base": 25000,
  "descripcion": "string (opcional)",
  "tiempo_estimado_horas": 1.5,
  "categoria": "computacion | celular | electrodomestico | electronico | otro"
}
```
- **Respuesta 201**: `{ "ok": true, "datos": { ...servicio } }`

---

### PUT /api/servicios/:id
Actualiza un servicio existente.
- **Auth**: JWT requerido
- **Body**: Cualquier subconjunto de campos
- **Respuesta 200**: `{ "ok": true, "datos": { ...servicio } }`

---

### DELETE /api/servicios/:id
Desactiva un servicio (soft delete).
- **Auth**: JWT requerido (rol: admin)
- **Respuesta 200**: `{ "ok": true, "mensaje": "Servicio desactivado" }`

---

## Módulo: Transacciones (`/api/transacciones`)

### GET /api/transacciones/
Lista órdenes de trabajo con filtros.
- **Auth**: JWT requerido
- **Query params**:
  - `estado` — pendiente | en_diagnostico | en_reparacion | completado | cancelado
  - `cliente_id`
  - `tecnico_id`
  - `fecha_desde` (YYYY-MM-DD)
  - `fecha_hasta` (YYYY-MM-DD)
  - `pagina`, `por_pagina`

---

### POST /api/transacciones/
Crea una nueva orden de trabajo.
- **Auth**: JWT requerido
- **Body**:
```json
{
  "cliente_id": 1,
  "tecnico_id": 2,
  "descripcion_problema": "string (min 10 chars)",
  "tipo_equipo": "string (opcional)",
  "marca_equipo": "string (opcional)",
  "modelo_equipo": "string (opcional)",
  "fecha_estimada": "2024-01-15T00:00:00 (opcional)",
  "detalles": [
    {
      "servicio_id": 1,
      "precio_unitario": 25000,
      "cantidad": 1,
      "notas": "string (opcional)"
    }
  ]
}
```
- **Respuesta 201**: `{ "ok": true, "datos": { ...orden, "detalles": [...] } }`

---

### GET /api/transacciones/:id
Obtiene una orden completa con sus detalles.
- **Auth**: JWT requerido
- **Respuesta 200**: `{ "ok": true, "datos": { ...orden, "detalles": [...] } }`

---

### PUT /api/transacciones/:id
Actualiza datos generales de la orden (no cambia estado).
- **Auth**: JWT requerido
- **Body**: Subconjunto de campos editables
- **Respuesta 200**: `{ "ok": true, "datos": { ...orden } }`
- **Respuesta 409**: Orden ya completada o cancelada

---

### PATCH /api/transacciones/:id/estado
Cambia el estado de una orden. Dispara notificación al cliente.
- **Auth**: JWT requerido
- **Body**:
```json
{
  "estado": "en_diagnostico | en_reparacion | completado | cancelado",
  "notas_tecnico": "string (opcional)"
}
```
- **Respuesta 200**: `{ "ok": true, "mensaje": "Estado actualizado a: completado" }`
- **Respuesta 409**: Transición de estado inválida

---

### POST /api/transacciones/:id/adjunto
Sube un archivo adjunto a la orden (almacenamiento local).
- **Auth**: JWT requerido
- **Content-Type**: `multipart/form-data`
- **Form field**: `archivo` (pdf, png, jpg, jpeg, docx)
- **Respuesta 200**: `{ "ok": true, "datos": { "archivo": "...", "ruta": "..." } }`
- **Nota**: Anti-patrón intencional — guarda en filesystem local

---

### DELETE /api/transacciones/:id
Cancela una orden de trabajo.
- **Auth**: JWT requerido (admin para órdenes en proceso)
- **Respuesta 200**: `{ "ok": true, "mensaje": "Orden cancelada" }`

---

## Módulo: Reportes (`/api/reportes`)

### GET /api/reportes/resumen
KPIs generales del negocio. **Solo admin**.
- **Auth**: JWT requerido (rol: admin)
- **Respuesta 200**:
```json
{
  "ok": true,
  "datos": {
    "ordenes": {
      "total": 42,
      "pendientes": 5,
      "en_proceso": 8,
      "completadas": 25,
      "canceladas": 4
    },
    "ingresos_mes_actual": 1250000,
    "clientes_activos": 120,
    "servicios_activos": 12,
    "tecnicos_activos": 3,
    "generado_en": "2024-01-15T10:30:00"
  }
}
```

---

### GET /api/reportes/ingresos
Ingresos agrupados por período. **Solo admin**.
- **Auth**: JWT requerido (rol: admin)
- **Query params**:
  - `desde` (YYYY-MM-DD, default: 30 días atrás)
  - `hasta` (YYYY-MM-DD, default: hoy)
  - `agrupacion`: `dia | semana | mes` (default: dia)

---

### GET /api/reportes/tecnicos
Rendimiento de técnicos. **Solo admin**.
- **Auth**: JWT requerido (rol: admin)
- **Respuesta 200**: Lista de técnicos con métricas de rendimiento

---

### GET /api/reportes/servicios-top
Servicios más solicitados. **Solo admin** (requiere JWT).
- **Auth**: JWT requerido
- **Query params**:
  - `limite` (default: 10)
  - `categoria` — filtrar por categoría

---

### GET /api/reportes/estado-cache
Estadísticas del caché en memoria. **Solo admin**.
- **Auth**: JWT requerido (rol: admin)
- **Respuesta 200**:
```json
{
  "ok": true,
  "datos": {
    "hits": 145,
    "misses": 23,
    "escrituras": 45,
    "entradas_activas": 8
  }
}
```

---

## Resumen de endpoints

| Módulo         | Método | Ruta                                  | Auth      | Público |
|----------------|--------|---------------------------------------|-----------|---------|
| Auth           | POST   | /api/auth/register                    | No        | Sí      |
| Auth           | POST   | /api/auth/login                       | No        | Sí      |
| Auth           | GET    | /api/auth/me                          | JWT       | No      |
| Auth           | POST   | /api/auth/logout                      | JWT       | No      |
| Auth           | PUT    | /api/auth/password                    | JWT       | No      |
| Clientes       | GET    | /api/clientes/                        | JWT       | No      |
| Clientes       | POST   | /api/clientes/                        | JWT       | No      |
| Clientes       | GET    | /api/clientes/\<id\>                  | JWT       | No      |
| Clientes       | PUT    | /api/clientes/\<id\>                  | JWT       | No      |
| Clientes       | DELETE | /api/clientes/\<id\>                  | JWT admin | No      |
| Clientes       | GET    | /api/clientes/\<id\>/historial        | JWT       | No      |
| Servicios      | GET    | /api/servicios/                       | No        | **Sí**  |
| Servicios      | GET    | /api/servicios/categorias             | No        | **Sí**  |
| Servicios      | GET    | /api/servicios/\<id\>                 | No        | **Sí**  |
| Servicios      | POST   | /api/servicios/                       | JWT       | No      |
| Servicios      | PUT    | /api/servicios/\<id\>                 | JWT       | No      |
| Servicios      | DELETE | /api/servicios/\<id\>                 | JWT admin | No      |
| Transacciones  | GET    | /api/transacciones/                   | JWT       | No      |
| Transacciones  | POST   | /api/transacciones/                   | JWT       | No      |
| Transacciones  | GET    | /api/transacciones/\<id\>             | JWT       | No      |
| Transacciones  | PUT    | /api/transacciones/\<id\>             | JWT       | No      |
| Transacciones  | PATCH  | /api/transacciones/\<id\>/estado      | JWT       | No      |
| Transacciones  | POST   | /api/transacciones/\<id\>/adjunto     | JWT       | No      |
| Transacciones  | DELETE | /api/transacciones/\<id\>             | JWT       | No      |
| Reportes       | GET    | /api/reportes/resumen                 | JWT admin | No      |
| Reportes       | GET    | /api/reportes/ingresos                | JWT admin | No      |
| Reportes       | GET    | /api/reportes/tecnicos                | JWT admin | No      |
| Reportes       | GET    | /api/reportes/servicios-top           | JWT       | No      |
| Reportes       | GET    | /api/reportes/estado-cache            | JWT admin | No      |

**Total: 29 endpoints**
