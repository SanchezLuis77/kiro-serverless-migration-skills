# Guía de Migración — Uploads a S3

**⚠️ BREAKING CHANGE:** El flujo de upload de archivos cambia de 1 paso (multipart/form-data) a 2 pasos (presigned URL + PUT directo a S3).

---

## Endpoints afectados

Los siguientes endpoints del monolito requieren cambios en el cliente:

- `[POST] /api/transacciones/{orden_id}/adjunto` (módulo: transacciones)

---

## Flujo ANTES (monolito)

```javascript
// Un solo request con FormData
const formData = new FormData();
formData.append('archivo', file);

const response = await fetch('/api/transacciones/123/adjunto', {
  method: 'POST',
  body: formData,
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

const result = await response.json();
console.log('Archivo subido:', result.url);
```

**Características:**
- ✅ Un solo request
- ❌ Consume bandwidth del backend
- ❌ Timeout en archivos grandes
- ❌ No hay progress tracking nativo

---

## Flujo DESPUÉS (serverless)

```javascript
// Paso 1: Solicitar presigned URL
const response1 = await fetch(
  `/api/transacciones/123/adjunto/upload-url?filename=${encodeURIComponent(file.name)}`,
  {
    headers: { 'Authorization': `Bearer ${token}` }
  }
);

const { upload_url, file_key, expires_in } = await response1.json();

// Paso 2: Upload directo a S3 (sin token, URL firmada)
const response2 = await fetch(upload_url, {
  method: 'PUT',
  body: file,
  headers: {
    'Content-Type': file.type
  }
});

if (!response2.ok) {
  throw new Error('Error al subir archivo a S3');
}

// Paso 3: Notificar al backend que el upload completó
const response3 = await fetch('/api/transacciones/123/adjunto', {
  method: 'POST',
  body: JSON.stringify({
    file_key: file_key,
    filename: file.name,
    size: file.size,
    content_type: file.type
  }),
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

const result = await response3.json();
console.log('Archivo registrado en BD:', result);
```

**Características:**
- ⚠️ Tres requests (más complejo)
- ✅ NO consume bandwidth del backend
- ✅ Sin timeouts (S3 maneja archivos grandes)
- ✅ Progress tracking con `xhr.upload.onprogress`
- ✅ Más rápido (sin proxy)
- ✅ Más escalable (S3 maneja millones de uploads concurrentes)

---

## Implementación con Progress Tracking

```javascript
function uploadFileWithProgress(file, presignedUrl, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    // Configurar evento de progreso
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percentComplete = (e.loaded / e.total) * 100;
        onProgress(percentComplete);
      }
    });

    // Configurar evento de completado
    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        resolve();
      } else {
        reject(new Error(`Upload falló: ${xhr.status}`));
      }
    });

    // Configurar evento de error
    xhr.addEventListener('error', () => {
      reject(new Error('Error de red al subir archivo'));
    });

    // Enviar request
    xhr.open('PUT', presignedUrl);
    xhr.setRequestHeader('Content-Type', file.type);
    xhr.send(file);
  });
}

// Uso:
await uploadFileWithProgress(file, upload_url, (progress) => {
  console.log(`Progreso: ${progress.toFixed(1)}%`);
  updateProgressBar(progress);
});
```

---

## Manejo de Errores

### Error 403: URL expirada

```javascript
try {
  await fetch(upload_url, { method: 'PUT', body: file });
} catch (error) {
  if (error.status === 403) {
    // La URL expiró (5 minutos), solicitar una nueva
    console.error('URL expirada, reintentando...');
    // Volver al Paso 1
  }
}
```

### Error de tamaño de archivo

```javascript
const MAX_FILE_SIZE_MB = 16;

if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
  alert(`Archivo muy grande. Máximo: ${MAX_FILE_SIZE_MB} MB`);
  return;
}
```

### Error de extensión no permitida

```javascript
const ALLOWED_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'docx'];
const extension = file.name.split('.').pop().toLowerCase();

if (!ALLOWED_EXTENSIONS.includes(extension)) {
  alert(`Extensión no permitida. Permitidas: ${ALLOWED_EXTENSIONS.join(', ')}`);
  return;
}
```

---

## Migración Incremental

Si no puedes cambiar el cliente inmediatamente:

1. **Opción A: Mantener ambos flujos**
   - Nuevo endpoint: `GET /adjunto/upload-url` (presigned)
   - Endpoint legacy: `POST /adjunto` (proxy a S3)
   - Migrar clientes gradualmente

2. **Opción B: Wrapper en el backend**
   - El backend recibe multipart/form-data
   - Internamente sube a S3 (sin filesystem)
   - ⚠️ Consume bandwidth y no aprovecha beneficios de S3

---

## Checklist de Migración

- [ ] Actualizar código del cliente para flujo de 3 pasos
- [ ] Implementar progress tracking (opcional)
- [ ] Añadir validación de extensión en el frontend
- [ ] Añadir validación de tamaño en el frontend
- [ ] Probar uploads con archivos pequeños (<1 MB)
- [ ] Probar uploads con archivos grandes (>5 MB)
- [ ] Probar manejo de errores (URL expirada, red caída)
- [ ] Actualizar documentación del API
- [ ] Notificar a equipos dependientes del cambio
- [ ] Configurar monitoreo de errores en S3 uploads

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Fecha:** 2026-11-12