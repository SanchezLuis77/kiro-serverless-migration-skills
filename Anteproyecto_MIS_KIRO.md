![](_page_0_Picture_0.jpeg)

# Dise˜no y Evaluaci´on de Agent Skills para Kiro IDE Orientados a la Migraci´on de Aplicaciones Monol´ıticas a Arquitecturas Serverless en AWS

# Luis Gerardo S´anchez Ord´o˜nez

Anteproyecto presentado como requisito parcial para optar al t´ıtulo de: Magister en Ingenier´ıa de Software

> Director(a): Mgr. Juan Gabriel Quintero Barbosa

Pontificia Universidad Javeriana Cali Facultad de Ingenier´ıa y Ciencias Departamento de Electr´onica y Ciencias de la Computaci´on Cali, Colombia 24 de junio de 2026

# Ficha Resumen

# Anteproyecto de Trabajo de Grado

Posible T´ıtulo: Dise˜no y Evaluaci´on de Agent Skills para Kiro IDE Orientados a la Migraci´on de Aplicaciones Monol´ıticas a Arquitecturas Serverless en AWS

- 1. Area de trabajo: Ingenier´ıa de Software / Arquitectura Cloud ´
- 2. Tipo de proyecto (Aplicado, Innovaci´on, Investigaci´on): Aplicado e Innovaci´on
- 3. Estudiante: Luis Gerardo S´anchez Ord´o˜nez
- 4. Correo electr´onico: sanchezluis777@javerianacali.edu.co
- 5. Direcci´on y tel´efono: Calle 38an No 2an-06 Prados del norte, 3168647407
- 6. Director: Juan Gabriel Quintero Barbosa, Mgr.
- 7. Vinculaci´on del director: Head Solutions Architecture, Amazon Web Services Colombia
- 8. Correo electr´onico del director: jgquint@amazon.com
- 9. Co-Director (Si aplica):
- 10. Grupo o empresa que lo avala (Si aplica):
- 11. Otros grupos o empresas:
- 12. ODS que aplica al proyecto (Agenda 2030): ODS 9 Industria, innovaci´on e infraestructura
- 13. Palabras clave : Agent Skills, Kiro IDE, Migraci´on Serverless, AWS Lambda, Gap Analysis, IA Generativa, Strangler Fig
- 14. Fecha de inicio: Segundo semestre 2026
- 15. Duraci´on estimada : cinco meses
- 16. Resumen:

El presente trabajo de grado propone el dise˜no, desarrollo y evaluaci´on de un conjunto de Agent Skills especializados para Kiro IDE, orientados a reducir las brechas de automatizaci´on que las herramientas de IA generativa exhiben al migrar aplicaciones monol´ıticas Flask a arquitecturas serverless en Amazon Web Services (AWS). La investigaci´on parte de un experimento emp´ırico preliminar en el que se le solicit´o a dos herramientas de IA —Claude (Anthropic) y Kiro (AWS)— que convirtieran la misma aplicaci´on monol´ıtica a serverless. Los resultados revelaron que Claude alcanz´o aproximadamente un 18 % de cobertura funcional, mientras que Kiro logr´o un 62 %, pero ambas fallaron sistem´aticamente en las mismas ´areas: la capa de persistencia (sin generaci´on de RDS, VPC ni migraciones de esquema), la capa de autenticaci´on durante la coexistencia monolito-Lambda, la capa de observabilidad (sin alarmas ni dashboards), y el plano operacional (sin tests, CI/CD completo ni rollback granular). A partir de estos hallazgos, se propone desarrollar cinco Agent Skills siguiendo el est´andar abierto agentskills.io: (1) un analizador de monolitos que genera un manifiesto de migraci´on con recomendaci´on de servicio objetivo por endpoint (Lambda, Fargate o App Runner); (2) un migrador de persistencia que genera la infraestructura de base de datos y adapta los modelos ORM; (3) un orquestador de coexistencia Strangler Fig; (4) un migrador de uploads con evaluaci´on de estrategias de almacenamiento; y (5) un validador post-generaci´on que verifica la completitud del output. La evaluaci´on se realizar´a comparando cuantitativamente la cobertura de migraci´on de Kiro sin Skills (baseline: 62 %) versus Kiro con los Skills instalados, sobre el mismo monolito de referencia. Se espera que los Skills incrementen la cobertura funcional por encima del 85 %, reduciendo el esfuerzo residual de intervenci´on humana. Los Skills ser´an publicados como c´odigo abierto, contribuyendo al ecosistema de la comunidad de Kiro.

# ´Indice

| 1. | Planteamiento y Justificaci´on del Problema |                                                  |    |  |  |
|----|---------------------------------------------|--------------------------------------------------|----|--|--|
|    | 1.1.                                        | Planteamiento                                    | 6  |  |  |
|    | 1.2.                                        | Justificaci´on                                   | 8  |  |  |
| 2. |                                             | Objetivos del proyecto                           | 9  |  |  |
|    | 2.1.                                        | Objetivo General<br>                             | 9  |  |  |
|    | 2.2.                                        | Objetivos espec´ıficos<br>                       | 9  |  |  |
| 3. |                                             | Alcance del Proyecto                             | 10 |  |  |
| 4. | Marco te´orico y antecedentes               |                                                  |    |  |  |
|    | 4.1.                                        | Bases Te´oricas                                  | 12 |  |  |
|    | 4.2.                                        | Antecedentes<br>                                 | 14 |  |  |
| 5. | Riesgos                                     | ´<br>Eticos                                      | 17 |  |  |
| 6. |                                             | Metodolog´ıa del Proyecto                        | 18 |  |  |
|    | 6.1.                                        | Justificaci´on de la Elecci´on Metodol´ogica<br> | 18 |  |  |
|    | 6.2.                                        | Justificaci´on de la Estrategia General<br>      | 18 |  |  |
|    | 6.3.                                        | Enfoque, T´ecnicas y Herramientas                | 19 |  |  |
|    | 6.4.                                        | Fases del Trabajo y Relaci´on con los Objetivos  | 19 |  |  |
|    | 6.5.                                        | Recopilaci´on y An´alisis de Datos<br>           | 20 |  |  |
| 7. |                                             | Cronograma                                       | 21 |  |  |

# ´Indice de figuras

# ´Indice de tablas

| 1. | Comparaci´on de propuestas existentes frente a las necesidades de la |    |
|----|----------------------------------------------------------------------|----|
|    | migraci´on serverless en AWS                                         | 16 |
| 2. | Distribuci´on de horas por fase del proyecto                         | 22 |
| 3. | Cronograma general de ejecuci´on del proyecto (5 meses)              | 23 |

# <span id="page-5-0"></span>1. Planteamiento y Justificaci´on del Problema

### <span id="page-5-1"></span>1.1. Planteamiento

La adopci´on de IDEs ag´enticos con capacidades de inteligencia artificial generativa ha transformado radicalmente la pr´actica del desarrollo de software. Herramientas como Kiro (AWS), Cursor, GitHub Copilot y Claude Code permiten a los desarrolladores generar c´odigo, refactorizar m´odulos y construir aplicaciones completas mediante instrucciones en lenguaje natural [Amazon Web Services](#page-24-0) [\(2025c\)](#page-24-0). Sin embargo, cuando estas herramientas se aplican a tareas de alta complejidad arquitect´onica —como la migraci´on de aplicaciones monol´ıticas a arquitecturas serverless en la nube— su efectividad se degrada significativamente, dejando brechas (gaps) que requieren intervenci´on humana experta para ser resueltas.

Un experimento emp´ırico preliminar realizado como parte de esta investigaci´on evidenci´o la magnitud de estas brechas. Se tom´o una aplicaci´on monol´ıtica en Flask (5 m´odulos, 29 endpoints, 5 tablas en SQLite) y se le solicit´o a dos herramientas de IA generativa que la convirtieran a una arquitectura serverless en AWS. Los resultados fueron reveladores: Claude (Anthropic) logr´o aproximadamente un 18 % de cobertura funcional, generando solo 4 de 29 funciones Lambda con c´odigo funcional y documentando 78 gaps. Kiro (AWS), con su enfoque de desarrollo basado en especificaciones, alcanz´o un 62 % de automatizaci´on, portando la l´ogica de negocio con alta fidelidad, pero a´un as´ı document´o 14 gaps con un esfuerzo estimado de 37 a 40 d´ıas-persona para cerrarlos.

Lo m´as significativo del experimento es que ambas herramientas fallaron sistem´aticamente en las mismas ´areas, independientemente de su nivel de sofisticaci´on. Las brechas se concentran en cuatro capas cr´ıticas: (1) la capa de persistencia, donde ninguna herramienta gener´o la infraestructura de base de datos necesaria (RDS, VPC, subnets, security groups, RDS Proxy), ni los scripts de migraci´on de esquema de SQLite a PostgreSQL, ni la adaptaci´on de funciones SQL no portables entre motores; (2) la capa de autenticaci´on y coexistencia, donde los tokens JWT generados por el monolito y por las funciones Lambda resultaron incompatibles durante la fase de coexistencia del patr´on Strangler Fig, y mecanismos como el blacklist de tokens en memoria carecen de equivalente en un entorno serverless sin estado; (3) la capa de observabilidad, donde ninguna herramienta configur´o alarmas, dashboards ni m´etricas personalizadas de CloudWatch; y (4) el plano operacional, donde no se generaron tests unitarios ni de integraci´on, ni scripts de migraci´on de datos, ni mecanismos de rollback granular por m´odulo en los pipelines de CI/CD.

Las causas fundamentales de estas brechas se clasifican en cuatro categor´ıas, seg´un el an´alisis de causa ra´ız realizado: falta de informaci´on de contexto del entorno de despliegue (la IA no conoce la VPC, las credenciales ni la infraestructura existente), decisiones arquitect´onicas con tradeoffs que requieren juicio humano (Lambda vs. Fargate, pre-signed URLs vs. CloudFront, arquitectura hexagonal vs. capas simples), cambios de contrato externo que no pueden inferirse autom´aticamente (breaking changes en la API al migrar uploads de filesystem a S3), y ausencia de c´odigo de infraestructura y operaciones que no forma parte de la l´ogica de negocio pero es indispensable para el despliegue.

Kiro IDE, el entorno de desarrollo ag´entico de AWS, ofrece un mecanismo extensible denominado Agent Skills: paquetes portables de instrucciones, scripts y recursos que dotan al agente de conocimiento especializado en dominios espec´ıficos [Amazon](#page-24-1) [Web Services](#page-24-1) [\(2025a\)](#page-24-1). Este mecanismo, basado en el est´andar abierto Agent Skills, permite a la comunidad de desarrolladores crear y compartir conocimiento que complementa las capacidades nativas del agente. Actualmente, Kiro cuenta con Powers para tecnolog´ıas como Stripe, Neon, Supabase y AWS SAM, pero no existe ning´un Skill ni Power especializado en la migraci´on integral de monolitos a arquitecturas serverless que aborde las brechas identificadas.

Ante este panorama, el presente proyecto plantea la siguiente pregunta de investigaci´on: ¿En qu´e medida un conjunto de Agent Skills especializados para Kiro IDE puede reducir las brechas de automatizaci´on identificadas en la migraci´on de aplicaciones monol´ıticas Flask a arquitecturas serverless en AWS, particularmente en las capas de persistencia, autenticaci´on, observabilidad y operaci´on?

### <span id="page-7-0"></span>1.2. Justificaci´on

Abordar las brechas de automatizaci´on en la migraci´on a arquitecturas serverless es relevante desde m´ultiples perspectivas. Desde el punto de vista t´ecnico y acad´emico, este proyecto contribuye a un campo emergente en la ingenier´ıa de software: la evaluaci´on emp´ırica de las capacidades y limitaciones de los IDEs ag´enticos como herramientas de transformaci´on arquitect´onica. A diferencia de los estudios existentes que eval´uan la generaci´on de c´odigo aislado [Pan et al.](#page-25-0) [\(2026\)](#page-25-0), esta investigaci´on examina el espectro completo de una migraci´on real —desde el an´alisis est´atico del c´odigo fuente hasta el despliegue funcional en la nube— y propone artefactos concretos (Skills) que cierran las brechas medidas. Adem´as, el uso del est´andar abierto Agent Skills garantiza que los resultados sean reproducibles y extensibles por la comunidad acad´emica.

Desde la perspectiva econ´omica y social, la migraci´on a serverless sigue siendo una necesidad cr´ıtica para las organizaciones que buscan optimizar costos operativos mediante modelos de pago por consumo [Timmer](#page-25-1) [\(2024\)](#page-25-1). En el contexto colombiano, donde el 61 % del ecosistema de software son microempresas y el 23 % peque˜nas empresas [Fedesoft](#page-24-2) [\(2025\)](#page-24-2), la barrera no es la disponibilidad de la tecnolog´ıa sino la complejidad de adoptarla correctamente [MinTIC](#page-25-2) [\(2024\)](#page-25-2). Si los IDEs ag´enticos no logran automatizar completamente la migraci´on, los equipos peque˜nos siguen necesitando conocimiento experto en arquitectura cloud que no pueden costear. Los Skills propuestos buscan cerrar esa brecha, encapsulando el conocimiento de un Solutions Architect en artefactos reutilizables que cualquier desarrollador puede instalar en Kiro con un solo clic.

Desde la perspectiva de contribuci´on a la comunidad, el resultado de este proyecto ser´a publicado como un conjunto de Skills de c´odigo abierto, instalables desde el marketplace de Kiro o directamente desde un repositorio de GitHub. Esto posiciona al investigador como contribuyente activo del ecosistema de herramientas de desarrollo de AWS, y genera un artefacto con impacto pr´actico m´as all´a del ´ambito acad´emico.

Finalmente, este proyecto se alinea estrat´egicamente con el ODS 9 (Indus-

tria, Innovaci´on e Infraestructura), al facilitar la adopci´on de infraestructuras tecnol´ogicas modernas mediante herramientas que democratizan el conocimiento especializado. La premisa central es que la IA generativa, complementada con conocimiento de dominio estructurado (Skills), puede superar las limitaciones que exhibe cuando opera sin contexto especializado —y medir esa mejora de forma rigurosa es el aporte principal de esta investigaci´on.

# <span id="page-8-0"></span>2. Objetivos del proyecto

### <span id="page-8-1"></span>2.1. Objetivo General

Dise˜nar, desarrollar y evaluar un conjunto de Agent Skills para Kiro IDE que reduzcan las brechas de automatizaci´on en la migraci´on de aplicaciones monol´ıticas Flask a arquitecturas serverless en Amazon Web Services, particularmente en las capas de persistencia, autenticaci´on, observabilidad y operaci´on.

### <span id="page-8-2"></span>2.2. Objetivos espec´ıficos

- 1. Caracterizar emp´ıricamente las brechas de automatizaci´on que presentan las herramientas de IA generativa al migrar una aplicaci´on monol´ıtica Flask a una arquitectura serverless en AWS, mediante la ejecuci´on de experimentos controlados con Claude y Kiro sobre un monolito de referencia, clasificando los gaps por capa arquitect´onica, causa ra´ız y severidad.
- 2. Dise˜nar la arquitectura y especificaci´on funcional de los Agent Skills propuestos, definiendo para cada Skill su alcance, instrucciones de dominio, scripts de an´alisis y plantillas de referencia, alineados con el est´andar abierto Agent Skills y con las capacidades de extensi´on de Kiro IDE (steering, hooks, Powers).
- 3. Construir los Agent Skills especializados integrando an´alisis est´atico de c´odigo fuente, generaci´on de Infraestructura como C´odigo para servicios nativos de AWS (Lambda, Fargate, API Gateway, Aurora Serverless, S3, CloudWatch), y

l´ogica de recomendaci´on arquitect´onica por endpoint (servicio objetivo y patr´on de dise˜no).

4. Evaluar la efectividad de los Agent Skills desarrollados mediante la comparaci´on cuantitativa de la cobertura de migraci´on de Kiro sin Skills (baseline) versus Kiro con los Skills instalados, utilizando m´etricas de cobertura funcional, esfuerzo residual de intervenci´on humana y desplegabilidad del output generado, sobre el mismo monolito de referencia.

# <span id="page-9-0"></span>3. Alcance del Proyecto

El alcance de este proyecto comprende el dise˜no, construcci´on y evaluaci´on de Agent Skills para Kiro IDE, enfocados en las brechas de automatizaci´on documentadas emp´ıricamente durante la migraci´on de aplicaciones monol´ıticas Flask a arquitecturas serverless en AWS. El proyecto se ejecutar´a dentro de las 192 horas de esfuerzo estipuladas para cinco meses.

Alcance t´ecnico y funcional. Los Skills se desarrollar´an exclusivamente para Kiro IDE siguiendo el est´andar abierto Agent Skills (archivos SKILL.md con instrucciones, scripts en Python y plantillas de referencia). El monolito de referencia para la evaluaci´on ser´a una aplicaci´on Flask con un m´ınimo de 5 m´odulos, 20 endpoints y 4 tablas interrelacionadas, construida para representar un caso realista de una Py-ME. Los servicios de AWS objetivo incluyen Lambda, Fargate, App Runner, API Gateway, Aurora Serverless v2, RDS Proxy, S3, CloudWatch, X-Ray y SSM Parameter Store. La generaci´on de Infraestructura como C´odigo se realizar´a con AWS SAM. El Skill de an´alisis incluir´a recomendaci´on de servicio objetivo por endpoint (Lambda, Fargate o App Runner) y recomendaci´on de patr´on arquitect´onico seg´un la complejidad del componente.

Limitaciones y exclusiones. Los Skills operar´an exclusivamente sobre monolitos escritos en Python; otros frameworks y lenguajes quedan fuera del alcance. No se contempla la integraci´on con proveedores de nube distintos a AWS. Los Skills no realizar´an refactorizaci´on autom´atica de la l´ogica de negocio ni migraci´on de datos en producci´on; su funci´on es generar la infraestructura, las plantillas y las recomendaciones para que el desarrollador ejecute la migraci´on de forma asistida. La evaluaci´on se realizar´a en un entorno controlado de pruebas, no en un ambiente de producci´on empresarial.

Supuestos. Se asume que se dispondr´a de acceso a una cuenta de AWS para validar la desplegabilidad del output generado por los Skills, que Kiro IDE mantendr´a compatibilidad con el est´andar Agent Skills durante el periodo de ejecuci´on del proyecto, y que el monolito de referencia ser´a construido previamente como insumo del proyecto.

# <span id="page-11-0"></span>4. Marco te´orico y antecedentes

### <span id="page-11-1"></span>4.1. Bases Te´oricas

#### IDEs Ag´enticos y Archivos de Contexto

Los IDEs ag´enticos constituyen una categor´ıa emergente de herramientas en la que un agente de IA planifica, ejecuta y encadena tareas complejas de desarrollo de forma aut´onoma, interactuando con el sistema de archivos, el compilador y los servicios externos [Horikawa et al.](#page-25-3) [\(2025\)](#page-25-3). Kiro, el IDE ag´entico de AWS, introduce el paradigma de spec-driven development: el agente recibe una especificaci´on en lenguaje natural y genera requerimientos, dise˜no y c´odigo de forma iterativa [Amazon](#page-24-0) [Web Services](#page-24-0) [\(2025c\)](#page-24-0).

Central a estos entornos son los archivos de contexto del agente: documentos que proveen instrucciones persistentes a nivel de proyecto. [Chatlatanagulchai et al.](#page-24-3) [\(2025\)](#page-24-3) condujeron el primer estudio emp´ırico a gran escala de 2.303 archivos de contexto en 1.925 repositorios, encontrando que los desarrolladores priorizan el contexto funcional pero rara vez especifican restricciones no funcionales como seguridad o rendimiento. Esta brecha es el fundamento te´orico de los Agent Skills propuestos: artefactos especializados que llenan sistem´aticamente ese vac´ıo para el dominio espec´ıfico de la migraci´on serverless en AWS.

#### Agent Skills como Mecanismo de Extensi´on

El est´andar abierto Agent Skills [Anthropic](#page-24-4) [\(2025\)](#page-24-4) define un formato portable para empaquetar instrucciones especializadas, scripts y plantillas de referencia que dotan a un agente de conocimiento de dominio. Un Skill consiste en una carpeta con un archivo SKILL.md (instrucciones en Markdown con metadatos YAML) y opcionalmente scripts ejecutables y documentaci´on de referencia. Kiro IDE adopta este est´andar y lo extiende con el concepto de Powers: paquetes que combinan Skills, servidores MCP y reglas de steering para dominios espec´ıficos [Amazon Web Services](#page-24-5) [\(2025d\)](#page-24-5).

#### Computaci´on Serverless y Servicios de C´omputo en AWS

La computaci´on serverless es un paradigma donde el proveedor gestiona din´amicamente la asignaci´on de recursos, abstrayendo la infraestructura subyacente [Wen](#page-25-4) [et al.](#page-25-4) [\(2022\)](#page-25-4). El modelo FaaS, materializado en AWS Lambda, permite desplegar funciones que se ejecutan en respuesta a eventos con pago por tiempo de ejecuci´on [Wen et al.](#page-25-5) [\(2023\)](#page-25-5). Sin embargo, introduce desaf´ıos propios: el cold start, la gesti´on de conexiones a bases de datos bajo alta concurrencia, y la ausencia de estado persistente entre invocaciones [Eismann et al.](#page-24-6) [\(2024\)](#page-24-6).

No todo componente de un monolito es candidato a Lambda. AWS provee un espectro de servicios: Lambda para funciones orientadas a eventos de corta duraci´on, AWS Fargate para contenedores con mayor tolerancia a tiempos de ejecuci´on largos, y AWS App Runner para servicios HTTP con tr´afico continuo [Amazon Web Services](#page-24-7) [\(2025b\)](#page-24-7). La elecci´on del servicio objetivo depende de criterios como duraci´on, patr´on de invocaci´on, estado requerido y tolerancia al cold start.

#### Patrones Arquitect´onicos: Strangler Fig y Arquitectura Hexagonal

El patr´on Strangler Fig [Fowler](#page-24-8) [\(2024\)](#page-24-8) propone migrar un monolito de forma incremental creando nuevos componentes a su alrededor y redirigiendo el tr´afico mediante una capa de intercepci´on como Amazon API Gateway, hasta que el monolito puede retirarse. Este patr´on mitiga el riesgo de una reescritura completa y permite la coexistencia del monolito y los nuevos servicios durante la transici´on.

Para el c´odigo dentro de cada funci´on Lambda o contenedor Fargate, la arquitectura hexagonal (ports and adapters) ha emergido como el patr´on recomendado por AWS [Amazon Web Services](#page-24-9) [\(2021\)](#page-24-9). Esta arquitectura a´ısla la l´ogica de negocio del handler de invocaci´on y de los adaptadores de infraestructura (base de datos, S3, SES), haciendo el c´odigo portable entre Lambda y Fargate y facilitando las pruebas unitarias sin dependencias de infraestructura. La elecci´on del patr´on arquitect´onico dentro de cada componente depende de su complejidad: una arquitectura de capas simple puede ser suficiente para endpoints CRUD, mientras que componentes con l´ogica compleja o m´ultiples dependencias externas se benefician de la separaci´on

expl´ıcita de puertos y adaptadores.

#### An´alisis Est´atico de C´odigo Fuente

El an´alisis est´atico mediante Arboles de Sintaxis Abstracta (AST) permite ins- ´ peccionar la estructura de un programa sin ejecutarlo, identificando patrones de c´odigo, dependencias entre m´odulos y puntos de entrada [Abgaz et al.](#page-24-10) [\(2023\)](#page-24-10). En el contexto de la migraci´on de monolitos, el an´alisis AST es la t´ecnica fundamental para descubrir endpoints HTTP candidatos a migraci´on, detectar acoplamiento entre m´odulos e identificar anti-patrones bloqueadores como el acceso a estado compartido en memoria o el uso de funciones SQL no portables entre motores de base de datos.

### <span id="page-13-0"></span>4.2. Antecedentes

Los trabajos previos se eval´uan seg´un cuatro criterios: (1) Nivel de automatizaci´on: grado de automatizaci´on sin intervenci´on experta; (2) Cobertura de capas: si aborda las capas de persistencia, autenticaci´on, observabilidad y operaci´on; (3) Integraci´on con AWS: si genera infraestructura nativa de AWS; (4) Desplegabilidad: si el output es directamente desplegable.

#### Revisi´on Sistem´atica sobre Descomposici´on de Monolitos

[Abgaz et al.](#page-24-10) [\(2023\)](#page-24-10) examinaron 35 estudios sobre descomposici´on de aplicaciones monol´ıticas publicados en IEEE Transactions on Software Engineering, concluyendo que el campo est´a en una etapa temprana de madurez y que no existen m´etodos que combinen an´alisis est´atico, din´amico y evolutivo de forma integrada. Ventajas: es la revisi´on m´as rigurosa del estado del arte con respaldo en una revista de primer nivel. Desventajas: no aborda la migraci´on espec´ıfica a arquitecturas serverless FaaS, ni la generaci´on de IaC, ni la integraci´on en un IDE ag´entico.

#### FaaSificaci´on Acad´emica: M2FaaS

[Pedratscher et al.](#page-25-6) [\(2022\)](#page-25-6) presentaron M2FaaS, una herramienta que convierte autom´aticamente bloques de c´odigo de un monolito Node.js en funciones serverless en m´ultiples proveedores FaaS, reportando reducciones del esfuerzo de hasta el 73.3 %. Ventajas: alta automatizaci´on a nivel de c´odigo fuente. Desventajas: se limita estrictamente a la capa de aplicaci´on; no genera infraestructura perimetral (VPC, IAM, API Gateway), no resuelve la capa de persistencia ni la integraci´on CI/CD, y el output no es desplegable directamente en AWS.

#### Generaci´on de IaC con LLMs: IaCGen

[Pan et al.](#page-25-0) [\(2026\)](#page-25-0) desarrollaron IaCGen, un marco basado en LLMs para generar plantillas de infraestructura en AWS, revelando que los modelos de lenguaje alcanzan entre el 20.8 % y el 30.2 % de ´exito en el primer intento de despliegue, identificando la falta de contexto del entorno como la barrera principal. Ventajas: evidencia emp´ırica cuantitativa de las limitaciones de la IA en la generaci´on de infraestructura. Desventajas: IaC de prop´osito general sin el contexto espec´ıfico de migraci´on de monolitos ni integraci´on con un IDE ag´entico.

#### IDEs Ag´enticos: Limitaciones Emp´ıricas

[Horikawa et al.](#page-25-3) [\(2025\)](#page-25-3) estudiaron 15.451 refactorizaciones generadas por agentes (Claude Code, Cursor, Codex) en proyectos de c´odigo abierto, encontrando que los agentes predominantemente realizan ediciones de bajo nivel en lugar de cambios de dise˜no de alto nivel. Ventajas: establece evidencia de lo que los agentes hacen bien (c´odigo repetitivo) versus lo que no hacen (decisiones arquitect´onicas complejas). Desventajas: se centra en refactorizaci´on gen´erica, no en migraci´on a serverless ni en el uso de Skills para guiar al agente.

[Chatlatanagulchai et al.](#page-24-3) [\(2025\)](#page-24-3) encontraron que solo el 14.5 % de los archivos de contexto para agentes especifica restricciones de seguridad y solo el 14.5 % de rendimiento, validando que los archivos de contexto gen´ericos son insuficientes para tareas de alta complejidad como la migraci´on serverless. Ventajas: evidencia emp´ırica directa de la necesidad de Skills especializados. Desventajas: describe el problema sin proponer artefactos concretos para resolverlo.

#### Identificaci´on de la Brecha

La Tabla [1](#page-15-0) resume la comparaci´on de las propuestas revisadas frente a los criterios definidos.

<span id="page-15-0"></span>Tabla 1: Comparaci´on de propuestas existentes frente a las necesidades de la migraci´on serverless en AWS

| Propuesta           | Automatiz.  | Cobertura      | Integr. | Desplegable |
|---------------------|-------------|----------------|---------|-------------|
|                     |             | capas          | AWS     |             |
| Abgaz<br>et<br>al.  | Nula        | Solo an´alisis | No      | No          |
| (2023)              |             |                |         |             |
| M2FaaS (2022)       | Alta (c´odi | Solo<br>aplica | Parcial | No          |
|                     | go)         | ci´on          |         |             |
| IaCGen (2025)       | Media       | Solo IaC       | S´ı     | 20–30 %     |
| Kiro sin Skills     | Alta (c´odi | 3 de 4 capas   | Parcial | 62 %        |
|                     | go)         |                |         |             |
| Kiro<br>+<br>Skills | Alta        | 4 de 4 capas   | Nativa  | >85 %*      |
| (propuesto)         |             |                |         |             |

<sup>\*</sup>Valor esperado al finalizar la investigaci´on.

Las propuestas revisadas no resuelven la pregunta de investigaci´on porque est´an polarizadas: los trabajos de descomposici´on y FaaSificaci´on operan exclusivamente a nivel de c´odigo sin abordar la infraestructura de AWS; la generaci´on de IaC con LLMs produce plantillas con baja tasa de despliegue exitoso; y Kiro sin Skills logra un 62 % de cobertura pero deja brechas sistem´aticas en las cuatro capas cr´ıticas identificadas. Ninguna propuesta existente combina el an´alisis del monolito, la generaci´on de IaC nativa de AWS, la cobertura de las cuatro capas cr´ıticas y la integraci´on en un IDE ag´entico en producci´on. Esta desconexi´on es el punto de partida exacto para el desarrollo de los Agent Skills propuestos.

# <span id="page-16-0"></span>5. Riesgos Eticos ´

El desarrollo de Agent Skills para Kiro IDE orientados a la migraci´on de aplicaciones monol´ıticas implica riesgos ´eticos que, aunque el proyecto opera en un entorno acad´emico controlado, deben identificarse y mitigarse desde el dise˜no.

Protecci´on de informaci´on sensible. Los Skills propuestos analizan c´odigo fuente mediante AST para detectar endpoints, modelos de datos y dependencias. En fases futuras de aplicaci´on pr´actica, este an´alisis podr´ıa ejecutarse sobre c´odigo propietario de organizaciones reales que contenga l´ogica de negocio confidencial o datos sensibles. Como mitigaci´on, los Skills se dise˜nar´an bajo el principio de privacy by design: el an´alisis est´atico operar´a exclusivamente en memoria local sin transmitir c´odigo fuente a servicios externos. El proyecto de investigaci´on se evaluar´a ´unicamente sobre el monolito de referencia construido para este fin, que no contiene informaci´on empresarial real.

Sesgo de cobertura tecnol´ogica. Los Skills propuestos operan exclusivamente sobre monolitos en Python con Flask y SQLAlchemy. Esto introduce un sesgo de exclusi´on hacia organizaciones cuyas aplicaciones est´en construidas en otros lenguajes o frameworks (Django, FastAPI, Node.js/Express, Java Spring, entre otros), lo que podr´ıa limitar el acceso al beneficio de la herramienta a un subconjunto de equipos de desarrollo. Como mitigaci´on, la documentaci´on de los Skills especificar´a expl´ıcitamente las restricciones de compatibilidad para evitar expectativas incorrectas, y el dise˜no modular de los archivos SKILL.md facilitar´a su extensi´on futura a otros frameworks por parte de la comunidad.

Dependencia tecnol´ogica y riesgo de vendor lock-in. Los Skills generan infraestructura exclusivamente para Amazon Web Services, lo que podr´ıa profundizar la dependencia tecnol´ogica de las organizaciones que los adopten respecto a un ´unico proveedor de nube. Como mitigaci´on, el dise˜no de los Skills priorizar´a el uso de plantillas AWS SAM con par´ametros configurables y est´andares abiertos, y la documentaci´on incluir´a advertencias expl´ıcitas sobre las implicaciones arquitect´onicas de la adopci´on de servicios propietarios.

Implicaciones no previstas en entornos productivos. Los Skills generan

Infraestructura como C´odigo y recomendaciones arquitect´onicas que una organizaci´on podr´ıa adoptar en producci´on sin la supervisi´on de un arquitecto cloud. Una configuraci´on incorrecta podr´ıa derivar en vulnerabilidades de seguridad (roles IAM sobredimensionados, buckets S3 p´ublicos, endpoints sin autenticaci´on) o en costos operativos no anticipados. Como mitigaci´on, los Skills incluir´an advertencias expl´ıcitas en su output indicando que el c´odigo generado debe ser revisado por un profesional antes de aplicarse en entornos productivos, y las plantillas IaC seguir´an por defecto las recomendaciones del AWS Well-Architected Framework con el principio de m´ınimo privilegio.

# <span id="page-17-0"></span>6. Metodolog´ıa del Proyecto

### <span id="page-17-1"></span>6.1. Justificaci´on de la Elecci´on Metodol´ogica

Este proyecto adopta la Investigaci´on en Ciencia de Dise˜no (Design Science Research — DSR) propuesta por [Peffers et al.](#page-25-7) [\(2007\)](#page-25-7) como marco metodol´ogico. La pertinencia de DSR se fundamenta en la naturaleza del problema: no se busca describir un fen´omeno existente, sino resolver un problema pr´actico y verificable (las brechas de automatizaci´on de Kiro en la migraci´on serverless) mediante la creaci´on de un artefacto tecnol´ogico novedoso (Agent Skills especializados). DSR proporciona un marco validado acad´emicamente que garantiza rigor t´ecnico y aplicabilidad real, siendo el paradigma de referencia para investigaciones de ingenier´ıa de software orientadas a la construcci´on de artefactos [Hevner et al.](#page-25-8) [\(2004\)](#page-25-8).

### <span id="page-17-2"></span>6.2. Justificaci´on de la Estrategia General

DSR [Peffers et al.](#page-25-7) [\(2007\)](#page-25-7) proporciona un marco validado acad´emicamente para garantizar que el artefacto construido posea rigor t´ecnico y aplicabilidad real. Su pertinencia se justifica en tres aspectos: (1) el problema es pr´actico y verificable (las brechas de automatizaci´on de Kiro son medibles); (2) la soluci´on es un artefacto t´ecnico novedoso (Agent Skills especializados para migraci´on serverless en AWS, que no existen actualmente); y (3) la evaluaci´on es emp´ırica y cuantitativa (comparaci´on antes/despu´es sobre el mismo monolito de referencia). Para la ejecuci´on t´ecnica de los Skills, se combina DSR con un enfoque de desarrollo iterativo e incremental, justificado por la restricci´on de 192 horas y la participaci´on de un ´unico desarrollador.

### <span id="page-18-0"></span>6.3. Enfoque, T´ecnicas y Herramientas

El problema se aborda desde tres perspectivas t´ecnicas complementarias. El an´alisis est´atico de c´odigo mediante AST (Abstract Syntax Trees) se aplica para caracterizar el monolito de referencia e identificar los patrones de c´odigo que los Skills deben detectar. La ingenier´ıa de prompts y dise˜no de instrucciones para agentes se aplica en la construcci´on de los archivos SKILL.md, definiendo instrucciones, criterios de decisi´on y plantillas de referencia que gu´ıan al agente de Kiro. La evaluaci´on experimental controlada se aplica para medir cuantitativamente el impacto de los Skills sobre la cobertura de migraci´on de Kiro.

Las herramientas principales son: Kiro IDE (plataforma de despliegue de los Skills), Python (scripts de an´alisis est´atico incluidos en los Skills), AWS SAM (formato de IaC generado por los Skills), y AWS (entorno de validaci´on de desplegabilidad del output).

### <span id="page-18-1"></span>6.4. Fases del Trabajo y Relaci´on con los Objetivos

Fase 1 — Caracterizaci´on de brechas (OE1): Se formaliza y documenta el experimento emp´ırico preliminar realizado con Claude y Kiro sobre el monolito de referencia, estableciendo el baseline cuantitativo: cobertura funcional por capa, esfuerzo residual (d´ıas-persona para cerrar gaps) y tasa de desplegabilidad. El monolito de referencia se construye como insumo controlado con las caracter´ısticas definidas en el alcance (Flask 2.x+, m´ınimo 5 m´odulos, 20 endpoints, 4 tablas). Esta fase produce la Matriz de Brechas: un cat´alogo de gaps clasificados por capa arquitect´onica, causa ra´ız y severidad, que sirve como especificaci´on de requerimientos para los Skills.

Fase 2 — Dise˜no de los Skills (OE2): A partir de la Matriz de Brechas, se dise˜na la arquitectura de cada Skill: definici´on de su alcance, instrucciones de dominio en SKILL.md, scripts de an´alisis en Python, plantillas IaC de referencia, y criterios de decisi´on arquitect´onica (Lambda vs. Fargate vs. App Runner; patr´on de dise˜no interno seg´un complejidad del endpoint). Esta fase produce las especificaciones funcionales de los cinco Skills propuestos.

Fase 3 — Construcci´on iterativa de los Skills (OE3): Se desarrollan los Skills en iteraciones cortas alineadas con el orden de migraci´on sugerido en el manifiesto (de menor a mayor complejidad): (a) Skill de an´alisis y manifiesto; (b) Skill de persistencia; (c) Skill de coexistencia Strangler Fig; (d) Skill de uploads; (e) Skill de validaci´on post-generaci´on. Cada iteraci´on incluye una sesi´on de prueba sobre el monolito de referencia con Kiro para verificar que el Skill se activa correctamente y mejora el output.

Fase 4 — Evaluaci´on (OE4): Se ejecuta el experimento de evaluaci´on comparativa: Kiro sin Skills (baseline medido en Fase 1) versus Kiro con los cinco Skills instalados, sobre el mismo monolito de referencia. Se recolectan las m´etricas definidas en la secci´on de recopilaci´on de datos. Esta fase produce el Informe de Evaluaci´on con los resultados cuantitativos.

### <span id="page-19-0"></span>6.5. Recopilaci´on y An´alisis de Datos

La recopilaci´on de datos es de car´acter cuantitativo y comparativo. Las m´etricas se recolectan en los dos escenarios del experimento (sin Skills y con Skills) sobre el mismo monolito de referencia, garantizando comparabilidad. Las tres m´etricas principales son:

- 1. Cobertura funcional ( %): Proporci´on de endpoints del monolito para los cuales Kiro genera una funci´on Lambda o contenedor Fargate con c´odigo funcional (handler completo, validaci´on de input, acceso a BD, respuesta HTTP). Se mide contando los endpoints con c´odigo funcional sobre el total de endpoints del monolito.
- 2. Esfuerzo residual (d´ıas-persona): Tiempo estimado necesario para que un desarrollador con perfil generalista complete manualmente los gaps que Kiro

no resolvi´o autom´aticamente, seg´un la clasificaci´on de causa ra´ız de la Fase 1. Este valor se estima mediante la r´ubrica de evaluaci´on construida en la Fase 1, que asigna un esfuerzo est´andar por tipo de gap.

3. Tasa de desplegabilidad ( %): Proporci´on de recursos de infraestructura del template SAM generado que se despliegan exitosamente en AWS en el primer intento, sin modificaci´on manual. Se mide ejecutando sam deploy sobre el output de Kiro y registrando el resultado (´exito/fallo) por recurso.

Los datos se tabular´an comparando los valores de cada m´etrica en el escenario sin Skills (baseline) versus con Skills, y se calcular´a la mejora relativa para cada una. El an´alisis determinar´a si los Skills alcanzan el umbral de efectividad esperado: cobertura funcional superior al 85 %, reducci´on del esfuerzo residual en al menos un 60 % respecto al baseline, y tasa de desplegabilidad superior al 80 %.

# <span id="page-20-0"></span>7. Cronograma

El proyecto se ejecutar´a en cinco meses con una dedicaci´on de 192 horas de esfuerzo total (aproximadamente 9–10 horas semanales). La metodolog´ıa DSR combinada con un enfoque iterativo e incremental organiza el trabajo en cuatro fases, cada una alineada con un objetivo espec´ıfico y con entregables concretos que sirven como puntos de control con el director.

### <span id="page-21-0"></span>Distribuci´on del Esfuerzo por Fase

Tabla 2: Distribuci´on de horas por fase del proyecto

| Fase                                 | %     | Horas | Objetivo espec´ıfico |
|--------------------------------------|-------|-------|----------------------|
| Fase 1: Caracterizaci´on de          | 16 %  | 30 h  | OE1                  |
| brechas                              |       |       |                      |
| Fase<br>2–3:<br>Dise˜no<br>y<br>cons | 47 %  | 90 h  | OE2 y OE3            |
| trucci´on de Skills                  |       |       |                      |
| Fase 4: Evaluaci´on                  | 13 %  | 25 h  | OE4                  |
| Documentaci´on, reuniones            | 14 %  | 28 h  | Transversal          |
| y defensa                            |       |       |                      |
| Holgura / buffer de impre            | 10 %  | 19 h  | —                    |
| vistos                               |       |       |                      |
| Total                                | 100 % | 192 h |                      |

# Desglose Mensual y Entregables

Tabla 3: Cronograma general de ejecución del proyecto (5 meses)

<span id="page-22-0"></span>

| Mes                       | Actividades clave                                                                                                                                                                                                                                          | Horas | Entregable / Hito                                               |
|---------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------|-----------------------------------------------------------------|
| Mes<br>1<br>(S1–<br>S4)   | Formalización del experimento empírico (Gap Analysis). Construcción del monolito de referencia (Flask, 5 módulos, 20+ endpoints). Elaboración de la Matriz de Brechas. Reunión de control con el director.                                                 | 30 h  | OE1: Matriz de Brechas documentada y validada.                  |
| Mes 2 (S5–S8)             | Diseño de los cinco Skills (SKILL.md, criterios Lambda vs. Fargate vs. App Runner, patrones arquitectónicos).  Construcción del Skill 1: analizador de monolito.  Construcción del Skill 2: migrador de persistencia.  Reunión de control con el director. | 38 h  | OE2 y OE3 (parcial): Skills 1 y 2 instalables en Kiro.          |
| Mes<br>3<br>(S9–<br>S12)  | Construcción del Skill 3: orquestador Strangler Fig. Construcción del Skill 4: migrador de uploads. Construcción del Skill 5: validador post-generación. Reunión de control con el director.                                                               | 42 h  | OE3 (completo): Cinco Skills funcionales e instalables en Kiro. |
| Mes<br>4<br>(S13-<br>S16) | Configuración del entorno de evaluación en AWS.  Experimento comparativo: Kiro 23 sin Skills (baseline) vs. Kiro con Skills.  Recolección y análisis de métricas.  Reunión de control con el director.                                                     | 35 h  | OE4: Informe de evaluación con métricas comparativas.           |
| Mes                       | Consolidación del documento de                                                                                                                                                                                                                             | 47 h  | Cierre: Documento fina                                          |

### Mecanismos de Control y Monitoreo

Para asegurar el cumplimiento del cronograma se implementar´an los siguientes controles:

- 1. Control semanal: Tablero Kanban personal (GitHub Projects o Trello) con desglose de tareas a nivel de c´odigo (´epicas, historias de usuario, bugs de los Skills). Registro del tiempo real invertido versus el planificado.
- 2. Control mensual: Sesiones de sincronizaci´on con el director del proyecto al cierre de cada mes para contrastar el avance real frente al planificado en la Tabla [3,](#page-22-0) revisar los entregables del mes, aplicar retroalimentaci´on arquitect´onica y aprobar el inicio de la siguiente fase. La bolsa de holgura (19 horas) se administrar´a estrictamente para absorber desviaciones detectadas en estos puntos de control.

# Referencias

- <span id="page-24-10"></span>Abgaz, Y., McCarren, A., Elger, P., Solan, D., Lapuz, N., Bivol, M., Jackson, G., Yilmaz, M., Buckley, J., and Clarke, P. (2023). Decomposition of monolith applications into microservices architectures: A systematic review. IEEE Transactions on Software Engineering, 49(8):4213–4242.
- <span id="page-24-9"></span>Amazon Web Services (2021). Developing evolutionary architecture with AWS Lambda. AWS Compute Blog. Accedido en abril 2026.
- <span id="page-24-1"></span>Amazon Web Services (2025a). Agent skills: Extend kiro with portable instruction packages. Accedido en abril 2026.
- <span id="page-24-7"></span>Amazon Web Services (2025b). Cloud Design Patterns: Strangler Fig Pattern.
- <span id="page-24-0"></span>Amazon Web Services (2025c). Introducing kiro: An agentic IDE for prototype to production. Accedido en abril 2026.
- <span id="page-24-5"></span>Amazon Web Services (2025d). Kiro powers: Specialized context and tools for kiro agents. Accedido en abril 2026.
- <span id="page-24-4"></span>Anthropic (2025). Agent skills: Open standard for IDE agent instructions. Est´andar abierto adoptado por Kiro, Claude Code, Cursor y VS Code.
- <span id="page-24-3"></span>Chatlatanagulchai, W., Li, H., Kashiwa, Y., Reid, B., Thonglek, K., Leelaprute, P., Rungsawang, A., Manaskasemsak, B., Adams, B., Hassan, A. E., and Iida, H. (2025). Agent READMEs: An empirical study of context files for agentic coding. arXiv preprint arXiv:2511.12884.
- <span id="page-24-6"></span>Eismann, S. et al. (2024). Cold start latency in serverless computing: A systematic review, taxonomy, and future directions. ACM Computing Surveys.
- <span id="page-24-2"></span>Fedesoft (2025). Industria del software en colombia tiene ventas que superan los 44 billones. Cifras sobre el ecosistema de micro y peque˜nas empresas.
- <span id="page-24-8"></span>Fowler, M. (2024). Strangler fig application. Accedido en 2026.

- <span id="page-25-8"></span>Hevner, A. R., March, S. T., Park, J., and Ram, S. (2004). Design science in information systems research. MIS Quarterly, 28(1):75–105.
- <span id="page-25-3"></span>Horikawa, K., Li, H., Kashiwa, Y., Adams, B., Iida, H., and Hassan, A. E. (2025). Agentic refactoring: An empirical study of AI coding agents. arXiv preprint ar-Xiv:2511.04824.
- <span id="page-25-2"></span>MinTIC (2024). Informe de gesti´on: Cierre de la brecha digital en colombia.
- <span id="page-25-0"></span>Pan, S., Zhang, T., Zhang, Z., Xing, Z., and Sun, X. (2026). Deployabilitycentric infrastructure-as-code generation: Fail, learn, refine, and succeed through LLM-empowered DevOps simulation. In Proceedings of the ACM International Conference on the Foundations of Software Engineering (FSE). Preprint ar-Xiv:2506.05623.
- <span id="page-25-6"></span>Pedratscher, S., Ristov, S., and Fahringer, T. (2022). M2FaaS: Transparent and fault tolerant FaaSification of Node.js monolith code blocks. Future Generation Computer Systems, 135:57–71.
- <span id="page-25-7"></span>Peffers, K., Tuunanen, T., Rothenberger, M. A., and Chatterjee, S. (2007). A design science research methodology for information systems research. Journal of Management Information Systems, 24(3):45–77.
- <span id="page-25-1"></span>Timmer, R. (2024). Cost-effective machine learning inference with AWS Lambda: Evaluating serverless resource configurations. Master's thesis, University of Groningen.
- <span id="page-25-5"></span>Wen, J., Chen, Z., Jin, X., and Liu, X. (2023). Rise of the planet of serverless computing: A systematic review. ACM Transactions on Software Engineering and Methodology, 32(5).
- <span id="page-25-4"></span>Wen, J., Chen, Z., and Liu, X. (2022). Software engineering for serverless computing. arXiv preprint arXiv:2207.13263.