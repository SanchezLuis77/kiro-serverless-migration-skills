# Implementation Plan: Skill 01 — Analizador de Monolito

## Overview

Implementación del Skill 01 (`skill-01-analyzer`) como paquete instalable en Kiro IDE siguiendo el estándar agentskills.io. El componente central es `analyze_monolith.py`, un script Python que opera exclusivamente con módulos de la biblioteca estándar para producir `migration-manifest.json` a partir del análisis estático AST de un monolito Flask.

El orden de tareas sigue la cadena de dependencias del diseño: scaffolding → componentes del pipeline AST en secuencia → CLI → tests de integración → tests de propiedad → validación final.

---

## Tasks

- [x] 1. Scaffolding del Skill (estructura de directorios, SKILL.md, README.md)
  - Crear el directorio `skills/skill-01-analyzer/` con la estructura requerida por agentskills.io: `scripts/`, `templates/` (vacío), `SKILL.md`, `README.md`
  - Escribir `SKILL.md` con el bloque de metadatos YAML obligatorio (`name`, `version`, `description`, `author`, `tags`, `triggers`) y las secciones "Cuándo activar este Skill" e "Instrucciones para el agente" conforme al diseño
  - Escribir `README.md` con instrucciones de instalación, uso, descripción del `migration-manifest.json`, y ejemplos de invocación desde terminal y desde Kiro IDE
  - Crear el archivo vacío `skills/skill-01-analyzer/scripts/analyze_monolith.py` con el encabezado de módulo, imports de stdlib y las constantes globales (`ANALYZER_VERSION`, `SKILL_VERSION`, conjuntos de métodos HTTP válidos)
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 2. Implementar `BlueprintDiscoverer`
  - [x] 2.1 Implementar `BlueprintDiscoverer` con descubrimiento en dos pasos: parseo AST de `app/__init__.py` para extraer variables de blueprint y sus `url_prefix`, seguido de búsqueda recursiva de los archivos `routes.py` correspondientes
    - Usar `ast.parse()` para leer `app/__init__.py` sin ejecutar el código
    - Buscar nodos `ast.Call` con `func.attr == 'register_blueprint'` para extraer nombre de variable blueprint y keyword `url_prefix`
    - Recorrer recursivamente el directorio para encontrar el archivo `.py` que contenga la declaración `<nombre_variable> = Blueprint(...)`
    - Definir el `TypedDict` `BlueprintInfo` con campos: `prefix: str`, `routes_file: Path`, `module_name: str`
    - Manejar el caso en que `app/__init__.py` no pueda parsearse: registrar advertencia y usar heurísticas de nombre de directorio para inferir prefijos
    - _Requirements: 1.1, 5.2, 6.1, 6.2_

  - [x] 2.2 Escribir prueba unitaria para `BlueprintDiscoverer` sobre el monolito de referencia
    - Verificar que se descubren exactamente 5 blueprints: `auth_bp → /api/auth`, `clientes_bp → /api/clientes`, `servicios_bp → /api/servicios`, `transacciones_bp → /api/transacciones`, `reportes_bp → /api/reportes`
    - _Requirements: 1.1, 1.5_

- [ ] 3. Implementar `EndpointExtractor`
  - [x] 3.1 Implementar `EndpointExtractor` para parsear un archivo `routes.py` y extraer todas las funciones de ruta con sus metadatos básicos
    - Usar `ast.walk()` para encontrar nodos `ast.FunctionDef` con decoradores `@<bp_var>.route(...)`
    - Extraer método HTTP desde el keyword `methods` del decorador (valor por defecto `["GET"]` si ausente)
    - Construir la ruta URL completa concatenando `url_prefix` del blueprint con la ruta relativa del decorador
    - Convertir parámetros de Flask (`<int:var>`, `<string:var>`, `<var>`) al formato estándar `{var}` usando `re.sub(r'<(?:\w+:)?(\w+)>', r'{\1}', ruta_relativa)`
    - Detectar `auth_required`: verificar si `jwt_required` aparece en `decorator_list` como `ast.Call` o `ast.Name`
    - Detectar `admin_required`: buscar en el cuerpo de la función comparaciones con `get_jwt()['rol'] != 'admin'` o `claims.get('rol') != 'admin'`
    - Definir el dataclass `EndpointNode` con campos: `func_node`, `method`, `full_path`, `relative_path`, `auth_required`, `admin_required`, `module_name`, `func_name`
    - Construir el `id` del endpoint como `<module_name>.<func_name>`
    - _Requirements: 1.2, 1.3, 1.4, 1.7, 1.8_

  - [-] 3.2 Escribir prueba unitaria para `EndpointExtractor` sobre `auth/routes.py` del monolito de referencia
    - Verificar los 5 endpoints de auth con sus métodos HTTP, rutas completas, y flags `auth_required`/`admin_required` correctos
    - _Requirements: 1.2, 1.3, 1.4, 1.5_

- [ ] 4. Implementar detectores de anti-patrones a nivel de función (`AntiPatternRegistry` — detectores de función)
  - [-] 4.1 Implementar `LocalFilesystemDetector` (detecta `AP-local-filesystem`, GAP-02)
    - Buscar en el cuerpo de la función nodos `ast.Call` con `func.attr == 'save'` sobre objetos provenientes de `request.files`
    - Buscar llamadas a `os.path.join` con argumentos referenciando `UPLOAD_FOLDER` o `current_app.config['UPLOAD_FOLDER']`
    - Retornar `{code: "AP-local-filesystem", gap_ids: ["GAP-02"], severity: "critical"}` cuando el patrón es detectado
    - _Requirements: 2.2, 1.6_

  - [x] 4.2 Implementar `StrftimeDetector` (detecta `AP-strftime-sqlite`, GAP-04)
    - Buscar nodos `ast.Call` donde `func` es `ast.Attribute` con `attr == 'strftime'` y el objeto sobre el que se llama es a su vez un `ast.Call` (patrón: `func.strftime(formato, columna)`)
    - Retornar `{code: "AP-strftime-sqlite", gap_ids: ["GAP-04"], severity: "high"}`
    - _Requirements: 2.3_

  - [x] 4.3 Implementar `SessionDetector` (detecta `AP-session-flask`, GAP-06)
    - Buscar nodos `ast.Subscript` donde el valor es `ast.Name` con `id == 'session'` (patrón: `session['key']`)
    - Buscar nodos `ast.Call` con `func.attr == 'clear'` sobre `ast.Name` con `id == 'session'` (patrón: `session.clear()`)
    - Retornar `{code: "AP-session-flask", gap_ids: ["GAP-06"], severity: "medium"}`
    - _Requirements: 2.5_

  - [x] 4.4 Implementar `TimestampIdDetector` (detecta `AP-order-num-ts`, GAP-14)
    - Buscar nodos `ast.Call` a `datetime.utcnow()` cuyo resultado sea asignado a una variable usada posteriormente en una f-string (`ast.JoinedStr`) o en una llamada a `.strftime()`
    - Adicionalmente, analizar funciones auxiliares como `generar_numero_orden()` si se encuentran en el mismo workspace
    - Retornar `{code: "AP-order-num-ts", gap_ids: ["GAP-14"], severity: "medium"}`
    - _Requirements: 2.4_

  - [~] 4.5 Escribir pruebas unitarias para los cuatro detectores de función sobre el monolito de referencia
    - Verificar que `LocalFilesystemDetector` detecta `AP-local-filesystem` en `transacciones/routes.py` función `subir_adjunto()`
    - Verificar que `StrftimeDetector` detecta `AP-strftime-sqlite` en `reportes/routes.py`
    - Verificar que `SessionDetector` detecta `AP-session-flask` en `auth/routes.py` funciones `login()` y `logout()`
    - Verificar que `TimestampIdDetector` detecta `AP-order-num-ts` en `transacciones/routes.py`
    - Verificar independencia: la detección en una función no afecta el análisis de otras funciones del mismo archivo (Requirements 2.9)
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.9, 8.9_

- [ ] 5. Implementar detectores de anti-patrones a nivel de módulo (`AntiPatternRegistry` — detectores de módulo)
  - [x] 5.1 Implementar `TokenBlacklistDetector` (detecta `AP-token-blacklist`, GAP-03)
    - Detectar a nivel de módulo: buscar nodos `ast.Assign` donde el valor es `ast.Call` a `set()` y el objetivo es una variable a nivel de módulo (no local)
    - Verificar que en el cuerpo de alguna función de ruta del mismo módulo existe `.add()` sobre la misma variable
    - La combinación de ambos patrones activa el detector
    - Registrar el anti-patrón en el módulo y en el endpoint que contiene la llamada `.add()`
    - _Requirements: 2.1_

  - [x] 5.2 Implementar `CrossBlueprintDetector` (detecta `AP-cross-blueprint`)
    - Buscar en sentencias de importación de nivel de módulo (`ast.ImportFrom`) cuyo `module` siga el patrón `app.blueprints.<nombre_modulo>.routes`
    - Registrar el anti-patrón en todos los endpoints del módulo importador
    - Añadir la dependencia `"A → B"` al campo `cross_blueprint_imports` del módulo
    - _Requirements: 2.6, 2.8_

  - [x] 5.3 Implementar `InMemorySingletonDetector` (detecta `AP-in-memory-singleton`)
    - Detectar atributos de clase `_instancia = None` dentro de un método `__new__` que asigna a `cls._instancia` (patrón Singleton canónico)
    - Detectar variables de módulo tipo `_cache = {}` o `_historial = []` con nombres sugestivos de estado compartido
    - _Requirements: 2.7_

  - [x] 5.4 Implementar la clase `AntiPatternRegistry` que coordina todos los detectores
    - Mantener `FUNCTION_DETECTORS` (lista de detectores de función: `LocalFilesystemDetector`, `StrftimeDetector`, `SessionDetector`, `TimestampIdDetector`)
    - Mantener `MODULE_DETECTORS` (lista de detectores de módulo: `TokenBlacklistDetector`, `CrossBlueprintDetector`, `InMemorySingletonDetector`)
    - Implementar `analyze_module(module_tree, endpoints)` que ejecuta todos los detectores y retorna `ModuleAnalysisResult` con `endpoint_antipatterns`, `module_antipatterns` y `cross_blueprint_imports`
    - Garantizar que cada detector opera de forma independiente sobre su nodo AST correspondiente
    - _Requirements: 2.9_

  - [~] 5.5 Escribir pruebas unitarias para los detectores de módulo sobre el monolito de referencia
    - Verificar que `TokenBlacklistDetector` detecta `AP-token-blacklist` en `auth/routes.py` por `_tokens_revocados = set()` + `_tokens_revocados.add(jti)`
    - Verificar que `CrossBlueprintDetector` registra `"transacciones → clientes"` en `cross_blueprint_imports` por la importación `from app.blueprints.clientes.routes import verificar_cliente_existe`
    - Verificar que `CrossBlueprintDetector` registra `"reportes → servicios"` por la importación `from app.blueprints.servicios.routes import CATEGORIAS`
    - _Requirements: 2.1, 2.6, 2.8, 8.8_

- [~] 6. Checkpoint — verificar cobertura de detección antes de continuar
  - Asegurarse de que todas las pruebas unitarias de los detectores pasan. Consultar al usuario si hay dudas sobre el comportamiento esperado de algún detector sobre el monolito de referencia.

- [ ] 7. Implementar `ComplexityScorer` y `ComputeTargetClassifier`
  - [~] 7.1 Implementar `ComplexityScorer` con reglas de precedencia estrictamente ordenadas
    - `very_high`: `AP-local-filesystem` presente en el endpoint (precedencia máxima, aplica siempre)
    - `high`: `AP-strftime-sqlite` presente, O `AP-cross-blueprint` presente, O el cuerpo contiene llamadas a `notificacion_service.*`, O contiene un dict de transiciones de máquina de estados
    - `medium`: el cuerpo referencia `cache_service`, O importa modelos de múltiples dominios, O contiene `get_jwt_identity()` con lógica de negocio no trivial (más de una línea tras la extracción)
    - `low`: ninguna condición anterior aplica
    - Verificar los casos de ejemplo del diseño: `POST /api/transacciones/{id}/adjunto → very_high`, `GET /api/reportes/ingresos → high`, `GET /api/clientes/ → medium`, `POST /api/auth/register → low`
    - _Requirements: 1.6, 8.3_

  - [~] 7.2 Implementar `ComputeTargetClassifier` con árbol de decisión
    - `fargate`: el cuerpo contiene loops sobre colecciones no paginadas de tamaño indeterminado, O requiere estado temporal en sistema de archivos entre sub-invocaciones
    - `app_runner`: el módulo expone ÚNICAMENTE endpoints HTTP de lectura pública (sin JWT), sin operaciones de escritura ni efectos secundarios
    - `lambda` (por defecto): todos los demás casos
    - Si además tiene `AP-local-filesystem`: `lambda` + `requires_architectural_transformation: true`
    - Verificar el caso específico del monolito de referencia: todos los 29 endpoints clasifican como `lambda`, con `POST /api/transacciones/{id}/adjunto` recibiendo `requires_architectural_transformation: true`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [~] 7.3 Escribir pruebas unitarias para `ComplexityScorer` y `ComputeTargetClassifier`
    - Verificar las 5 filas de la tabla de ejemplos del diseño (complexity)
    - Verificar que `compute_target` es siempre uno de `{"lambda", "fargate", "app_runner"}` para inputs válidos
    - Verificar que `AP-local-filesystem` produce `requires_architectural_transformation: true` con `compute_target = "lambda"`
    - _Requirements: 3.4, 3.5, 3.6, 8.2, 8.3_

- [ ] 8. Implementar `ManifestBuilder`
  - [~] 8.1 Implementar la lógica de cálculo de `cohesion` e `isolation` de módulos
    - `cohesion: "high"`: todos los endpoints del módulo operan sobre la misma entidad de dominio
    - `cohesion: "medium"`: hay mezcla de responsabilidades (p. ej., `transacciones` mezcla CRUD, upload y máquina de estados)
    - `cohesion: "low"`: el módulo importa de múltiples dominios (p. ej., `reportes` importa 5 entidades distintas)
    - `isolation: "high"`: sin importaciones cross-blueprint ni exportaciones usadas externamente
    - `isolation: "medium"`: importaciones diferidas de modelos de otros dominios
    - `isolation: "low"`: importaciones directas desde otros blueprints
    - _Requirements: 4.3_

  - [~] 8.2 Implementar la derivación de `lambda_layers` recomendadas
    - `taller-db-layer`: consumido por todos los módulos (modelos SQLAlchemy + conexión RDS Proxy)
    - `taller-auth-layer`: consumido por `auth` y el autorizador Lambda de API GW (validación JWT + DynamoDB blacklist)
    - `taller-utils-layer`: consumido por todos los módulos (funciones auxiliares sin dependencias Flask)
    - _Requirements: 4.4_

  - [~] 8.3 Implementar la generación de `migration_sequence` con las 5 fases ordenadas por complejidad de acoplamiento creciente
    - Fase 1: `servicios` (menor acoplamiento, 3 endpoints públicos)
    - Fase 2: `auth` (establece autorizador Lambda compartido)
    - Fase 3: `clientes` (acoplamiento medio, requiere migrar `verificar_cliente_existe` a utils-layer)
    - Fase 4: `reportes` (read-only, solo requiere corrección `func.strftime`)
    - Fase 5: `transacciones` (mayor complejidad, requiere transformación de uploads y notificaciones)
    - Cada fase incluye `phase` (int), `module` (str), `justification` (str), y `prerequisites` (array de str)
    - _Requirements: 4.5, 4.10_

  - [~] 8.4 Implementar el ensamblaje del diccionario completo del manifiesto y la escritura a disco
    - Construir la sección `metadata` con `analyzed_at` (ISO 8601 UTC), `monolith_path` (ruta absoluta), `total_endpoints`, `analyzer_version`, `skill_version`, y `warnings`
    - Construir la sección `summary` con todos los contadores: `total_endpoints`, `lambda_candidates`, `fargate_candidates`, `app_runner_candidates`, `requires_transformation`, `critical_blockers`, `anti_pattern_summary`
    - Garantizar el invariante `summary.total_endpoints == Σ len(m["endpoints"]) ∀m ∈ manifest["modules"]` (I-1)
    - Garantizar el invariante `lambda_candidates + fargate_candidates + app_runner_candidates + requires_transformation == total_endpoints` (I-2)
    - Serializar con `json.dumps(manifest, indent=2, ensure_ascii=False)` — todos los campos deben ser tipos primitivos Python serializables por JSON (sin objetos `datetime`, `Path`, ni nodos `ast.AST`)
    - Implementar `write()` que escribe en `output_path` con fallback a `cwd` si no hay permisos de escritura
    - _Requirements: 4.1, 4.2, 4.3, 4.6, 4.7, 4.8, 4.9_

  - [~] 8.5 Escribir prueba unitaria para `ManifestBuilder` con datos del monolito de referencia
    - Verificar que `summary.total_endpoints = 29`, `lambda_candidates = 28`, `requires_transformation = 1`, `critical_blockers = 1`
    - Verificar la secuencia de migración: 5 fases en el orden `servicios → auth → clientes → reportes → transacciones`
    - Verificar que el manifiesto es completamente serializable con `json.dumps()` sin errores
    - _Requirements: 4.7, 4.8, 4.9, 4.10_

- [ ] 9. Implementar `main()` — punto de entrada CLI y manejo de errores
  - [~] 9.1 Implementar `main()` con `argparse` para la interfaz de línea de comandos
    - Parámetro obligatorio `--path <ruta_monolito>`
    - Parámetro opcional `--output <ruta_manifiesto>` (por defecto: `<path>/migration-manifest.json`)
    - Orquestar la cadena completa: `BlueprintDiscoverer → EndpointExtractor → AntiPatternRegistry → ComplexityScorer + ComputeTargetClassifier → ManifestBuilder`
    - _Requirements: 7.5_

  - [~] 9.2 Implementar manejo de errores fatales y tolerancia a fallos por archivo
    - Código de salida `1` + JSON a stderr con `"error": "MONOLITH_PATH_NOT_FOUND"` si el directorio no existe
    - Código de salida `2` + JSON a stderr con `"error": "NO_BLUEPRINTS_FOUND"` si no hay blueprints Flask
    - Código de salida `3` + intento de fallback a `cwd` si hay error de escritura del manifiesto
    - Omitir archivos Python con errores de sintaxis y registrar advertencia en `metadata.warnings`
    - Envolver toda la orquestación en `try/except Exception` de último recurso para garantizar que ninguna excepción no manejada llegue al usuario
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [~] 9.3 Escribir pruebas unitarias para los códigos de salida y mensajes de error
    - Verificar código de salida `1` y JSON con `"error": "MONOLITH_PATH_NOT_FOUND"` cuando el directorio no existe
    - Verificar código de salida `2` y JSON con `"error": "NO_BLUEPRINTS_FOUND"` cuando no hay blueprints
    - Verificar que archivos con error de sintaxis producen advertencia en `metadata.warnings` sin interrumpir el análisis
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [~] 10. Checkpoint — integración completa antes de las pruebas
  - Asegurarse de que todas las pruebas unitarias pasan y que el script puede ejecutarse end-to-end sin errores. Consultar al usuario si hay dudas antes de proceder a los tests de integración y propiedad.

- [ ] 11. Prueba de integración contra el monolito de referencia
  - [~] 11.1 Escribir `test_full_analysis_reference_monolith` que ejecuta `analyze_monolith.py --path monolith/` y valida el manifiesto completo
    - Verificar exactamente 29 endpoints distribuidos en 5 módulos (auth: 5, clientes: 6, servicios: 6, transacciones: 7, reportes: 5)
    - Verificar `summary.total_endpoints = 29`, `lambda_candidates = 28`, `requires_transformation = 1`, `critical_blockers = 1`
    - Verificar la presencia exacta de los 5 anti-patrones documentados: `AP-token-blacklist` en `auth`, `AP-local-filesystem` en `transacciones`, `AP-strftime-sqlite` en `reportes`, `AP-session-flask` en `auth`, `AP-order-num-ts` en `transacciones`
    - Verificar el endpoint `transacciones.subir_adjunto` con `compute_target = "lambda"`, `requires_architectural_transformation = true`, `migration_complexity = "very_high"`
    - Verificar que el archivo `monolith/migration-manifest.json` es producido y es JSON válido parseable con `json.loads()`
    - _Requirements: 1.5, 2.2-2.6, 3.6, 4.9, 4.10, 8.9_

  - [~] 11.2 Escribir pruebas de robustez con directorios sintéticos
    - Verificar comportamiento con directorio vacío: código de salida `2`, JSON con `"error": "NO_BLUEPRINTS_FOUND"`
    - Verificar comportamiento con directorio inexistente: código de salida `1`, JSON con `"error": "MONOLITH_PATH_NOT_FOUND"`
    - Verificar que un archivo Python con error de sintaxis no interrumpe el análisis de los demás archivos del mismo directorio
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 8.1_

- [ ] 12. Pruebas basadas en propiedades con `hypothesis`
  - [~] 12.1 Implementar los generadores sintéticos de blueprints Flask para `hypothesis`
    - `flask_route_function()`: genera código fuente de una función de ruta Flask aleatoria con método HTTP, ruta, decoradores JWT opcionales y anti-patrones controlables
    - `flask_blueprint_file()`: genera el código fuente completo de un archivo `routes.py` con N funciones de ruta (1 ≤ N ≤ 10)
    - Funciones auxiliares `temp_blueprint_dir()`, `temp_multi_blueprint_dir()` y `run_analyzer()` para ejecutar el analizador sobre los blueprints generados
    - _Requirements: 8.1–8.10_

  - [~] 12.2 Escribir prueba de Propiedad 1: Completitud de campos obligatorios de endpoint
    - Para cualquier blueprint Flask generado, cada endpoint extraído tiene los campos `id`, `method`, `path`, `auth_required`, `admin_required`, `compute_target`, `migration_complexity` con valores no nulos
    - `method` pertenece exclusivamente al conjunto `{"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}`
    - **Propiedad 1 — Validates: Requirements 1.2, 1.3, 1.4, 1.8, 8.2**

  - [~] 12.3 Escribir prueba de Propiedad 2: Dominio cerrado de `compute_target`
    - Para cualquier conjunto de blueprints Flask analizados, `compute_target` ∈ `{"lambda", "fargate", "app_runner"}` sin valores nulos ni fuera del conjunto
    - **Propiedad 2 — Validates: Requirements 3.4, 8.2**

  - [~] 12.4 Escribir prueba de Propiedad 3: Dominio cerrado y precedencia de `migration_complexity`
    - `migration_complexity` ∈ `{"low", "medium", "high", "very_high"}` para cualquier combinación de anti-patrones
    - Si `AP-local-filesystem` está presente, la complejidad es `"very_high"` independientemente de otros anti-patrones presentes
    - **Propiedad 3 — Validates: Requirements 1.6, 8.3**

  - [~] 12.5 Escribir prueba de Propiedad 4: Invariante de conteo del summary
    - `summary.total_endpoints == Σ len(m["endpoints"]) ∀m ∈ manifest["modules"]` para cualquier manifiesto generado
    - **Propiedad 4 — Validates: Requirements 4.7, 8.4**

  - [~] 12.6 Escribir prueba de Propiedad 5: Round-trip de serialización JSON
    - `json.loads(json.dumps(manifest))` produce un objeto con los mismos campos y valores que el original para los campos `metadata`, `summary`, `modules`, `lambda_layers`, `migration_sequence`
    - **Propiedad 5 — Validates: Requirements 4.8, 8.6**

  - [~] 12.7 Escribir prueba de Propiedad 6: Secuencia de migración no vacía
    - Para cualquier directorio de monolito que tenga al menos un módulo con endpoints, `migration_sequence` contiene al menos un elemento
    - **Propiedad 6 — Validates: Requirements 4.5, 8.5**

  - [~] 12.8 Escribir prueba de Propiedad 7: Detección del bloqueador crítico GAP-02
    - Para cualquier función de ruta POST con `archivo.save()` en el cuerpo, el Analizador produce exactamente un endpoint con `migration_complexity = "very_high"`, `compute_target = "lambda"`, `requires_architectural_transformation = true`, y `"GAP-02"` en `gap_ids`
    - **Propiedad 7 — Validates: Requirements 2.2, 3.5, 8.7**

  - [~] 12.9 Escribir prueba de Propiedad 8: Completitud de la detección cross-blueprint
    - Para cualquier par de módulos (A, B) donde `routes.py` de A importa de `app.blueprints.B.routes`, el Analizador registra `AP-cross-blueprint` en al menos un endpoint de A y lista `"A → B"` en `modules[A].cross_blueprint_imports`
    - **Propiedad 8 — Validates: Requirements 2.6, 2.8, 8.8**

  - [~] 12.10 Escribir prueba de Propiedad 9: Aislamiento de la detección por función
    - Para un archivo con N funciones de ruta donde exactamente K < N contienen `AP-strftime-sqlite`, el Analizador registra el anti-patrón en exactamente K endpoints
    - **Propiedad 9 — Validates: Requirements 2.9**

  - [~] 12.11 Escribir prueba de Propiedad 10: Partición completa del summary
    - `lambda_candidates + fargate_candidates + app_runner_candidates + requires_transformation == total_endpoints` para cualquier ejecución con 1–50 endpoints
    - **Propiedad 10 — Validates: Requirements 8.10**

  - [~] 12.12 Escribir prueba de robustez ante contenido arbitrario (Propiedad adicional — Requirements 8.1)
    - El Analizador nunca lanza excepciones no manejadas para cualquier contenido de archivos `.py`; el proceso termina siempre con código de salida en `{0, 1, 2, 3}`
    - **Validates: Requirements 5.4, 8.1**

- [ ] 13. Validación final — ejecutar el Analizador contra el monolito de referencia
  - [~] 13.1 Ejecutar `python skills/skill-01-analyzer/scripts/analyze_monolith.py --path monolith/` y verificar que produce `monolith/migration-manifest.json` sin errores
    - Confirmar que `migration-manifest.json` es JSON válido con todos los campos esperados
    - Confirmar `summary.total_endpoints = 29`, módulos correctos con endpoint counts correctos
    - Confirmar la presencia de los 5 anti-patrones documentados en los módulos correctos
    - Confirmar la secuencia de migración de 5 fases en el orden `servicios → auth → clientes → reportes → transacciones`
    - Confirmar tiempo de ejecución ≤ 30 segundos (Requirements 5.6)
    - _Requirements: 1.5, 4.9, 5.6, 6.4_

  - [~] 13.2 Verificar que el Analizador opera sin conectividad de red y sin dependencias externas
    - Confirmar que `analyze_monolith.py` no importa módulos fuera de `ast`, `os`, `json`, `pathlib`, `re`, `datetime`, `argparse`
    - Confirmar que no hay llamadas a `exec`, `eval`, `importlib.import_module` ni operaciones de red en el código de producción
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

---

## Notes

- Las sub-tareas marcadas con `*` son opcionales y pueden omitirse para un MVP más rápido, pero son importantes para el experimento comparativo de la tesis (evidencia cuantitativa de robustez)
- El script `analyze_monolith.py` es el único artefacto de código de producción; `hypothesis` es exclusivamente dependencia de desarrollo para los tests de propiedad
- Todos los componentes deben residir en el archivo único `skills/skill-01-analyzer/scripts/analyze_monolith.py` para cumplir el principio de cero dependencias de instalación
- Los tests de integración (tarea 11) y de propiedad (tarea 12) pueden colocarse en `skills/skill-01-analyzer/scripts/tests/` como archivos separados usando `pytest` + `hypothesis`
- La tarea 13 es la validación definitiva del contrato de datos que consumirán los Skills 02–05

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "3.1"] },
    { "id": 3, "tasks": ["3.2", "4.1", "4.2", "4.3", "4.4"] },
    { "id": 4, "tasks": ["4.5", "5.1", "5.2", "5.3"] },
    { "id": 5, "tasks": ["5.4"] },
    { "id": 6, "tasks": ["5.5", "7.1", "7.2"] },
    { "id": 7, "tasks": ["7.3", "8.1"] },
    { "id": 8, "tasks": ["8.2", "8.3"] },
    { "id": 9, "tasks": ["8.4"] },
    { "id": 10, "tasks": ["8.5", "9.1"] },
    { "id": 11, "tasks": ["9.2"] },
    { "id": 12, "tasks": ["9.3", "11.1"] },
    { "id": 13, "tasks": ["11.2", "12.1"] },
    { "id": 14, "tasks": ["12.2", "12.3", "12.4", "12.5", "12.6", "12.7", "12.8", "12.9", "12.10", "12.11", "12.12"] },
    { "id": 15, "tasks": ["13.1"] },
    { "id": 16, "tasks": ["13.2"] }
  ]
}
```
