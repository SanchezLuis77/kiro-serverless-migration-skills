# Requirements Document

## Introduction

El Skill 01 — Analizador de Monolito (`skill-01-analyzer`) es el punto de entrada de la cadena completa de migración asistida por Agent Skills. Su responsabilidad es examinar el código fuente de una aplicación Flask monolítica exclusivamente mediante análisis estático del árbol de sintaxis abstracta (AST), sin ejecutar el código ni transmitirlo a servicios externos, y producir un contrato de datos legible por máquina denominado `migration-manifest.json`.

Dicho manifiesto describe la estructura de módulos del monolito, cada endpoint REST descubierto, los anti-patrones de migración detectados con sus identificadores de brecha (GAP-IDs), la recomendación de destino de cómputo AWS para cada endpoint (Lambda, Fargate o App Runner), y la secuencia sugerida de migración siguiendo el patrón *Strangler Fig*. Los Skills 02, 03, 04 y 05 consumen el manifiesto como insumo, por lo que la exactitud, completitud y estructura del archivo JSON generado por este Skill son determinantes para la calidad del resto del pipeline.

El Skill se implementa como un paquete instalable en Kiro IDE siguiendo el estándar agentskills.io, con un script Python principal (`scripts/analyze_monolith.py`) que opera exclusivamente sobre archivos locales del workspace del desarrollador.

---

## Glossary

- **Analizador**: El componente `analyze_monolith.py` que ejecuta el análisis estático sobre el código fuente del monolito.
- **Anti-patrón**: Construcción de código que constituye un bloqueador o impedimento para la migración a arquitectura serverless, identificado mediante análisis AST.
- **AST** *(Abstract Syntax Tree)*: Representación en árbol de la estructura sintáctica de un archivo Python, producida por el módulo estándar `ast` de Python, sin necesidad de ejecutar el código.
- **Blueprint**: Módulo de enrutamiento de Flask que agrupa endpoints relacionados bajo un prefijo de URL común.
- **Brecha de migración** (GAP): Problema específico identificado en el experimento de automatización de base que requiere intervención manual si no es resuelto por los Skills. Referenciados por identificadores GAP-02, GAP-03, GAP-04, GAP-06, GAP-14.
- **Destino de cómputo**: Servicio AWS recomendado para alojar un endpoint migrado. Valores posibles: `lambda`, `fargate`, `app_runner`.
- **Endpoint**: Una ruta HTTP definida mediante un decorador `@bp.route(...)` dentro de un blueprint de Flask, caracterizada por método HTTP, ruta URL, requerimiento de autenticación y restricción de rol.
- **GAP-02**: Brecha crítica — almacenamiento de archivos en el sistema de archivos local (`archivo.save(ruta)`, `os.path.join(UPLOAD_FOLDER, ...)`), incompatible con el almacenamiento efímero de Lambda.
- **GAP-03**: Brecha de alta severidad — lista negra de tokens JWT almacenada en un `set()` en memoria del proceso (`_tokens_revocados`), con semántica *fail-open*.
- **GAP-04**: Brecha de alta severidad — uso de `func.strftime()` de SQLAlchemy, función exclusiva del dialecto SQLite incompatible con PostgreSQL/Aurora.
- **GAP-06**: Brecha de severidad media — uso de `session[...]` de Flask como mecanismo de autenticación complementario al JWT, incompatible con el modelo stateless de Lambda.
- **GAP-14**: Brecha de severidad media — generación de identificadores únicos basada en `datetime.utcnow()`, susceptible a colisiones bajo concurrencia.
- **Import cross-blueprint**: Importación directa desde el módulo `routes.py` de un blueprint hacia el módulo `routes.py` de otro blueprint, generando acoplamiento lateral incompatible con la arquitectura de funciones Lambda independientes.
- **JTI** *(JWT ID)*: Identificador único incluido en el payload de un token JWT, empleado para individualizar tokens en mecanismos de revocación.
- **Manifiesto de migración** (`migration-manifest.json`): Archivo JSON generado por el Analizador que constituye el contrato de datos entre los cinco Skills del pipeline de migración.
- **Monolito de referencia**: Aplicación Flask ubicada en `monolith/` del workspace, compuesta por 5 blueprints y 29 endpoints, utilizada como caso de prueba canónico del proyecto de investigación.
- **Singleton en memoria**: Instancia única de una clase cuyo estado se almacena en la memoria del proceso Python (p. ej., `CacheService`, `_tokens_revocados`), incompatible con el modelo de ejecución multi-instancia de Lambda.
- **Skill**: Paquete instalable en Kiro IDE que automatiza una etapa del pipeline de migración, siguiendo el estándar agentskills.io.

---

## Requirements

### Requirement 1: Descubrimiento de rutas Flask mediante análisis AST

**User Story:** Como desarrollador que instala el Skill 01 en Kiro IDE, quiero que el Analizador recorra automáticamente los blueprints Flask del monolito y extraiga todos los endpoints definidos, para obtener un inventario completo sin necesidad de ejecutar la aplicación ni inspeccionar el código manualmente.

#### Acceptance Criteria

1. WHEN el Analizador recibe la ruta de un directorio de monolito Flask válido, THE Analizador SHALL recorrer recursivamente todos los archivos Python (`*.py`) dentro de ese directorio en busca de definiciones de blueprints de Flask.

2. WHEN el Analizador encuentra un decorador `@<nombre_variable>.route(path, methods=[...])` sobre una función en un archivo Python, THE Analizador SHALL registrar el endpoint con los campos: método HTTP (`method`), ruta URL completa incluyendo el prefijo del blueprint (`path`), identificador único derivado del módulo y nombre de función (`id`), y nombre del módulo al que pertenece.

3. WHEN el Analizador detecta la presencia del decorador `@jwt_required()` en la cadena de decoradores de una función de ruta, THE Analizador SHALL establecer el campo `auth_required` del endpoint en `true`.

4. WHEN el Analizador detecta que el cuerpo de una función de ruta contiene la expresión `get_jwt()['rol'] != 'admin'` o `claims.get('rol') != 'admin'`, THE Analizador SHALL establecer el campo `admin_required` del endpoint en `true`.

5. WHEN el Analizador procesa el monolito de referencia ubicado en `monolith/` del workspace, THE Analizador SHALL descubrir exactamente 29 endpoints distribuidos en 5 módulos (auth: 5, clientes: 6, servicios: 6, transacciones: 7, reportes: 5).

6. THE Analizador SHALL asignar a cada endpoint un valor de `migration_complexity` conforme a las siguientes reglas mutuamente excluyentes, aplicadas en orden de precedencia decreciente:
   - `very_high`: el cuerpo de la función de ruta contiene escrituras al sistema de archivos local (GAP-02).
   - `high`: el cuerpo contiene `func.strftime` (GAP-04), importaciones cross-blueprint, efectos secundarios síncronos a servicios externos, o lógica de máquina de estados embebida en el controlador.
   - `medium`: el cuerpo contiene uso de `cache_service`, acceso a modelos de múltiples dominios, o `get_jwt_identity()` combinado con lógica de negocio.
   - `low`: ninguna de las condiciones anteriores aplica.

7. FOR ALL conjuntos de archivos Python sintácticamente válidos que contengan al menos un decorador `@bp.route`, THE Analizador SHALL descubrir al menos un endpoint por archivo que contenga dicho decorador.

8. FOR ALL endpoints descubiertos por el Analizador en cualquier monolito Flask válido, el campo `method` SHALL contener exclusivamente valores del conjunto `{"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}`.

---

### Requirement 2: Detección de anti-patrones bloqueadores de migración

**User Story:** Como arquitecto de soluciones que revisa el output del Skill 01, quiero que el Analizador identifique automáticamente los anti-patrones de código que bloquean o dificultan la migración a serverless, para poder planificar las refactorizaciones necesarias con sus identificadores de brecha documentados.

#### Acceptance Criteria

1. WHEN el Analizador detecta en un archivo Python una asignación de la forma `<nombre> = set()` a nivel de módulo seguida de operaciones `.add()` sobre esa variable dentro de funciones de ruta, THE Analizador SHALL registrar el anti-patrón `AP-token-blacklist` con `gap_ids: ["GAP-03"]` en el endpoint correspondiente y en el módulo que lo contiene.

2. WHEN el Analizador detecta en el cuerpo de una función de ruta una llamada al método `.save()` sobre un objeto de archivo (`request.files[...]`) o el uso de `os.path.join` con una variable que referencia la carpeta de uploads (`UPLOAD_FOLDER`), THE Analizador SHALL registrar el anti-patrón `AP-local-filesystem` con `gap_ids: ["GAP-02"]` en el endpoint correspondiente, establecer `migration_complexity` en `very_high`, y añadir `"GAP-02"` a la lista `gap_ids` del módulo.

3. WHEN el Analizador detecta en el cuerpo de una función de ruta la expresión `func.strftime(`, THE Analizador SHALL registrar el anti-patrón `AP-strftime-sqlite` con `gap_ids: ["GAP-04"]` en el endpoint correspondiente.

4. WHEN el Analizador detecta en el cuerpo de una función de ruta una llamada a `datetime.utcnow()` cuyo resultado se usa para construir un identificador de cadena de texto (concatenación con f-string o `strftime`), THE Analizador SHALL registrar el anti-patrón `AP-order-num-ts` con `gap_ids: ["GAP-14"]` en el endpoint correspondiente.

5. WHEN el Analizador detecta en el cuerpo de una función de ruta el acceso a la variable `session` de Flask mediante `session[...]` o `session.clear()`, THE Analizador SHALL registrar el anti-patrón `AP-session-flask` con `gap_ids: ["GAP-06"]` en el endpoint correspondiente.

6. WHEN el Analizador detecta en la sección de importaciones de nivel de módulo de un blueprint una sentencia `from app.blueprints.<modulo_a>.routes import <nombre>`, THE Analizador SHALL registrar el anti-patrón `AP-cross-blueprint` en cada endpoint del blueprint importador y añadir la dependencia al campo `cross_blueprint_imports` del módulo.

7. WHEN el Analizador detecta a nivel de módulo la declaración de un `set()` o `dict()` asignado a una variable con nombre sugestivo de singleton (p. ej., `_cache`, `_tokens_revocados`, `_historial`) o la presencia de un método `__new__` con un atributo de clase `_instancia`, THE Analizador SHALL registrar el anti-patrón `AP-in-memory-singleton` en el módulo correspondiente.

8. FOR ALL pares de blueprints (A, B) en cualquier monolito Flask analizado, IF el módulo A importa directamente desde `app.blueprints.B.routes`, THEN THE Analizador SHALL incluir la dependencia `A → B` en el campo `cross_blueprint_imports` del módulo A del manifiesto.

9. FOR ALL archivos Python analizados, THE Analizador SHALL detectar los anti-patrones AP-local-filesystem, AP-strftime-sqlite, AP-token-blacklist, AP-order-num-ts, AP-session-flask y AP-cross-blueprint de forma independiente para cada función de ruta, sin que la detección de un anti-patrón en una función afecte el análisis de las demás funciones del mismo archivo.

---

### Requirement 3: Clasificación del destino de cómputo AWS

**User Story:** Como arquitecto de soluciones que diseña la arquitectura serverless destino, quiero que el Analizador recomiende automáticamente si cada endpoint debe migrar a AWS Lambda, AWS Fargate o AWS App Runner, para disponer de una primera clasificación fundada en criterios técnicos objetivos del código.

#### Acceptance Criteria

1. THE Analizador SHALL clasificar un endpoint como `"lambda"` cuando el cuerpo de su función de ruta no contenga anti-patrones que indiquen duración de ejecución superior a 15 minutos, no requiera estado temporal persistente entre sub-invocaciones, y el patrón de invocación sea orientado a eventos discretos.

2. THE Analizador SHALL clasificar un endpoint como `"fargate"` cuando el análisis del cuerpo de la función indique operaciones de larga duración (procesamiento batch de archivos grandes, iteraciones sobre colecciones de tamaño indeterminado sin paginación) o requiera estado temporal en el sistema de archivos durante la ejecución.

3. THE Analizador SHALL clasificar un endpoint como `"app_runner"` cuando el módulo al que pertenece exponga únicamente endpoints HTTP síncronos de lectura pública con requisito de latencia baja y consistente, sin operaciones de escritura ni efectos secundarios complejos.

4. FOR ALL endpoints descubiertos en cualquier monolito Flask válido, THE Analizador SHALL asignar exactamente un valor del conjunto `{"lambda", "fargate", "app_runner"}` al campo `compute_target` de cada endpoint.

5. WHEN el Analizador clasifica un endpoint como `"very_high"` en `migration_complexity` debido al anti-patrón `AP-local-filesystem`, THE Analizador SHALL mantener el `compute_target` en `"lambda"` e incluir la nota `"requires_architectural_transformation": true` en el objeto del endpoint, indicando que la transformación al protocolo de presigned URL de S3 es un prerrequisito previo al despliegue.

6. WHEN el Analizador procesa el monolito de referencia, THE Analizador SHALL clasificar 28 endpoints como `"lambda"` y 1 endpoint (el correspondiente a `POST /api/transacciones/{id}/adjunto`) como `"lambda"` con `"requires_architectural_transformation": true`.

7. FOR ALL endpoints descubiertos, IF el valor de `compute_target` es `"lambda"` y el campo `requires_architectural_transformation` no está presente o es `false`, THEN THE Analizador SHALL incluir el endpoint en la lista de `lambda_candidates` del resumen del manifiesto.

---

### Requirement 4: Generación del manifiesto de migración (`migration-manifest.json`)

**User Story:** Como desarrollador del pipeline de Skills de migración, quiero que el Analizador produzca un archivo `migration-manifest.json` con estructura validable y predecible, para que los Skills 02, 03, 04 y 05 puedan consumirlo como contrato de datos sin ambigüedades.

#### Acceptance Criteria

1. WHEN el Analizador completa el análisis de un monolito Flask sin errores, THE Analizador SHALL escribir el archivo `migration-manifest.json` en el directorio raíz del monolito analizado, en formato JSON válido con indentación de 2 espacios.

2. THE Analizador SHALL incluir en el manifiesto una sección `metadata` con los campos: `analyzed_at` (fecha y hora ISO 8601 en UTC), `monolith_path` (ruta absoluta del directorio analizado), `total_endpoints` (número entero con el total de endpoints descubiertos), `analyzer_version` (cadena con la versión semántica del script), y `skill_version` (cadena con la versión semántica del Skill).

3. THE Analizador SHALL incluir en el manifiesto una sección `modules` como array de objetos, donde cada objeto representa un blueprint y contiene los campos: `name`, `blueprint_prefix`, `cohesion` (`"high"`, `"medium"` o `"low"`), `isolation` (`"high"`, `"medium"` o `"low"`), `anti_patterns` (array de objetos con `code`, `description`, `gap_ids`), `cross_blueprint_imports` (array de cadenas), y `endpoints` (array de objetos de endpoint).

4. THE Analizador SHALL incluir en el manifiesto una sección `lambda_layers` con la lista de Lambda Layers recomendadas para los módulos detectados, derivada del análisis de dependencias compartidas entre blueprints.

5. THE Analizador SHALL incluir en el manifiesto una sección `migration_sequence` como array de al menos una fase, donde cada fase contiene: `phase` (número entero), `module` (nombre del blueprint), `justification` (texto descriptivo), y `prerequisites` (array de cadenas con dependencias técnicas previas).

6. THE Analizador SHALL incluir en el manifiesto una sección `summary` con los campos: `total_endpoints`, `lambda_candidates`, `fargate_candidates`, `app_runner_candidates`, `requires_transformation`, `critical_blockers` (número de endpoints con `migration_complexity = "very_high"`), y `anti_pattern_summary` (objeto con conteo por código de anti-patrón).

7. FOR ALL manifiestos generados por el Analizador, el valor del campo `summary.total_endpoints` SHALL ser igual a la suma de los campos `endpoints.length` de todos los módulos en el array `modules`.

8. FOR ALL manifiestos válidos generados, la serialización del objeto de manifiesto a JSON seguida de su deserialización SHALL producir un objeto con los mismos campos y valores que el objeto original (propiedad de ida y vuelta de serialización).

9. WHEN el Analizador procesa el monolito de referencia, THE Analizador SHALL producir un manifiesto con `summary.total_endpoints = 29`, `summary.lambda_candidates = 28`, `summary.requires_transformation = 1`, y `summary.critical_blockers = 1`.

10. THE Analizador SHALL incluir en el campo `migration_sequence` del manifiesto del monolito de referencia las cinco fases en el orden: `servicios` (fase 1), `auth` (fase 2), `clientes` (fase 3), `reportes` (fase 4), `transacciones` (fase 5), conforme al orden de complejidad de acoplamiento creciente documentado en el análisis arquitectónico.

---

### Requirement 5: Resiliencia y manejo de errores

**User Story:** Como desarrollador que usa el Skill 01 en proyectos con código parcialmente completo o con errores de sintaxis, quiero que el Analizador siempre termine de forma controlada y reportada, para no interrumpir mi flujo de trabajo ni perder el análisis de los módulos correctamente formados.

#### Acceptance Criteria

1. IF el directorio proporcionado como ruta del monolito no existe en el sistema de archivos, THEN THE Analizador SHALL terminar con código de salida distinto de cero y escribir en la salida de error estándar un mensaje JSON con el campo `error: "MONOLITH_PATH_NOT_FOUND"` y la ruta que no pudo resolverse.

2. IF un archivo Python dentro del directorio del monolito contiene errores de sintaxis que impiden la construcción del AST, THEN THE Analizador SHALL omitir ese archivo, registrar una advertencia en el campo `warnings` del manifiesto con el nombre del archivo y el mensaje de error de sintaxis, y continuar analizando los demás archivos.

3. IF el Analizador no encuentra ningún archivo Python con decoradores `@bp.route(...)` en el directorio proporcionado, THEN THE Analizador SHALL terminar con código de salida distinto de cero y escribir un mensaje JSON con el campo `error: "NO_BLUEPRINTS_FOUND"`.

4. FOR ALL rutas de directorio válidas del sistema de archivos proporcionadas al Analizador, ya sean directorios de monolitos Flask completos, directorios vacíos, o directorios con archivos Python sin blueprints, THE Analizador SHALL terminar sin lanzar excepciones no manejadas (`unhandled exceptions`) en el proceso Python.

5. IF el directorio de destino para escribir `migration-manifest.json` no tiene permisos de escritura, THEN THE Analizador SHALL escribir el manifiesto en el directorio de trabajo actual (`cwd`) como alternativa y registrar una advertencia en la salida estándar indicando la ruta alternativa utilizada.

6. THE Analizador SHALL completar el análisis del monolito de referencia (`monolith/`) en un tiempo máximo de 30 segundos en un entorno de ejecución con al menos 1 vCPU y 512 MB de RAM disponibles.

---

### Requirement 6: Operación en privacidad (análisis local)

**User Story:** Como desarrollador corporativo que trabaja con código propietario, quiero que el Analizador opere exclusivamente sobre archivos locales del workspace sin transmitir el código fuente a ningún servicio externo, para cumplir con las políticas de seguridad y privacidad de mi organización.

#### Acceptance Criteria

1. THE Analizador SHALL operar exclusivamente mediante el módulo estándar `ast` de Python para la construcción y recorrido del árbol de sintaxis abstracta, sin importar ni invocar bibliotecas que realicen llamadas de red.

2. THE Analizador SHALL leer los archivos Python del monolito como cadenas de texto en memoria y construir los árboles AST a partir de dichas cadenas, sin ejecutar (`exec`, `eval`, `importlib.import_module`) ningún fragmento del código fuente del monolito.

3. THE Analizador SHALL utilizar únicamente módulos de la biblioteca estándar de Python (`ast`, `os`, `json`, `datetime`, `pathlib`, `re`) para la lógica de análisis y generación del manifiesto, sin dependencias externas adicionales.

4. WHERE el desarrollador ejecute el Analizador en un entorno sin acceso a internet, THE Analizador SHALL completar el análisis exitosamente sin requerir conectividad de red para ninguna de sus operaciones.

---

### Requirement 7: Estructura del Skill (estándar agentskills.io)

**User Story:** Como desarrollador que instala Skills en Kiro IDE, quiero que el Skill 01 cumpla el estándar estructural de agentskills.io con metadatos completos y documentación clara, para poder instalarlo, activarlo y usarlo siguiendo los mecanismos estándar de Kiro.

#### Acceptance Criteria

1. THE Skill SHALL incluir un archivo `SKILL.md` en la raíz del directorio `skills/skill-01-analyzer/` con un bloque de metadatos YAML que contenga los campos obligatorios: `name`, `version`, `description`, `author`, `tags`, y `triggers`.

2. THE Skill SHALL incluir en `SKILL.md` una sección "Cuándo activar este Skill" que describa los disparadores semánticos que llevan a Kiro a activar el Skill (palabras clave como "analizar", "migrar", "monolito", "serverless", "lambda").

3. THE Skill SHALL incluir en `SKILL.md` una sección "Instrucciones para el agente" con los pasos que el agente debe seguir para invocar `analyze_monolith.py`, interpretar su salida y presentar el resumen al desarrollador.

4. THE Skill SHALL incluir un archivo `README.md` con instrucciones de instalación, uso, descripción del `migration-manifest.json` generado, y ejemplos de invocación desde la terminal y desde Kiro IDE.

5. THE Skill SHALL incluir el script `scripts/analyze_monolith.py` compatible con Python 3.9 o superior, con una interfaz de línea de comandos que acepte el parámetro `--path <ruta_monolito>` y el parámetro opcional `--output <ruta_destino_manifiesto>`.

6. WHERE el desarrollador instale el Skill en un entorno con Python 3.9 o superior disponible y ejecute el caso de uso básico de análisis AST y generación del manifiesto, THE Skill SHALL ejecutarse sin requerir la instalación de paquetes adicionales mediante `pip`; IF el Skill utiliza paquetes externos para funcionalidades opcionales (por ejemplo, generación de reportes en formatos adicionales), THEN THE Skill SHALL documentarlos como prerrequisitos opcionales en el archivo `README.md` con el comando `pip install` correspondiente.

---

### Requirement 8: Propiedades de corrección para pruebas basadas en propiedades

**User Story:** Como investigador que evalúa la calidad del Skill 01, quiero que el Analizador exhiba propiedades de corrección verificables automáticamente, para poder incluir evidencia cuantitativa de robustez en el experimento comparativo de la tesis.

#### Acceptance Criteria

1. FOR ALL directorios de workspace válidos del sistema de archivos local proporcionados como argumento `--path`, THE Analizador SHALL terminar sin lanzar excepciones no manejadas, independientemente del contenido de los archivos Python encontrados.

2. FOR ALL endpoints descubiertos en cualquier ejecución del Analizador, THE campo `compute_target` SHALL contener exclusivamente uno de los valores `"lambda"`, `"fargate"` o `"app_runner"`, sin valores nulos ni valores fuera de ese conjunto.

3. FOR ALL endpoints descubiertos, THE campo `migration_complexity` SHALL contener exclusivamente uno de los valores `"low"`, `"medium"`, `"high"` o `"very_high"`, sin valores nulos ni valores fuera de ese conjunto.

4. FOR ALL manifiestos generados, THE valor del campo `summary.total_endpoints` SHALL ser igual a la suma de `len(modulo["endpoints"])` para todo módulo en `manifest["modules"]` (invariante de conteo).

5. FOR ALL manifiestos generados, THE array `migration_sequence` SHALL contener al menos un elemento (invariante de secuencia no vacía).

6. FOR ALL manifiestos generados, THE serialización del manifiesto a JSON seguida de su deserialización con `json.loads(json.dumps(manifest))` SHALL producir un objeto `dict` cuyos campos `summary`, `modules`, `lambda_layers`, y `migration_sequence` sean iguales a los del objeto original (propiedad de ida y vuelta de serialización JSON).

7. FOR ALL archivos Python que contengan exactamente una función decorada con `@bp.route(path, methods=["POST"])` y en cuyo cuerpo aparezca `archivo.save(`, THE Analizador SHALL producir exactamente un endpoint con `migration_complexity = "very_high"` y con `"GAP-02"` presente en el campo `gap_ids` del endpoint.

8. FOR ALL pares de módulos (A, B) donde el archivo `routes.py` de A contiene la sentencia `from app.blueprints.B.routes import`, THE Analizador SHALL registrar el anti-patrón `AP-cross-blueprint` en al menos un endpoint del módulo A y listar la dependencia `"A → B"` en `modules[A].cross_blueprint_imports`.

9. WHEN el Analizador procesa el monolito de referencia, THE Analizador SHALL detectar exactamente los siguientes anti-patrones documentados: `AP-token-blacklist` en el módulo `auth`, `AP-local-filesystem` en el módulo `transacciones`, `AP-strftime-sqlite` en el módulo `reportes`, `AP-session-flask` en el módulo `auth`, y `AP-order-num-ts` en el módulo `transacciones`.

10. FOR ALL ejecuciones del Analizador sobre blueprints Flask sintéticamente generados que contengan entre 1 y 50 endpoints con combinaciones arbitrarias de métodos HTTP, decoradores JWT y anti-patrones, THE suma de `lambda_candidates + fargate_candidates + app_runner_candidates + requires_transformation` en el campo `summary` SHALL ser igual a `summary.total_endpoints`.
