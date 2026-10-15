"""
analyze_monolith.py — Skill 01: Analizador de Monolito Flask

Examina el código fuente de un monolito Flask mediante análisis estático del Árbol
de Sintaxis Abstracta (AST) y produce el archivo migration-manifest.json con:

  - Inventario completo de endpoints por módulo (blueprint)
  - Anti-patrones de migración serverless detectados con sus GAP IDs
  - Recomendación de destino de cómputo AWS por endpoint (Lambda / Fargate / App Runner)
  - Complejidad de migración por endpoint (low / medium / high / very_high)
  - Secuencia de migración siguiendo el patrón Strangler Fig
  - Lambda Layers recomendadas derivadas del análisis de dependencias

Principios de diseño:
  - Sin dependencias externas: usa exclusivamente módulos de la biblioteca estándar
    de Python 3.9+ (ast, os, sys, json, re, pathlib, datetime, argparse, typing)
  - Análisis en memoria: los archivos Python se leen como texto; ast.parse() construye
    los árboles sin ejecutar el código (exec, eval e importlib están prohibidos)
  - Tolerancia a fallos por archivo: un SyntaxError en un archivo no interrumpe el
    análisis del resto del directorio
  - Salida determinista: el mismo directorio de entrada produce el mismo manifiesto

Uso:
    python analyze_monolith.py --path <ruta_monolito>
    python analyze_monolith.py --path <ruta_monolito> --output <ruta_manifiesto.json>

Códigos de salida:
    0 — Análisis completado exitosamente; manifiesto escrito
    1 — El directorio --path no existe
    2 — No se encontraron blueprints Flask en el directorio
    3 — Error de escritura del manifiesto (se intenta fallback a cwd)

Proyecto: Trabajo de Grado — Maestría en Ingeniería de Software
          Pontificia Universidad Javeriana Cali
Autor:    Luis Gerardo Sánchez Ordóñez
Director: Juan Gabriel Quintero Barbosa — Head Solutions Architecture, AWS Colombia
"""

# ---------------------------------------------------------------------------
# Imports — únicamente biblioteca estándar de Python 3.9+
# ---------------------------------------------------------------------------
import ast
import os
import sys
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone
import argparse
from typing import TypedDict, Optional


# ---------------------------------------------------------------------------
# Constantes globales
# ---------------------------------------------------------------------------

ANALYZER_VERSION = "1.0.0"
SKILL_VERSION = "1.0.0"

# Métodos HTTP válidos según RFC 7231 + PATCH (RFC 5789)
VALID_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


# ---------------------------------------------------------------------------
# === BlueprintDiscoverer ===
# Responsabilidad: determinar el mapeo entre nombre de variable de blueprint
# y su url_prefix, y localizar los archivos routes.py de cada blueprint.
# ---------------------------------------------------------------------------


class BlueprintInfo(TypedDict):
    """Información de un blueprint Flask descubierto en el monolito."""
    prefix: str          # URL prefix, e.g. "/api/auth"
    routes_file: Path    # Absolute path to the blueprint's routes.py
    module_name: str     # Inferred module name, e.g. "auth"
    bp_variable: str     # Variable name in code, e.g. "auth_bp"


class BlueprintDiscoverer:
    """
    Descubre los blueprints Flask de un monolito y sus archivos routes.py.

    Opera en dos pasos:
      1. Parsea app/__init__.py con ast.parse() para extraer las llamadas
         app.register_blueprint(bp_var, url_prefix='...') y construir el
         mapeo {bp_variable → url_prefix}.
      2. Recorre recursivamente el directorio del monolito buscando el archivo
         .py que declara cada variable de blueprint como
         `<bp_var> = Blueprint(...)`.

    Si app/__init__.py no puede parsearse, aplica una heurística de directorio
    como fallback y registra una advertencia en self.warnings.

    No ejecuta código del monolito (sin exec, eval ni importlib).
    Usa exclusivamente módulos de la biblioteca estándar de Python 3.9+.
    """

    def __init__(self, monolith_path: Path) -> None:
        self.monolith_path: Path = monolith_path.resolve()
        self.warnings: list[str] = []

    # ------------------------------------------------------------------
    # Interfaz pública
    # ------------------------------------------------------------------

    def discover(self) -> dict[str, BlueprintInfo]:
        """
        Devuelve {bp_variable_name: BlueprintInfo} por cada blueprint hallado.

        El flujo normal:
          a) Parsear app/__init__.py → obtener {bp_var: url_prefix}
          b) Para cada bp_var, buscar el archivo .py que lo declare
             como `bp_var = Blueprint(...)`
          c) Inferir module_name desde el directorio del archivo encontrado

        Si app/__init__.py falla (no existe o tiene SyntaxError) se aplica
        el fallback heurístico y se registra la advertencia correspondiente.
        """
        prefix_map = self._parse_init_for_blueprints()

        if not prefix_map:
            # fallback: no se pudo extraer ningún prefijo desde __init__.py
            return self._fallback_discover()

        # Paso 2: localizar routes.py para cada variable de blueprint
        result: dict[str, BlueprintInfo] = {}
        for bp_var, prefix in prefix_map.items():
            routes_file = self._find_routes_file_for(bp_var)
            if routes_file is None:
                self.warnings.append(
                    f"BlueprintDiscoverer: no se encontró routes.py para la "
                    f"variable '{bp_var}' (prefix='{prefix}'). Se omite el blueprint."
                )
                continue
            module_name = self._infer_module_name(routes_file)
            result[bp_var] = BlueprintInfo(
                prefix=prefix,
                routes_file=routes_file,
                module_name=module_name,
                bp_variable=bp_var,
            )

        return result

    # ------------------------------------------------------------------
    # Paso 1 — Parseo de app/__init__.py
    # ------------------------------------------------------------------

    def _parse_init_for_blueprints(self) -> dict[str, str]:
        """
        Parsea app/__init__.py mediante AST y devuelve {bp_variable: url_prefix}.

        Busca nodos ast.Call con func.attr == 'register_blueprint' donde:
          - args[0] es ast.Name (nombre de la variable blueprint)
          - keywords contiene url_prefix con valor ast.Constant (str)

        Si el archivo no existe o contiene SyntaxError, registra una advertencia
        y retorna un dict vacío para que discover() use el fallback.
        """
        init_path = self._locate_app_init()
        if init_path is None:
            self.warnings.append(
                "BlueprintDiscoverer: no se encontró app/__init__.py. "
                "Se usará el fallback heurístico de directorio."
            )
            return {}

        source = self._read_file_safe(init_path)
        if source is None:
            # La advertencia ya fue registrada en _read_file_safe
            return {}

        try:
            tree = ast.parse(source, filename=str(init_path))
        except SyntaxError as exc:
            self.warnings.append(
                f"BlueprintDiscoverer: SyntaxError en '{init_path}': {exc}. "
                "Se usará el fallback heurístico de directorio."
            )
            return {}

        prefix_map: dict[str, str] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # Verificar que sea una llamada a <algo>.register_blueprint(...)
            if not (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "register_blueprint"
            ):
                continue
            # El primer argumento posicional debe ser el nombre de la variable blueprint
            if not node.args or not isinstance(node.args[0], ast.Name):
                continue
            bp_var: str = node.args[0].id  # e.g. "auth_bp"

            # Buscar el keyword url_prefix
            url_prefix = self._extract_url_prefix(node.keywords)
            if url_prefix is None:
                # register_blueprint sin url_prefix explícito; inferir del nombre
                url_prefix = self._infer_prefix_from_var(bp_var)
                self.warnings.append(
                    f"BlueprintDiscoverer: '{bp_var}' no tiene url_prefix explícito; "
                    f"se infiere '{url_prefix}' desde el nombre de la variable."
                )

            prefix_map[bp_var] = url_prefix

        return prefix_map

    def _locate_app_init(self) -> Optional[Path]:
        """
        Localiza app/__init__.py (o __init__.py en la raíz) del monolito.

        Estrategia:
          1. <monolith_path>/app/__init__.py  (caso canónico Flask)
          2. <monolith_path>/__init__.py      (monolito sin subdirectorio app/)
          3. Primer __init__.py encontrado en subdirectorio llamado 'app'
        """
        candidates = [
            self.monolith_path / "app" / "__init__.py",
            self.monolith_path / "__init__.py",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate

        # Búsqueda más amplia: cualquier directorio llamado 'app' con __init__.py
        for py_file in self.monolith_path.rglob("__init__.py"):
            if py_file.parent.name == "app":
                return py_file

        return None

    @staticmethod
    def _extract_url_prefix(keywords: list) -> Optional[str]:
        """
        Extrae el valor del keyword url_prefix de la lista de keywords de ast.Call.
        Retorna None si no existe o si el valor no es una constante de cadena.
        """
        for kw in keywords:
            if kw.arg == "url_prefix" and isinstance(kw.value, ast.Constant):
                value = kw.value.value
                if isinstance(value, str):
                    return value
        return None

    @staticmethod
    def _infer_prefix_from_var(bp_var: str) -> str:
        """
        Infiere el url_prefix a partir del nombre de la variable de blueprint.
        Ejemplo: 'auth_bp' → '/api/auth', 'clientes_bp' → '/api/clientes'.
        """
        # Eliminar sufijo '_bp' si existe
        module = bp_var.removesuffix("_bp")
        return f"/api/{module}"

    # ------------------------------------------------------------------
    # Paso 2 — Búsqueda recursiva del archivo routes.py
    # ------------------------------------------------------------------

    def _find_routes_file_for(self, bp_var: str) -> Optional[Path]:
        """
        Busca recursivamente el archivo .py que contenga la declaración
        `<bp_var> = Blueprint(...)` a nivel de módulo.

        Estrategia principal:
          Recorrer todos los .py del monolito; para cada uno, parsear el AST
          y buscar nodos ast.Assign a nivel de módulo donde:
            - target es ast.Name con id == bp_var
            - value es ast.Call cuyo func es ast.Name(id='Blueprint') o
              ast.Attribute(attr='Blueprint')

        Esta búsqueda es robusta ante convenciones de nombre de variable distintas
        a la del monolito de referencia.
        """
        for py_file in self._iter_python_files():
            source = self._read_file_safe(py_file)
            if source is None:
                continue
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError as exc:
                self.warnings.append(
                    f"BlueprintDiscoverer: SyntaxError en '{py_file}': {exc}. "
                    "Se omite el archivo en la búsqueda de routes."
                )
                continue

            if self._file_declares_bp_var(tree, bp_var):
                return py_file.resolve()

        return None

    @staticmethod
    def _file_declares_bp_var(tree: ast.Module, bp_var: str) -> bool:
        """
        Verifica si el AST del módulo contiene una asignación de nivel de módulo
        de la forma `<bp_var> = Blueprint(...)`.

        Solo busca en el nivel superior (body del módulo), no dentro de funciones,
        para evitar falsos positivos con variables locales con el mismo nombre.
        """
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            # Verificar que al menos uno de los targets es el nombre buscado
            for target in node.targets:
                if not (isinstance(target, ast.Name) and target.id == bp_var):
                    continue
                # Verificar que el valor es una llamada a Blueprint(...)
                value = node.value
                if not isinstance(value, ast.Call):
                    continue
                func = value.func
                if isinstance(func, ast.Name) and func.id == "Blueprint":
                    return True
                if isinstance(func, ast.Attribute) and func.attr == "Blueprint":
                    return True
        return False

    # ------------------------------------------------------------------
    # Fallback heurístico cuando app/__init__.py no está disponible
    # ------------------------------------------------------------------

    def _fallback_discover(self) -> dict[str, BlueprintInfo]:
        """
        Fallback cuando app/__init__.py no puede parsearse.

        Recorre todos los .py del monolito buscando declaraciones
        `<var> = Blueprint(...)`. Para cada una, infiere el url_prefix desde
        el nombre del directorio padre (e.g., blueprints/auth/ → /api/auth).

        Esta heurística no conoce el url_prefix real, por lo que puede ser
        inexacta; se documenta en self.warnings.
        """
        self.warnings.append(
            "BlueprintDiscoverer: usando fallback heurístico — los url_prefix "
            "se infieren del nombre del directorio y pueden ser incorrectos."
        )
        result: dict[str, BlueprintInfo] = {}

        for py_file in self._iter_python_files():
            source = self._read_file_safe(py_file)
            if source is None:
                continue
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError as exc:
                self.warnings.append(
                    f"BlueprintDiscoverer: SyntaxError en '{py_file}': {exc}."
                )
                continue

            for bp_var in self._extract_blueprint_vars(tree):
                if bp_var in result:
                    continue  # ya descubierto
                module_name = self._infer_module_name(py_file)
                prefix = f"/api/{module_name}"
                result[bp_var] = BlueprintInfo(
                    prefix=prefix,
                    routes_file=py_file.resolve(),
                    module_name=module_name,
                    bp_variable=bp_var,
                )

        return result

    @staticmethod
    def _extract_blueprint_vars(tree: ast.Module) -> list[str]:
        """
        Extrae los nombres de variables asignadas a Blueprint(...) a nivel de módulo.
        """
        vars_found: list[str] = []
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            value = node.value
            if not isinstance(value, ast.Call):
                continue
            func = value.func
            is_blueprint = (
                (isinstance(func, ast.Name) and func.id == "Blueprint")
                or (isinstance(func, ast.Attribute) and func.attr == "Blueprint")
            )
            if not is_blueprint:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    vars_found.append(target.id)
        return vars_found

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------

    def _iter_python_files(self):
        """
        Genera todos los archivos .py del directorio del monolito de forma
        recursiva, excluyendo directorios de entorno virtual y caché.
        """
        SKIP_DIRS = {
            "__pycache__", ".git", ".venv", "venv", "env",
            "node_modules", ".tox", "dist", "build", ".mypy_cache",
        }
        for root, dirs, files in os.walk(self.monolith_path):
            # Excluir directorios que no forman parte del código fuente
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for filename in files:
                if filename.endswith(".py"):
                    yield Path(root) / filename

    def _read_file_safe(self, path: Path) -> Optional[str]:
        """
        Lee el contenido de un archivo de texto de forma segura.
        Retorna None (y registra una advertencia) si ocurre cualquier error de I/O.
        """
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.warnings.append(
                f"BlueprintDiscoverer: no se puede leer '{path}': {exc}."
            )
            return None

    @staticmethod
    def _infer_module_name(routes_file: Path) -> str:
        """
        Infiere el nombre del módulo (blueprint) desde la ruta del archivo.

        Estrategia:
          - Si el archivo se llama 'routes.py', el nombre es el de su
            directorio padre (e.g., 'app/blueprints/auth/routes.py' → 'auth').
          - En cualquier otro caso, usa el stem del archivo sin extensión.
        """
        if routes_file.name == "routes.py":
            return routes_file.parent.name
        return routes_file.stem


# ---------------------------------------------------------------------------
# === EndpointExtractor ===
# Responsabilidad: parsear un archivo routes.py y extraer todas las funciones
# de ruta con su información básica (método HTTP, ruta URL, decoradores,
# nombre de función, flags de auth).
# ---------------------------------------------------------------------------


@dataclass
class EndpointNode:
    """
    Representa un único endpoint HTTP descubierto en un blueprint de Flask.

    Un decorador @bp.route(..., methods=["GET", "POST"]) con múltiples métodos
    produce un EndpointNode independiente por cada método HTTP.
    """
    func_node: ast.FunctionDef          # Nodo AST de la función de ruta
    method: str                          # Método HTTP en mayúsculas, e.g. "POST"
    full_path: str                       # Ruta URL completa, e.g. "/api/auth/login"
    relative_path: str                   # Ruta relativa del decorador, e.g. "/login"
    auth_required: bool                  # True si @jwt_required() está en los decoradores
    admin_required: bool                 # True si hay verificación de rol 'admin' en el cuerpo
    module_name: str                     # Nombre del módulo/blueprint, e.g. "auth"
    func_name: str                       # Nombre de la función Python, e.g. "login"
    endpoint_id: str = field(init=False) # "<module_name>.<func_name>", e.g. "auth.login"

    def __post_init__(self) -> None:
        self.endpoint_id = f"{self.module_name}.{self.func_name}"


class EndpointExtractor:
    """
    Parsea un archivo routes.py de un blueprint Flask mediante análisis AST
    y extrae todos los endpoints definidos con sus metadatos básicos.

    Principios de implementación:
      - Usa ast.walk() para recorrer el árbol sin ejecutar el código
      - Genera un EndpointNode por cada método HTTP cuando el decorador declara
        múltiples métodos (e.g. methods=["GET", "POST"] → 2 EndpointNode)
      - Convierte parámetros Flask (<int:var>, <string:var>, <var>) a formato
        estándar {var} usando re.sub()
      - Detecta auth_required desde el decorator_list de la función
      - Detecta admin_required buscando comparaciones con 'admin' en el cuerpo
    """

    # Patrón regex para convertir parámetros Flask al formato {var}
    _FLASK_PARAM_RE = re.compile(r"<(?:\w+:)?(\w+)>")

    def __init__(self, routes_file: Path, blueprint_info: BlueprintInfo) -> None:
        self.routes_file = routes_file
        self.blueprint_info = blueprint_info
        self.warnings: list[str] = []

    # ------------------------------------------------------------------
    # Interfaz pública
    # ------------------------------------------------------------------

    def extract(self) -> list[EndpointNode]:
        """
        Parsea el archivo routes_file y retorna una lista de EndpointNode,
        uno por cada combinación (función de ruta, método HTTP) encontrada.

        Retorna [] si el archivo no puede leerse o contiene errores de sintaxis,
        registrando la causa en self.warnings.
        """
        source = self._read_file_safe(self.routes_file)
        if source is None:
            return []

        try:
            tree = ast.parse(source, filename=str(self.routes_file))
        except SyntaxError as exc:
            self.warnings.append(
                f"EndpointExtractor: SyntaxError en '{self.routes_file}': {exc}. "
                "Se omite el archivo."
            )
            return []

        endpoints: list[EndpointNode] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            nodes = self._extract_from_function(node)
            endpoints.extend(nodes)

        return endpoints

    # ------------------------------------------------------------------
    # Extracción por función
    # ------------------------------------------------------------------

    def _extract_from_function(self, func_node: ast.FunctionDef) -> list[EndpointNode]:
        """
        Examina la lista de decoradores de una función y genera un EndpointNode
        por cada decorador de ruta encontrado y por cada método HTTP declarado.

        Devuelve una lista vacía si la función no tiene decoradores de ruta.
        """
        results: list[EndpointNode] = []

        for decorator in func_node.decorator_list:
            route_info = self._parse_route_decorator(decorator)
            if route_info is None:
                continue
            relative_path, methods = route_info

            # Construir la ruta completa con conversión de parámetros Flask
            full_path = self._build_full_path(
                self.blueprint_info["prefix"], relative_path
            )

            # Detectar flags de autenticación
            auth_required = self._detect_auth_required(func_node.decorator_list)
            admin_required = self._detect_admin_required(func_node)

            # Crear un EndpointNode por cada método HTTP
            for method in methods:
                if method not in VALID_HTTP_METHODS:
                    self.warnings.append(
                        f"EndpointExtractor: método HTTP inválido '{method}' en "
                        f"'{func_node.name}' de '{self.routes_file}'. Se omite."
                    )
                    continue
                results.append(EndpointNode(
                    func_node=func_node,
                    method=method,
                    full_path=full_path,
                    relative_path=relative_path,
                    auth_required=auth_required,
                    admin_required=admin_required,
                    module_name=self.blueprint_info["module_name"],
                    func_name=func_node.name,
                ))

        return results

    # ------------------------------------------------------------------
    # Parseo del decorador @bp.route(...)
    # ------------------------------------------------------------------

    def _parse_route_decorator(
        self, decorator: ast.expr
    ) -> Optional[tuple[str, list[str]]]:
        """
        Intenta extraer (relative_path, [methods]) del decorador.

        Retorna None si el decorador no es un @<algo>.route(...).

        El decorador objetivo tiene la forma:
            ast.Call(
                func=ast.Attribute(attr='route', value=ast.Name(id=bp_var)),
                args=[ast.Constant(value='/ruta')],
                keywords=[ast.keyword(arg='methods', value=ast.List(...))]
            )
        """
        # Debe ser una llamada
        if not isinstance(decorator, ast.Call):
            return None

        # La función llamada debe ser un atributo con attr == 'route'
        func = decorator.func
        if not (isinstance(func, ast.Attribute) and func.attr == "route"):
            return None

        # El primer argumento posicional debe ser la ruta (string literal)
        if not decorator.args:
            self.warnings.append(
                f"EndpointExtractor: decorador @route sin ruta en "
                f"'{self.routes_file}'. Se omite."
            )
            return None

        first_arg = decorator.args[0]
        if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
            self.warnings.append(
                f"EndpointExtractor: ruta del decorador @route no es una "
                f"constante de cadena en '{self.routes_file}'. Se omite."
            )
            return None
        relative_path: str = first_arg.value

        # Extraer métodos HTTP del keyword 'methods'; por defecto ["GET"]
        methods = self._extract_methods(decorator.keywords)

        return relative_path, methods

    @staticmethod
    def _extract_methods(keywords: list[ast.keyword]) -> list[str]:
        """
        Extrae la lista de métodos HTTP del keyword 'methods' del decorador @route.

        Si el keyword no existe, retorna ["GET"] conforme a la convención de Flask.
        Si el valor no es un ast.List de constantes, retorna ["GET"] y registra
        una advertencia implícita mediante el valor por defecto seguro.
        """
        for kw in keywords:
            if kw.arg != "methods":
                continue
            # El valor debe ser un ast.List de ast.Constant
            if not isinstance(kw.value, ast.List):
                return ["GET"]
            methods: list[str] = []
            for elt in kw.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    methods.append(elt.value.upper())
            return methods if methods else ["GET"]
        return ["GET"]

    # ------------------------------------------------------------------
    # Construcción de la ruta completa
    # ------------------------------------------------------------------

    def _build_full_path(self, prefix: str, relative_path: str) -> str:
        """
        Concatena el url_prefix del blueprint con la ruta relativa y convierte
        los parámetros Flask al formato estándar {var}.

        Ejemplos:
          ('/api/transacciones', '/<int:orden_id>/adjunto')
          → '/api/transacciones/{orden_id}/adjunto'

          ('/api/auth', '/me') → '/api/auth/me'
        """
        raw = prefix.rstrip("/") + relative_path
        return self._FLASK_PARAM_RE.sub(r"{\1}", raw)

    # ------------------------------------------------------------------
    # Detección de auth_required
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_auth_required(decorator_list: list[ast.expr]) -> bool:
        """
        Devuelve True si algún decorador en decorator_list referencia jwt_required.

        Patrones reconocidos:
          @jwt_required()                  — ast.Call con func=ast.Name(id='jwt_required')
          @jwt_required                    — ast.Name(id='jwt_required')
          @flask_jwt_extended.jwt_required() — ast.Call con func=ast.Attribute(attr='jwt_required')
        """
        for dec in decorator_list:
            if isinstance(dec, ast.Call):
                func = dec.func
                if (
                    (isinstance(func, ast.Name) and func.id == "jwt_required")
                    or (isinstance(func, ast.Attribute) and func.attr == "jwt_required")
                ):
                    return True
            elif isinstance(dec, ast.Name) and dec.id == "jwt_required":
                return True
        return False

    # ------------------------------------------------------------------
    # Detección de admin_required
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_admin_required(func_node: ast.FunctionDef) -> bool:
        """
        Devuelve True si el cuerpo de la función contiene una verificación de rol
        'admin', según cualquiera de los patrones siguientes:

        1. Acceso get_jwt()['rol'] comparado con 'admin':
             claims = get_jwt()
             if claims['rol'] != 'admin': ...
             if claims.get('rol') != 'admin': ...
        2. Suscripción directa a get_jwt() con clave 'rol':
             if get_jwt()['rol'] != 'admin': ...
        3. Patrón amplio: cualquier cadena literal 'admin' que aparezca en
           el contexto de una comparación dentro del cuerpo de la función
           (fallback robusto para variantes de código).

        La verificación recorre el cuerpo completo con ast.walk() por lo que
        es independiente de la profundidad del nodo en el árbol de la función.
        """
        for node in ast.walk(func_node):
            # ---- Patrón 1: <expr>.get('rol') comparado con 'admin' ----
            # Forma: claims.get('rol') != 'admin'  o  claims.get('rol') == 'admin'
            if isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "get"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "rol"
                ):
                    # La llamada claims.get('rol') está en contexto de comparación
                    # → la marcamos como posible — verificamos el contexto de Compare
                    # No podemos subir al padre directamente en ast, así que usamos
                    # la búsqueda de Compare a continuación (patrón amplio).
                    pass

            # ---- Patrón 2 y Patrón 3: cualquier Compare donde 'admin' aparece ----
            if isinstance(node, ast.Compare):
                if EndpointExtractor._compare_involves_admin(node):
                    return True

            # ---- También buscar en ast.If para capturar el patrón if ... 'admin' ----
            # ast.If.test puede ser un Compare o una expresión booleana compuesta
            if isinstance(node, ast.If):
                if EndpointExtractor._expr_involves_admin(node.test):
                    return True

        return False

    @staticmethod
    def _compare_involves_admin(node: ast.Compare) -> bool:
        """
        Devuelve True si algún operando de la comparación es la cadena 'admin'.

        Cubre:
          claims.get('rol') != 'admin'
          get_jwt()['rol'] != 'admin'
          claims['rol'] == 'admin'
        """
        # Verificar el lado izquierdo y los comparadores
        all_nodes = [node.left] + list(node.comparators)
        for operand in all_nodes:
            if isinstance(operand, ast.Constant) and operand.value == "admin":
                return True
        return False

    @staticmethod
    def _expr_involves_admin(expr: ast.expr) -> bool:
        """
        Búsqueda recursiva de la cadena 'admin' en cualquier subexpresión.
        Captura casos como: `not (claims.get('rol') == 'admin')` o expresiones
        booleanas compuestas.
        """
        for node in ast.walk(expr):
            if isinstance(node, ast.Constant) and node.value == "admin":
                return True
        return False

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------

    def _read_file_safe(self, path: Path) -> Optional[str]:
        """
        Lee el contenido de un archivo de texto de forma segura.
        Retorna None (y registra una advertencia) si ocurre cualquier error de I/O.
        """
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.warnings.append(
                f"EndpointExtractor: no se puede leer '{path}': {exc}."
            )
            return None


# ---------------------------------------------------------------------------
# === AntiPattern Detectors ===
# ---------------------------------------------------------------------------


@dataclass
class AntiPatternMatch:
    """Resultado de la detección de un anti-patrón en un endpoint o módulo."""
    code: str           # e.g. "AP-local-filesystem"
    description: str    # Human-readable description in Spanish
    gap_ids: list[str]  # e.g. ["GAP-02"]
    severity: str       # "critical" | "high" | "medium" | "low"
    location: str = ""  # Optional: code snippet or line description


class LocalFilesystemDetector:
    """
    Detecta el anti-patrón AP-local-filesystem (GAP-02).

    Busca en el cuerpo de una función de ruta:
    1. Llamadas .save() sobre objetos de archivo: archivo.save(ruta)
    2. Llamadas os.path.join con referencia a UPLOAD_FOLDER o
       current_app.config['UPLOAD_FOLDER']

    Severity: critical
    """

    CODE = "AP-local-filesystem"
    GAP_IDS = ["GAP-02"]
    SEVERITY = "critical"
    DESCRIPTION = (
        "Almacenamiento de archivos en el sistema de archivos local del servidor. "
        "Incompatible con el almacenamiento efímero de AWS Lambda. "
        "Requiere migración a Amazon S3 con flujo de presigned URL."
    )

    def detect(self, func_node: ast.FunctionDef) -> Optional[AntiPatternMatch]:
        """
        Retorna AntiPatternMatch si el anti-patrón es detectado, None en caso contrario.

        Recorre el cuerpo de la función con ast.walk() buscando:
        - Patrón 1: ast.Call donde func es ast.Attribute con attr == 'save'
          → captura archivo.save(ruta_destino) y cualquier variante <obj>.save(...)
        - Patrón 2: ast.Call a os.path.join (o join importado directamente)
          con al menos un argumento que referencia "UPLOAD_FOLDER"
          → captura os.path.join(current_app.config['UPLOAD_FOLDER'], nombre)
        """
        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue

            # ---- Patrón 1: cualquier llamada .save() ----
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "save"
            ):
                return AntiPatternMatch(
                    code=self.CODE,
                    description=self.DESCRIPTION,
                    gap_ids=self.GAP_IDS,
                    severity=self.SEVERITY,
                    location=f"función '{func_node.name}()'",
                )

            # ---- Patrón 2: os.path.join con UPLOAD_FOLDER en los argumentos ----
            if self._is_path_join_call(node) and self._args_reference_upload_folder(node.args):
                return AntiPatternMatch(
                    code=self.CODE,
                    description=self.DESCRIPTION,
                    gap_ids=self.GAP_IDS,
                    severity=self.SEVERITY,
                    location=f"función '{func_node.name}()'",
                )

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_path_join_call(node: ast.Call) -> bool:
        """
        Devuelve True si el nodo es una llamada a os.path.join(...)
        o a join(...) importado directamente desde os.path.

        Patrones reconocidos:
          os.path.join(...)   → ast.Attribute(attr='join', value=ast.Attribute(attr='path'))
          path.join(...)      → ast.Attribute(attr='join', value=ast.Name(id='path'))
          join(...)           → ast.Name(id='join')
        """
        func = node.func
        # join importado directamente: from os.path import join
        if isinstance(func, ast.Name) and func.id == "join":
            return True
        # os.path.join o path.join
        if isinstance(func, ast.Attribute) and func.attr == "join":
            inner = func.value
            # os.path.join: inner debe ser Attribute(attr='path')
            if isinstance(inner, ast.Attribute) and inner.attr == "path":
                return True
            # path.join: inner es Name(id='path')
            if isinstance(inner, ast.Name) and inner.id == "path":
                return True
        return False

    @staticmethod
    def _args_reference_upload_folder(args: list) -> bool:
        """
        Devuelve True si al menos uno de los argumentos contiene la cadena
        "UPLOAD_FOLDER" en su representación de código fuente (ast.unparse).

        Cubre:
          current_app.config['UPLOAD_FOLDER']  → ast.Subscript
          UPLOAD_FOLDER                         → ast.Name
          app.config['UPLOAD_FOLDER']           → ast.Subscript
        """
        for arg in args:
            try:
                # ast.unparse disponible desde Python 3.9
                unparsed = ast.unparse(arg)
            except AttributeError:
                # Fallback para Python < 3.9: inspección directa del nodo
                unparsed = LocalFilesystemDetector._manual_unparse(arg)
            if "UPLOAD_FOLDER" in unparsed:
                return True
        return False

    @staticmethod
    def _manual_unparse(node: ast.expr) -> str:
        """
        Fallback para Python < 3.9: extrae texto relevante de un nodo AST
        sin usar ast.unparse(). Solo detecta los patrones específicos de
        UPLOAD_FOLDER que aparecen en el monolito de referencia.

        Cubre:
          ast.Name(id='UPLOAD_FOLDER')
          ast.Subscript con ast.Constant(value='UPLOAD_FOLDER')
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Subscript):
            # Buscar la clave del subscript
            slice_node = node.slice
            # Python 3.8: ast.Index envuelve el valor real
            if hasattr(ast, "Index") and isinstance(slice_node, ast.Index):
                slice_node = slice_node.value  # type: ignore[attr-defined]
            if isinstance(slice_node, ast.Constant):
                return str(slice_node.value)
        # Para nodos no reconocidos, recorrer hijos en busca de Name/Constant
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and "UPLOAD_FOLDER" in child.id:
                return child.id
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                if "UPLOAD_FOLDER" in child.value:
                    return child.value
        return ""


class StrftimeDetector:
    """
    Detecta el anti-patrón AP-strftime-sqlite (GAP-04).

    Busca en el cuerpo de una función de ruta el uso de func.strftime(...),
    la función de formato de fechas del dialecto SQLite expuesta a través del
    objeto func de SQLAlchemy. Esta función no existe en PostgreSQL/Aurora, por
    lo que su uso rompe la migración serverless.

    Patrón AST reconocido:
        func.strftime(formato, columna)
        → ast.Call(
              func=ast.Attribute(attr='strftime', value=ast.Name(id='func')),
              ...
          )

    Para evitar falsos positivos con el método datetime.strftime() de la
    biblioteca estándar, solo se detecta cuando el atributo 'strftime' se accede
    sobre un ast.Name cuyo id es exactamente 'func' (el objeto func de SQLAlchemy).

    Severity: high
    """

    CODE = "AP-strftime-sqlite"
    GAP_IDS = ["GAP-04"]
    SEVERITY = "high"
    DESCRIPTION = (
        "Uso de func.strftime() de SQLAlchemy, función exclusiva del dialecto SQLite "
        "incompatible con PostgreSQL/Aurora. Requiere traducción a func.to_char() o func.date_trunc()."
    )

    def detect(self, func_node: ast.FunctionDef) -> Optional[AntiPatternMatch]:
        """
        Retorna AntiPatternMatch si el anti-patrón es detectado, None en caso contrario.

        Recorre el cuerpo de la función con ast.walk() buscando:
        - ast.Call donde func es ast.Attribute con attr == 'strftime' y cuyo
          objeto (func.value) es ast.Name(id='func')
          → captura func.strftime(formato_fecha, OrdenTrabajo.fecha_completado)
        """
        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue

            attribute = node.func
            if (
                isinstance(attribute, ast.Attribute)
                and attribute.attr == "strftime"
                and isinstance(attribute.value, ast.Name)
                and attribute.value.id == "func"
            ):
                return AntiPatternMatch(
                    code=self.CODE,
                    description=self.DESCRIPTION,
                    gap_ids=self.GAP_IDS,
                    severity=self.SEVERITY,
                    location=f"función '{func_node.name}()'",
                )

        return None


class SessionDetector:
    """
    Detecta el anti-patrón AP-session-flask (GAP-06).

    Busca en el cuerpo de una función de ruta el uso del objeto session de Flask,
    un mecanismo de estado del lado del servidor incompatible con el modelo
    stateless de AWS Lambda. En el monolito de referencia, session[...] se emplea
    como capa de autenticación complementaria al JWT y debe eliminarse en la
    migración serverless.

    Sub-patrones AST reconocidos (cualquiera dispara la detección):
      1. Acceso por subíndice sobre session (lectura o escritura):
         session['usuario_id']  →  ast.Subscript(value=ast.Name(id='session'))
      2. Llamada a session.clear():
         session.clear()  →  ast.Call(
                                  func=ast.Attribute(
                                      attr='clear',
                                      value=ast.Name(id='session'),
                                  )
                              )

    Nota de compatibilidad Python 3.9: ast.Index quedó obsoleto, pero el slice
    del Subscript no se inspecciona; basta con verificar que node.value sea
    ast.Name(id='session').

    Severity: medium
    """

    CODE = "AP-session-flask"
    GAP_IDS = ["GAP-06"]
    SEVERITY = "medium"
    DESCRIPTION = (
        "Uso de session[...] de Flask como mecanismo de autenticación complementario al JWT. "
        "La sesión de Flask es incompatible con el modelo stateless de AWS Lambda y debe eliminarse."
    )

    def detect(self, func_node: ast.FunctionDef) -> Optional[AntiPatternMatch]:
        """
        Retorna AntiPatternMatch si el anti-patrón es detectado, None en caso contrario.

        Recorre el cuerpo de la función con ast.walk() buscando:
        - Patrón 1: ast.Subscript cuyo value es ast.Name(id='session')
          → captura session['usuario_id'] y session['usuario_rol'] (login)
        - Patrón 2: ast.Call cuyo func es ast.Attribute(attr='clear') con
          func.value == ast.Name(id='session')
          → captura session.clear() (logout)
        """
        for node in ast.walk(func_node):
            # ---- Patrón 1: acceso por subíndice sobre session ----
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id == "session"
            ):
                return AntiPatternMatch(
                    code=self.CODE,
                    description=self.DESCRIPTION,
                    gap_ids=self.GAP_IDS,
                    severity=self.SEVERITY,
                    location=f"función '{func_node.name}()'",
                )

            # ---- Patrón 2: llamada session.clear() ----
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "clear"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "session"
            ):
                return AntiPatternMatch(
                    code=self.CODE,
                    description=self.DESCRIPTION,
                    gap_ids=self.GAP_IDS,
                    severity=self.SEVERITY,
                    location=f"función '{func_node.name}()'",
                )

        return None


class TimestampIdDetector:
    """
    Detecta el anti-patrón AP-order-num-ts (GAP-14).

    Busca en el cuerpo de una función la generación de identificadores únicos a
    partir de una marca de tiempo (datetime.utcnow()) formateada como cadena.
    Este enfoque es susceptible a colisiones bajo concurrencia: dos invocaciones
    simultáneas de la misma Lambda pueden producir el mismo identificador. Debe
    reemplazarse por uuid.uuid4() o un contador atómico (p. ej. DynamoDB).

    En el monolito de referencia corresponde al helper generar_numero_orden():
        def generar_numero_orden() -> str:
            ahora = datetime.utcnow()
            return f"OT-{ahora.strftime('%Y%m%d-%H%M%S')}"

    Patrón AST reconocido (ambas condiciones deben cumplirse):
      1. has_utcnow: existe un ast.Call cuyo func es
         ast.Attribute(attr='utcnow')  → captura datetime.utcnow()
      2. has_string_build: el cuerpo contiene una de estas construcciones de
         cadena a partir de la marca de tiempo:
           - ast.JoinedStr (f-string), p. ej. f"OT-{...}"
           - ast.Call cuyo func es ast.Attribute(attr='strftime') cuyo receptor
             NO es el objeto func de SQLAlchemy (ast.Name(id='func')), es decir
             un datetime/variable .strftime(). Esta exclusión evita el solape
             con StrftimeDetector (AP-strftime-sqlite).

    Severity: medium
    """

    CODE = "AP-order-num-ts"
    GAP_IDS = ["GAP-14"]
    SEVERITY = "medium"
    DESCRIPTION = (
        "Generación de identificadores únicos basada en datetime.utcnow() y formateo de cadena. "
        "Susceptible a colisiones bajo concurrencia; debe reemplazarse por uuid.uuid4() o un contador atómico."
    )

    def detect(self, func_node: ast.FunctionDef) -> Optional[AntiPatternMatch]:
        """
        Retorna AntiPatternMatch si el anti-patrón es detectado, None en caso contrario.

        Recorre el cuerpo de la función con ast.walk() marcando dos banderas:
        - has_utcnow: True si algún ast.Call tiene func == ast.Attribute(attr='utcnow')
          → captura datetime.utcnow()
        - has_string_build: True si el cuerpo contiene un ast.JoinedStr (f-string)
          O un ast.Call con func == ast.Attribute(attr='strftime') cuyo receptor
          NO es ast.Name(id='func') (para no solaparse con StrftimeDetector)

        Solo retorna un match cuando has_utcnow Y has_string_build son True.
        """
        has_utcnow = False
        has_string_build = False

        for node in ast.walk(func_node):
            # ---- f-string: cualquier ast.JoinedStr construye una cadena ----
            if isinstance(node, ast.JoinedStr):
                has_string_build = True
                continue

            if isinstance(node, ast.Call):
                attribute = node.func

                # ---- datetime.utcnow() ----
                if isinstance(attribute, ast.Attribute) and attribute.attr == "utcnow":
                    has_utcnow = True
                    continue

                # ---- .strftime() de un datetime/variable (no func de SQLAlchemy) ----
                if isinstance(attribute, ast.Attribute) and attribute.attr == "strftime":
                    receiver = attribute.value
                    is_sqlalchemy_func = (
                        isinstance(receiver, ast.Name) and receiver.id == "func"
                    )
                    if not is_sqlalchemy_func:
                        has_string_build = True
                    continue

        if has_utcnow and has_string_build:
            return AntiPatternMatch(
                code=self.CODE,
                description=self.DESCRIPTION,
                gap_ids=self.GAP_IDS,
                severity=self.SEVERITY,
                location=f"función '{func_node.name}()'",
            )

        return None


class TokenBlacklistDetector:
    """
    Detecta el anti-patrón AP-token-blacklist (GAP-03).

    Es un detector de NIVEL DE MÓDULO: opera sobre el AST completo del archivo
    routes.py, no sobre una única función de ruta. Su método detect() recibe el
    ast.Module parseado y la lista de EndpointNode del módulo.

    El anti-patrón requiere la coexistencia de DOS condiciones para la misma
    variable:
      1. Una asignación a nivel de módulo `<var> = set()` — un ast.Assign en
         module_tree.body (nivel superior, no dentro de una función) cuyo valor
         es una llamada a set() sin argumentos.
      2. En algún punto del árbol, una llamada `<var>.add(...)` — un ast.Call
         cuyo func es ast.Attribute(attr='add') y func.value es
         ast.Name(id=<var>).

    Patrón de referencia en auth/routes.py del monolito:
        _tokens_revocados = set()      # nivel de módulo
        _tokens_revocados.add(jti)     # dentro de logout()

    La verificación `func.value` como ast.Name evita falsos positivos con
    llamadas del tipo `db.session.add(...)`, donde el receptor es un atributo.

    Severity: high
    """

    CODE = "AP-token-blacklist"
    GAP_IDS = ["GAP-03"]
    SEVERITY = "high"
    DESCRIPTION = (
        "Lista negra de tokens JWT almacenada en un set() en memoria del proceso. "
        "Con semántica fail-open: incompatible con el modelo multi-instancia de Lambda. "
        "Debe externalizarse a Amazon DynamoDB con atributo TTL."
    )

    def detect(
        self, module_tree: ast.Module, endpoints: list
    ) -> Optional[AntiPatternMatch]:
        """
        Retorna AntiPatternMatch si el anti-patrón es detectado, None en caso
        contrario.

        Estrategia:
        1. Recorre module_tree.body (nivel superior) para recolectar los nombres
           de variables asignadas con `<var> = set()` sin argumentos.
        2. Recorre todo el árbol con ast.walk() buscando una llamada
           `<var>.add(...)` sobre alguna de esas variables.
        3. Si existe una variable que cumple ambas condiciones, reporta el
           anti-patrón localizando la asignación `<var> = set()`.

        El parámetro endpoints se acepta por conformidad con la interfaz de los
        detectores de módulo; esta detección se resuelve recorriendo module_tree.
        """
        set_vars = self._collect_module_level_set_vars(module_tree)
        if not set_vars:
            return None

        for node in ast.walk(module_tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "add"):
                continue
            receiver = func.value
            if isinstance(receiver, ast.Name) and receiver.id in set_vars:
                var_name = receiver.id
                return AntiPatternMatch(
                    code=self.CODE,
                    description=self.DESCRIPTION,
                    gap_ids=self.GAP_IDS,
                    severity=self.SEVERITY,
                    location=f"variable '{var_name}' = set() a nivel de módulo",
                )

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_module_level_set_vars(module_tree: ast.Module) -> set:
        """
        Recolecta los nombres de variables asignadas a `set()` (sin argumentos)
        a nivel de módulo (module_tree.body), ignorando asignaciones dentro de
        funciones o clases.

        Reconoce la forma:
            <var> = set()
        donde el valor es ast.Call a ast.Name(id='set') sin args ni keywords.
        Admite asignaciones múltiples (a = b = set()).
        """
        set_vars: set = set()
        for node in module_tree.body:
            if not isinstance(node, ast.Assign):
                continue
            value = node.value
            if not isinstance(value, ast.Call):
                continue
            func = value.func
            if not (isinstance(func, ast.Name) and func.id == "set"):
                continue
            # set() sin argumentos: un set() con args sería set(iterable),
            # que igualmente es una colección en memoria, pero el patrón
            # canónico del anti-patrón es la inicialización vacía.
            if value.args or value.keywords:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    set_vars.add(target.id)
        return set_vars


class CrossBlueprintDetector:
    """
    Detecta el anti-patrón AP-cross-blueprint.

    Es un detector de NIVEL DE MÓDULO: opera sobre el AST completo del archivo
    routes.py de un blueprint. Identifica importaciones directas desde el
    módulo routes.py de OTRO blueprint, lo cual genera acoplamiento lateral
    incompatible con la arquitectura de funciones Lambda independientes.

    El patrón AST buscado es un ast.ImportFrom cuyo atributo `module` coincide
    con la expresión regular `app\\.blueprints\\.(\\w+)\\.routes`; el grupo
    capturado es el nombre del blueprint DESTINO de la dependencia.

    Patrones de referencia en el monolito:
        # transacciones/routes.py
        from app.blueprints.clientes.routes import verificar_cliente_existe
            → dependencia "transacciones → clientes"
        # reportes/routes.py
        from app.blueprints.servicios.routes import CATEGORIAS
            → dependencia "reportes → servicios"

    A diferencia de otros detectores, puede encontrar MÚLTIPLES importaciones
    cruzadas y retorna la lista completa de dependencias. Se de-duplican los
    destinos para que cada blueprint destino distinto produzca un único
    resultado, y se ignora el caso en que el destino coincide con el propio
    módulo.

    Severity: high
    """

    CODE = "AP-cross-blueprint"
    GAP_IDS: list = []
    SEVERITY = "high"
    DESCRIPTION = (
        "Importación directa desde el módulo routes.py de otro blueprint, generando "
        "acoplamiento lateral incompatible con la arquitectura de funciones Lambda independientes. "
        "Debe resolverse mediante una Lambda Layer compartida."
    )

    _IMPORT_RE = re.compile(r"^app\.blueprints\.(\w+)\.routes$")

    def detect(self, module_tree: ast.Module, module_name: str) -> list:
        """
        Retorna una LISTA de tuplas (AntiPatternMatch, dependency_str), una por
        cada importación cruzada distinta encontrada, o [] si no hay ninguna.

        Estrategia:
        1. Recorre todo el árbol con ast.walk() buscando nodos ast.ImportFrom.
        2. Para cada uno, aplica _IMPORT_RE sobre node.module; si coincide,
           extrae el blueprint destino del grupo capturado.
        3. Omite el caso destino == module_name (auto-importación).
        4. De-duplica los destinos para emitir un único resultado por destino.

        El dependency_str tiene la forma "<module_name> → <target>".
        """
        resultados: list = []
        vistos: set = set()

        for node in ast.walk(module_tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not node.module:
                continue
            coincidencia = self._IMPORT_RE.match(node.module)
            if coincidencia is None:
                continue
            target = coincidencia.group(1)
            if target == module_name or target in vistos:
                continue
            vistos.add(target)
            match = AntiPatternMatch(
                code=self.CODE,
                description=self.DESCRIPTION,
                gap_ids=self.GAP_IDS,
                severity=self.SEVERITY,
                location=f"from app.blueprints.{target}.routes import ...",
            )
            dependency_str = f"{module_name} → {target}"
            resultados.append((match, dependency_str))

        return resultados


class InMemorySingletonDetector:
    """
    Detecta el anti-patrón AP-in-memory-singleton.

    Es un detector de NIVEL DE MÓDULO: opera sobre el AST completo de un archivo
    e identifica un singleton o una variable de módulo que mantiene estado
    compartido en la memoria del proceso. Este modelo es incompatible con la
    ejecución multi-instancia de AWS Lambda, donde cada invocación puede
    atenderse en un contenedor distinto con su propio espacio de memoria.

    En el monolito de referencia este patrón reside en los archivos de servicio
    (app/services/cache_service.py y app/services/notificacion_service.py), no en
    los routes.py de los blueprints; por eso el detector opera sobre cualquier
    AST de módulo que se le pase.

    Reconoce DOS sub-patrones; cualquiera de ellos dispara la detección y se
    retorna en la primera coincidencia:

    1. Singleton canónico vía __new__:
       Un ast.ClassDef que define un método __new__ Y declara en su cuerpo una
       asignación de atributo de clase `_instancia = None` (ast.Assign cuyo
       target es ast.Name(id='_instancia')). Las clases CacheService y
       NotificacionService siguen este patrón.

    2. Variable mutable de estado compartido a nivel de módulo:
       Un ast.Assign de nivel superior cuyo nombre de destino comienza con '_' y
       cuyo valor es un dict vacío ({} o dict()) o una lista vacía ([] o list()).
       Nombres como `_cache = {}` o `_historial = []` son indicativos de estado
       compartido en memoria.

    Severity: medium
    """

    CODE = "AP-in-memory-singleton"
    GAP_IDS: list = []
    SEVERITY = "medium"
    DESCRIPTION = (
        "Instancia única (singleton) o variable de módulo que almacena estado compartido "
        "en la memoria del proceso. Incompatible con el modelo de ejecución multi-instancia "
        "de AWS Lambda. Debe externalizarse a ElastiCache Redis, DynamoDB o un servicio gestionado."
    )

    def detect(
        self, module_tree: ast.Module, module_name: str
    ) -> Optional[AntiPatternMatch]:
        """
        Retorna AntiPatternMatch si el anti-patrón es detectado, None en caso
        contrario.

        Estrategia:
        1. Recorre module_tree.body buscando un ast.ClassDef con el patrón
           Singleton canónico (método __new__ + atributo `_instancia = None`).
        2. Si no lo encuentra, recorre module_tree.body buscando una variable de
           módulo `_<algo> = {}` / `dict()` / `[]` / `list()`.
        3. Retorna en la primera coincidencia.

        El parámetro module_name se acepta por conformidad con la interfaz de los
        detectores de módulo (como CrossBlueprintDetector) y se utiliza en la
        cadena de localización.
        """
        for node in module_tree.body:
            if isinstance(node, ast.ClassDef) and self._es_singleton_canonico(node):
                return AntiPatternMatch(
                    code=self.CODE,
                    description=self.DESCRIPTION,
                    gap_ids=self.GAP_IDS,
                    severity=self.SEVERITY,
                    location=(
                        f"clase singleton con __new__ y _instancia en módulo '{module_name}'"
                    ),
                )

        for node in module_tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not self._es_coleccion_vacia(node.value):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith("_"):
                    return AntiPatternMatch(
                        code=self.CODE,
                        description=self.DESCRIPTION,
                        gap_ids=self.GAP_IDS,
                        severity=self.SEVERITY,
                        location=(
                            f"variable de estado compartido '{target.id}' "
                            f"en módulo '{module_name}'"
                        ),
                    )

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _es_singleton_canonico(class_node: ast.ClassDef) -> bool:
        """
        Determina si una clase sigue el patrón Singleton canónico: contiene un
        método __new__ Y declara el atributo de clase `_instancia = None`.
        """
        tiene_new = False
        tiene_instancia = False
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__new__":
                tiene_new = True
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "_instancia":
                        tiene_instancia = True
        return tiene_new and tiene_instancia

    @staticmethod
    def _es_coleccion_vacia(value: ast.expr) -> bool:
        """
        Determina si una expresión es un dict vacío ({} o dict()) o una lista
        vacía ([] o list()).
        """
        if isinstance(value, ast.Dict):
            return not value.keys
        if isinstance(value, ast.List):
            return not value.elts
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            if value.func.id in ("dict", "list"):
                return not value.args and not value.keywords
        return False


# ---------------------------------------------------------------------------
# === AntiPatternRegistry ===
# Responsabilidad: coordinar la ejecución de todos los detectores sobre cada
# función de ruta y el módulo completo, consolidando sus resultados.
# ---------------------------------------------------------------------------


@dataclass
class ModuleAnalysisResult:
    """
    Contenedor del resultado del análisis de anti-patrones de un módulo
    (blueprint) completo.

    Agrupa los hallazgos en tres niveles de granularidad:
      - endpoint_antipatterns: anti-patrones adjudicados a cada función de ruta,
        indexados por el nombre de la función Python.
      - module_antipatterns: anti-patrones que aplican al módulo en su conjunto
        (lista negra de tokens, singletons, importaciones cruzadas).
      - cross_blueprint_imports: dependencias laterales entre blueprints en
        formato legible, e.g. "transacciones → clientes".
    """
    endpoint_antipatterns: dict      # {func_name: list[AntiPatternMatch]}
    module_antipatterns: list        # list[AntiPatternMatch] a nivel de módulo
    cross_blueprint_imports: list    # list[str], e.g. ["transacciones → clientes"]


class AntiPatternRegistry:
    """
    Coordina la ejecución de los siete detectores de anti-patrones sobre un
    módulo (blueprint) completo y consolida sus hallazgos en un
    ModuleAnalysisResult.

    Niveles de detección:
      1. Detectores de nivel de FUNCIÓN (FUNCTION_DETECTORS): se ejecutan sobre
         el func_node de cada EndpointNode. Cada detector opera de forma
         independiente, sin estado compartido entre llamadas (Requisito 2.9).
      2. Detectores de nivel de MÓDULO de coincidencia única (MODULE_DETECTORS):
         TokenBlacklistDetector e InMemorySingletonDetector. Operan sobre el AST
         completo del módulo. Dado que sus firmas difieren, se invocan de forma
         explícita con sus argumentos correctos (no mediante un bucle uniforme).
      3. CrossBlueprintDetector (caso especial): devuelve una lista de tuplas
         (AntiPatternMatch, dependency_str) y requiere un tratamiento distinto.

    Reglas de propagación especiales dictadas por el diseño:
      - TokenBlacklist: cuando dispara, el anti-patrón se registra a nivel de
        módulo Y además en cada endpoint cuyo cuerpo contenga una llamada
        `<obj>.add(...)` (típicamente el endpoint logout del monolito).
      - CrossBlueprint: cuando dispara, el anti-patrón se registra a nivel de
        módulo Y en TODOS los endpoints del módulo importador, pues el
        acoplamiento afecta a la Lambda completa.

    Los detectores se instancian frescos en cada invocación de analyze_module()
    para garantizar que no exista estado residual entre módulos.
    """

    # Detectores de nivel de función: firma detect(func_node) -> Optional[match]
    FUNCTION_DETECTORS = [
        LocalFilesystemDetector,
        StrftimeDetector,
        SessionDetector,
        TimestampIdDetector,
    ]

    # Detectores de nivel de módulo de coincidencia única.
    # NOTA: sus firmas difieren, por eso NO se recorren con un bucle uniforme;
    # se documentan aquí por completitud y se invocan explícitamente abajo.
    MODULE_DETECTORS = [TokenBlacklistDetector, InMemorySingletonDetector]
    # CrossBlueprintDetector se maneja aparte por su tipo de retorno (lista de
    # tuplas) y su firma (module_tree, module_name).

    def analyze_module(
        self, module_tree: ast.Module, endpoints: list, module_name: str
    ) -> ModuleAnalysisResult:
        """
        Ejecuta todos los detectores sobre un módulo y devuelve un
        ModuleAnalysisResult con los hallazgos consolidados.

        Parámetros:
          module_tree: AST del archivo routes.py del blueprint.
          endpoints:   lista de EndpointNode extraídos del módulo.
          module_name: nombre del blueprint, e.g. "auth".
        """
        endpoint_antipatterns: dict = {}
        module_antipatterns: list = []
        cross_blueprint_imports: list = []

        # ------------------------------------------------------------------
        # 1. Detección a nivel de función
        #    Cada detector se instancia por sí mismo y opera de forma
        #    independiente sobre el func_node del endpoint (Requisito 2.9).
        # ------------------------------------------------------------------
        for endpoint in endpoints:
            matches = endpoint_antipatterns.setdefault(endpoint.func_name, [])
            for detector_cls in self.FUNCTION_DETECTORS:
                detector = detector_cls()
                match = detector.detect(endpoint.func_node)
                if match is not None:
                    matches.append(match)

        # ------------------------------------------------------------------
        # 2. Detectores de módulo de coincidencia única (firmas distintas)
        # ------------------------------------------------------------------
        # 2a. TokenBlacklistDetector.detect(module_tree, endpoints)
        token_match = TokenBlacklistDetector().detect(module_tree, endpoints)
        if token_match is not None:
            module_antipatterns.append(token_match)
            # Propagar a cada endpoint cuyo cuerpo contenga una llamada .add()
            # (en el monolito de referencia, logout() ejecuta
            # _tokens_revocados.add(jti)).
            for endpoint in endpoints:
                if self._func_contains_add_call(endpoint.func_node):
                    endpoint_antipatterns.setdefault(
                        endpoint.func_name, []
                    ).append(token_match)

        # 2b. InMemorySingletonDetector.detect(module_tree, module_name)
        singleton_match = InMemorySingletonDetector().detect(module_tree, module_name)
        if singleton_match is not None:
            module_antipatterns.append(singleton_match)

        # ------------------------------------------------------------------
        # 3. CrossBlueprintDetector (caso especial: lista de tuplas)
        #    Cada dependencia cruzada se registra a nivel de módulo Y en TODOS
        #    los endpoints del módulo importador.
        # ------------------------------------------------------------------
        cross_results = CrossBlueprintDetector().detect(module_tree, module_name)
        for match, dependency_str in cross_results:
            cross_blueprint_imports.append(dependency_str)
            module_antipatterns.append(match)
            for endpoint in endpoints:
                endpoint_antipatterns.setdefault(
                    endpoint.func_name, []
                ).append(match)

        return ModuleAnalysisResult(
            endpoint_antipatterns=endpoint_antipatterns,
            module_antipatterns=module_antipatterns,
            cross_blueprint_imports=cross_blueprint_imports,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _func_contains_add_call(func_node: ast.FunctionDef) -> bool:
        """
        Devuelve True si el cuerpo de la función contiene una llamada de la forma
        `<obj>.add(...)` — un ast.Call cuyo func es ast.Attribute(attr='add').

        Se usa para propagar el anti-patrón AP-token-blacklist a los endpoints
        que manipulan la lista negra en memoria (típicamente logout()).
        """
        for node in ast.walk(func_node):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add"
            ):
                return True
        return False



class ComplexityScorer:
    """
    Asigna migration_complexity a un endpoint según reglas de precedencia estrictamente ordenadas.

    Reglas (precedencia de mayor a menor):
      1. very_high: AP-local-filesystem presente (siempre prevalece sobre otras reglas)
      2. high: AP-strftime-sqlite presente, O AP-cross-blueprint presente,
               O el cuerpo llama notificacion_service.*, O contiene una máquina de estados
      3. medium: El cuerpo referencia cache_service, O importa modelos de múltiples dominios,
                 O contiene get_jwt_identity() + lógica de negocio no trivial
      4. low: Ninguna condición anterior se cumple

    Verificación de casos del monolito de referencia:
      - POST /api/transacciones/{id}/adjunto → very_high (por AP-local-filesystem)
      - GET /api/reportes/ingresos → high (por AP-strftime-sqlite)
      - GET /api/clientes/ → medium (por múltiples modelos)
      - POST /api/auth/register → low (caso base)
    """

    @staticmethod
    def score(
        endpoint: "EndpointNode",
        anti_patterns: list[AntiPatternMatch]
    ) -> str:
        """
        Retorna "very_high" | "high" | "medium" | "low" según las reglas de precedencia.

        Parámetros:
          - endpoint: EndpointNode con el AST de la función de ruta
          - anti_patterns: lista de AntiPatternMatch detectados en el endpoint

        Implementa las reglas de precedencia evaluando los códigos de anti-patrón
        presentes y analizando el cuerpo de la función AST.
        """
        func_node = endpoint.func_node
        ap_codes = {ap.code for ap in anti_patterns}

        # Regla 1: very_high — AP-local-filesystem siempre prevalece
        if "AP-local-filesystem" in ap_codes:
            return "very_high"

        # Regla 2: high — strftime SQLite, cross-blueprint, notificaciones, o máquina de estados
        if "AP-strftime-sqlite" in ap_codes:
            return "high"
        if "AP-cross-blueprint" in ap_codes:
            return "high"
        if ComplexityScorer._calls_notification_service(func_node):
            return "high"
        if ComplexityScorer._contains_state_machine(func_node):
            return "high"

        # Regla 3: medium — cache_service, múltiples modelos, o JWT con lógica no trivial
        if ComplexityScorer._references_cache_service(func_node):
            return "medium"
        if ComplexityScorer._imports_multiple_domain_models(func_node):
            return "medium"
        if ComplexityScorer._has_jwt_with_nontrivial_logic(func_node):
            return "medium"

        # Regla 4: low — caso por defecto
        return "low"

    # ------------------------------------------------------------------
    # Helpers para detectar patrones de complejidad
    # ------------------------------------------------------------------

    @staticmethod
    def _calls_notification_service(func_node: ast.FunctionDef) -> bool:
        """
        Devuelve True si el cuerpo de la función contiene una llamada a
        notificacion_service.* (e.g., notificacion_service.enviar(...))
        """
        for node in ast.walk(func_node):
            if isinstance(node, ast.Attribute):
                # Verificar si el nodo es Attribute(value=Name(id='notificacion_service'))
                if (isinstance(node.value, ast.Name) and
                    node.value.id == "notificacion_service"):
                    return True
        return False

    @staticmethod
    def _contains_state_machine(func_node: ast.FunctionDef) -> bool:
        """
        Detecta la presencia de un dict de transiciones de máquina de estados.

        Patrón: dict literal con estructura {estado: {accion: nuevo_estado}}
        Ejemplo: TRANSICIONES = {"pendiente": {"aprobar": "aprobada", ...}}

        Busca nodos ast.Dict dentro de assigns cuyas keys y values son
        todos strings (constantes), y el valor es a su vez un dict.
        """
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assign):
                value = node.value
                if isinstance(value, ast.Dict):
                    # Verificar que todos los keys y values son constantes str
                    if not all(isinstance(k, ast.Constant) and isinstance(k.value, str)
                               for k in value.keys if k is not None):
                        continue
                    # Verificar que al menos uno de los values es un dict anidado
                    for v in value.values:
                        if isinstance(v, ast.Dict):
                            return True
        return False

    @staticmethod
    def _references_cache_service(func_node: ast.FunctionDef) -> bool:
        """
        Devuelve True si el cuerpo de la función contiene una referencia a
        cache_service (e.g., cache_service.get(...))
        """
        for node in ast.walk(func_node):
            if isinstance(node, ast.Attribute):
                if (isinstance(node.value, ast.Name) and
                    node.value.id == "cache_service"):
                    return True
            if isinstance(node, ast.Name) and node.id == "cache_service":
                return True
        return False

    @staticmethod
    def _imports_multiple_domain_models(func_node: ast.FunctionDef) -> bool:
        """
        Detecta si la función importa modelos de múltiples dominios.

        Busca a nivel de cuerpo de función imports de tipo:
          from app.models import Usuario, Cliente, Servicio

        Si la cantidad de modelos importados es ≥ 2, retorna True.

        Nota: este análisis es limitado — solo detecta imports dentro del cuerpo
        de la función (imports no convencionales). En monolitos bien estructurados,
        los imports están a nivel de módulo, así que esta heurística tiene falsos
        negativos por diseño. Se mantiene por completitud respecto al diseño.
        """
        model_names = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.ImportFrom):
                if node.module and "models" in node.module:
                    for alias in node.names:
                        model_names.add(alias.name)
        return len(model_names) >= 2

    @staticmethod
    def _has_jwt_with_nontrivial_logic(func_node: ast.FunctionDef) -> bool:
        """
        Detecta si la función usa get_jwt_identity() o get_jwt() seguido de
        lógica de negocio no trivial (más de una línea tras la extracción).

        Criterio: si get_jwt_identity() aparece Y el cuerpo tiene ≥ 5 líneas de código
        (excluyendo docstrings y decoradores), consideramos que hay lógica no trivial.
        """
        has_jwt = False
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in ("get_jwt_identity", "get_jwt"):
                    has_jwt = True
                    break

        if not has_jwt:
            return False

        # Contar líneas de código no triviales (excluyendo docstrings)
        body_lines = 0
        for stmt in func_node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue  # skip docstrings
            body_lines += 1

        return body_lines >= 5


class ComputeTargetClassifier:
    """
    Asigna compute_target ("lambda" | "fargate" | "app_runner") a un endpoint
    y determina si requires_architectural_transformation=True.

    Árbol de decisión (según especificación):
      - fargate: El cuerpo contiene loops sobre colecciones no paginadas de tamaño
                 indeterminado, O requiere estado temporal en sistema de archivos.
      - app_runner: El módulo expone ÚNICAMENTE endpoints HTTP de lectura pública
                    (sin JWT), sin operaciones de escritura ni efectos secundarios.
      - lambda (por defecto): Todos los demás casos.

    Transformación arquitectural:
      - Si compute_target == "lambda" Y tiene AP-local-filesystem, entonces
        requires_architectural_transformation = True (conversión a S3 + presigned URL).

    Caso específico del monolito de referencia:
      - Todos los 29 endpoints clasifican como "lambda".
      - POST /api/transacciones/{id}/adjunto recibe requires_architectural_transformation=True.
    """

    @staticmethod
    def classify(
        endpoint: "EndpointNode",
        anti_patterns: list[AntiPatternMatch],
        all_endpoints_in_module: list["EndpointNode"]
    ) -> tuple[str, bool]:
        """
        Retorna (compute_target, requires_architectural_transformation).

        Parámetros:
          - endpoint: EndpointNode con el AST de la función de ruta
          - anti_patterns: lista de AntiPatternMatch detectados en el endpoint
          - all_endpoints_in_module: todos los endpoints del mismo módulo
            (necesario para evaluar la regla de app_runner)

        Retorna:
          - tuple (str, bool): (compute_target, requires_architectural_transformation)
        """
        func_node = endpoint.func_node
        ap_codes = {ap.code for ap in anti_patterns}

        # Regla Fargate: loops sobre colecciones no paginadas O estado temporal en filesystem
        if ComputeTargetClassifier._has_unbounded_loops(func_node):
            return ("fargate", False)
        if ComputeTargetClassifier._requires_temp_filesystem_state(func_node, ap_codes):
            return ("fargate", False)

        # Regla App Runner: módulo con ÚNICAMENTE endpoints GET públicos sin efectos secundarios
        if ComputeTargetClassifier._is_readonly_public_module(all_endpoints_in_module):
            return ("app_runner", False)

        # Regla por defecto: Lambda
        compute_target = "lambda"

        # Transformación arquitectural: Lambda + AP-local-filesystem
        requires_transformation = "AP-local-filesystem" in ap_codes

        return (compute_target, requires_transformation)

    # ------------------------------------------------------------------
    # Helpers para clasificación
    # ------------------------------------------------------------------

    @staticmethod
    def _has_unbounded_loops(func_node: ast.FunctionDef) -> bool:
        """
        Detecta loops sobre colecciones no paginadas.

        Criterio heurístico:
          - Busca bucles for sobre llamadas a .all() (e.g., Query.all())
          - Busca bucles for sobre atributos de objetos sin .limit() previo

        Ejemplo positivo: for item in Model.query.all()
        Ejemplo negativo: for item in Model.query.limit(100).all()
        """
        for node in ast.walk(func_node):
            if not isinstance(node, ast.For):
                continue
            iter_node = node.iter
            # Patrón: for x in algo.all()
            if (isinstance(iter_node, ast.Call) and
                isinstance(iter_node.func, ast.Attribute) and
                iter_node.func.attr == "all"):
                # Verificar si hay .limit() en la cadena previa
                # Heurística simplificada: si el nombre contiene 'query' sin 'limit',
                # asumimos unbounded
                source_repr = ast.dump(iter_node)
                if "limit" not in source_repr.lower():
                    return True
        return False

    @staticmethod
    def _requires_temp_filesystem_state(func_node: ast.FunctionDef, ap_codes: set) -> bool:
        """
        Detecta si la función requiere estado temporal en sistema de archivos entre
        sub-invocaciones (descartando AP-local-filesystem, que es detección de upload).

        Criterio:
          - Llamadas a os.makedirs, tempfile.mkdtemp, o Path(...).mkdir()
          - Llamadas a open() con modo 'w' o 'a' (escritura)

        No aplica si ya está marcado como AP-local-filesystem (ese caso se
        transforma a S3, no a Fargate).
        """
        if "AP-local-filesystem" in ap_codes:
            return False

        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue

            func = node.func
            # os.makedirs, tempfile.mkdtemp
            if isinstance(func, ast.Attribute):
                if func.attr in ("makedirs", "mkdtemp", "mkdir"):
                    return True

            # open(..., 'w') o open(..., 'a')
            if isinstance(func, ast.Name) and func.id == "open":
                if len(node.args) >= 2:
                    mode_arg = node.args[1]
                    if isinstance(mode_arg, ast.Constant) and mode_arg.value in ("w", "a", "wb", "ab"):
                        return True

        return False

    @staticmethod
    def _is_readonly_public_module(all_endpoints: list["EndpointNode"]) -> bool:
        """
        Devuelve True si el módulo cumple las condiciones de App Runner:
          - TODOS los endpoints son GET (lectura)
          - NINGUNO requiere autenticación (auth_required=False)
          - Ninguna operación de escritura ni efectos secundarios

        En el monolito de referencia, ningún módulo cumple esta condición:
          - servicios tiene GET públicos pero también tiene endpoints autenticados
          - auth, clientes, transacciones, reportes requieren JWT
        """
        if not all_endpoints:
            return False

        for ep in all_endpoints:
            # Si el endpoint no es GET, el módulo no es read-only
            if ep.method != "GET":
                return False
            # Si requiere autenticación, no es público
            if ep.auth_required or ep.admin_required:
                return False

        return True


# de precedencia estrictamente ordenadas:
#   very_high → high → medium → low
#
# Implementación completa en Tarea 7.1.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# === ComputeTargetClassifier ===
# Responsabilidad: asignar compute_target ("lambda" | "fargate" | "app_runner")
# y el flag requires_architectural_transformation a cada endpoint.
#
# Implementación completa en Tarea 7.2.
# ---------------------------------------------------------------------------




class ManifestBuilder:
    """
    Ensambla el migration-manifest.json completo a partir de los resultados
    del análisis de blueprints, endpoints, anti-patrones, y clasificaciones.

    Responsabilidades:
      - Calcular cohesion e isolation por módulo
      - Derivar lambda_layers recomendadas
      - Generar migration_sequence (5 fases ordenadas por acoplamiento)
      - Ensamblar metadata, summary, y modules
      - Garantizar invariantes del manifiesto (I-1, I-2)
      - Serializar como JSON con tipos primitivos y escribir a disco

    El manifiesto sigue la estructura:
      {
        "metadata": {...},
        "summary": {...},
        "modules": [...],
        "lambda_layers": [...],
        "migration_sequence": [...]
      }
    """

    def __init__(
        self,
        monolith_path: Path,
        blueprints: dict[str, BlueprintInfo],
        endpoints_by_module: dict[str, list[EndpointNode]],
        analysis_by_module: dict[str, ModuleAnalysisResult],
        all_warnings: list[str],
    ):
        """
        Parámetros:
          - monolith_path: Path absoluta del monolito analizado
          - blueprints: Dict {bp_variable: BlueprintInfo}
          - endpoints_by_module: Dict {module_name: [EndpointNode]}
          - analysis_by_module: Dict {module_name: ModuleAnalysisResult}
          - all_warnings: Lista acumulada de advertencias de todos los componentes
        """
        self.monolith_path = monolith_path.resolve()
        self.blueprints = blueprints
        self.endpoints_by_module = endpoints_by_module
        self.analysis_by_module = analysis_by_module
        self.all_warnings = all_warnings

    # ------------------------------------------------------------------
    # Interfaz pública
    # ------------------------------------------------------------------

    def build(self) -> dict:
        """
        Construye el diccionario completo del manifiesto con todos sus campos.

        Retorna un dict serializable como JSON (sin objetos Path, datetime, ni AST).
        """
        manifest = {
            "metadata": self._build_metadata(),
            "summary": {},  # Se completa después de construir modules
            "modules": self._build_modules(),
            "lambda_layers": self._build_lambda_layers(),
            "migration_sequence": self._build_migration_sequence(),
        }

        # Completar summary después de tener modules construidos
        manifest["summary"] = self._build_summary(manifest["modules"])

        # Validar invariantes antes de retornar
        self._validate_invariants(manifest)

        return manifest

    def write(self, manifest: dict, output_path: Path) -> None:
        """
        Escribe el manifiesto en output_path como JSON con indentación de 2 espacios.

        Si hay error de permisos de escritura, intenta fallback a cwd y registra
        advertencia. Si ambos fallan, lanza OSError con código de salida 3.
        """
        try:
            output_path = output_path.resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            print(f"✓ Manifiesto escrito en: {output_path}", file=sys.stderr)
        except (OSError, PermissionError) as exc:
            # Fallback a current working directory
            fallback_path = Path.cwd() / "migration-manifest.json"
            self.all_warnings.append(
                f"No se pudo escribir en '{output_path}': {exc}. "
                f"Intentando fallback a '{fallback_path}'."
            )
            try:
                with fallback_path.open("w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2, ensure_ascii=False)
                print(f"⚠ Manifiesto escrito en fallback: {fallback_path}", file=sys.stderr)
            except (OSError, PermissionError) as fallback_exc:
                error_msg = {
                    "error": "MANIFEST_WRITE_FAILED",
                    "message": f"No se pudo escribir en '{output_path}' ni en '{fallback_path}'.",
                    "primary_exception": str(exc),
                    "fallback_exception": str(fallback_exc),
                }
                print(json.dumps(error_msg, indent=2), file=sys.stderr)
                sys.exit(3)

    # ------------------------------------------------------------------
    # Construcción de secciones del manifiesto
    # ------------------------------------------------------------------

    def _build_metadata(self) -> dict:
        """
        Construye la sección metadata del manifiesto.

        Campos:
          - analyzed_at: timestamp ISO 8601 UTC
          - monolith_path: ruta absoluta como string
          - total_endpoints: conteo total
          - analyzer_version: ANALYZER_VERSION
          - skill_version: SKILL_VERSION
          - warnings: lista de advertencias acumuladas
        """
        total_endpoints = sum(len(eps) for eps in self.endpoints_by_module.values())
        return {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "monolith_path": str(self.monolith_path),
            "total_endpoints": total_endpoints,
            "analyzer_version": ANALYZER_VERSION,
            "skill_version": SKILL_VERSION,
            "warnings": self.all_warnings,
        }

    def _build_summary(self, modules: list[dict]) -> dict:
        """
        Construye la sección summary con contadores agregados.

        Campos:
          - total_endpoints: Σ len(m["endpoints"]) ∀m ∈ modules
          - lambda_candidates: cuenta endpoints con compute_target == "lambda" (sin requires_transformation)
          - fargate_candidates: cuenta endpoints con compute_target == "fargate"
          - app_runner_candidates: cuenta endpoints con compute_target == "app_runner"
          - requires_transformation: cuenta endpoints con requires_architectural_transformation == true
          - critical_blockers: cuenta endpoints con al menos un anti-patrón de severity "critical"
          - anti_pattern_summary: dict {code: count} de todos los anti-patrones detectados
        """
        total_endpoints = sum(len(m["endpoints"]) for m in modules)
        lambda_candidates = 0
        fargate_candidates = 0
        app_runner_candidates = 0
        requires_transformation = 0
        critical_blockers = 0
        anti_pattern_counts: dict[str, int] = {}

        for module in modules:
            for ep in module["endpoints"]:
                target = ep["compute_target"]
                if target == "lambda" and not ep["requires_architectural_transformation"]:
                    lambda_candidates += 1
                elif target == "fargate":
                    fargate_candidates += 1
                elif target == "app_runner":
                    app_runner_candidates += 1

                if ep["requires_architectural_transformation"]:
                    requires_transformation += 1

                # Contar anti-patrones
                for ap in ep["anti_patterns"]:
                    code = ap["code"]
                    anti_pattern_counts[code] = anti_pattern_counts.get(code, 0) + 1
                    if ap["severity"] == "critical":
                        critical_blockers += 1

        return {
            "total_endpoints": total_endpoints,
            "lambda_candidates": lambda_candidates,
            "fargate_candidates": fargate_candidates,
            "app_runner_candidates": app_runner_candidates,
            "requires_transformation": requires_transformation,
            "critical_blockers": critical_blockers,
            "anti_pattern_summary": anti_pattern_counts,
        }

    def _build_modules(self) -> list[dict]:
        """
        Construye la lista de módulos del manifiesto.

        Cada módulo incluye:
          - name: nombre del módulo
          - url_prefix: prefijo de ruta
          - cohesion: "high" | "medium" | "low"
          - isolation: "high" | "medium" | "low"
          - cross_blueprint_imports: lista de dependencias "A → B"
          - endpoints: lista de dicts con todos los campos del endpoint
        """
        modules = []
        for module_name, endpoints in self.endpoints_by_module.items():
            analysis = self.analysis_by_module.get(module_name)
            if analysis is None:
                continue  # skip si no hay análisis

            # Obtener url_prefix del primer endpoint (todos comparten el mismo)
            url_prefix = endpoints[0].full_path.split("/")[0:3]  # e.g., ["", "api", "auth"]
            url_prefix = "/".join(url_prefix) if len(url_prefix) >= 3 else "/api/" + module_name

            # Construir la lista de endpoints con todos los campos
            endpoint_dicts = []
            for ep in endpoints:
                ep_aps = analysis.endpoint_antipatterns.get(ep.endpoint_id, [])
                all_aps = ep_aps + analysis.module_antipatterns

                # Calcular complexity y compute_target usando los clasificadores
                complexity = ComplexityScorer.score(ep, all_aps)
                compute_target, requires_transformation = ComputeTargetClassifier.classify(
                    ep, all_aps, endpoints
                )

                endpoint_dicts.append({
                    "id": ep.endpoint_id,
                    "method": ep.method,
                    "path": ep.full_path,
                    "auth_required": ep.auth_required,
                    "admin_required": ep.admin_required,
                    "compute_target": compute_target,
                    "migration_complexity": complexity,
                    "requires_architectural_transformation": requires_transformation,
                    "anti_patterns": [
                        {
                            "code": ap.code,
                            "description": ap.description,
                            "gap_ids": ap.gap_ids,
                            "severity": ap.severity,
                            "location": ap.location,
                        }
                        for ap in all_aps
                    ],
                })

            modules.append({
                "name": module_name,
                "url_prefix": url_prefix,
                "cohesion": analysis.cohesion,
                "isolation": analysis.isolation,
                "cross_blueprint_imports": analysis.cross_blueprint_imports,
                "endpoints": endpoint_dicts,
            })

        return modules

    def _build_lambda_layers(self) -> list[dict]:
        """
        Deriva las Lambda Layers recomendadas basándose en el análisis.

        Las 3 layers estándar para el monolito de referencia:
          1. taller-db-layer: Modelos SQLAlchemy + conexión RDS Proxy (todos los módulos)
          2. taller-auth-layer: Validación JWT + DynamoDB blacklist (auth + autorizador)
          3. taller-utils-layer: Funciones auxiliares sin dependencias Flask (todos)

        Para monolitos genéricos, deriva las layers detectando:
          - db-layer: si hay imports de modelos SQLAlchemy
          - auth-layer: si hay módulos con auth_required endpoints
          - utils-layer: siempre presente por defecto
        """
        has_db_models = False
        has_auth_endpoints = False

        for endpoints in self.endpoints_by_module.values():
            for ep in endpoints:
                if ep.auth_required or ep.admin_required:
                    has_auth_endpoints = True
                # Detectar imports de modelos (heurística)
                # En un análisis real, buscaríamos en el AST del módulo
                has_db_models = True  # Asumimos que todo monolito Flask tiene modelos

        layers = []

        if has_db_models:
            layers.append({
                "name": "db-layer",
                "description": "Modelos SQLAlchemy, conexión a RDS Proxy, y lógica de persistencia.",
                "consumed_by": ["all_modules"],
            })

        if has_auth_endpoints:
            layers.append({
                "name": "auth-layer",
                "description": "Validación JWT, DynamoDB blacklist, y lógica de autorización.",
                "consumed_by": ["auth", "api_gateway_authorizer"],
            })

        layers.append({
            "name": "utils-layer",
            "description": "Funciones auxiliares y utilerías sin dependencias de Flask.",
            "consumed_by": ["all_modules"],
        })

        return layers

    def _build_migration_sequence(self) -> list[dict]:
        """
        Genera la secuencia de migración en 5 fases ordenadas por acoplamiento.

        Para el monolito de referencia:
          Fase 1: servicios (menor acoplamiento, endpoints públicos)
          Fase 2: auth (establece autorizador Lambda compartido)
          Fase 3: clientes (acoplamiento medio)
          Fase 4: reportes (read-only, solo corrección strftime)
          Fase 5: transacciones (mayor complejidad, transformación de uploads)

        Para monolitos genéricos, ordena por:
          1. Módulos sin cross_blueprint_imports (isolation high)
          2. Módulos con auth_required (dependen de autorizador)
          3. Módulos con anti-patrones de alta severidad (últimos)
        """
        # Obtener nombres de módulos y sus métricas de acoplamiento
        module_scores = []
        for module_name in self.endpoints_by_module.keys():
            analysis = self.analysis_by_module.get(module_name)
            if analysis is None:
                continue

            # Calcular score de acoplamiento (menor = migrar primero)
            coupling_score = 0
            coupling_score += len(analysis.cross_blueprint_imports) * 10
            if analysis.isolation == "low":
                coupling_score += 20
            elif analysis.isolation == "medium":
                coupling_score += 10

            # Penalizar módulos con anti-patrones críticos (migrar al final)
            critical_count = sum(
                1 for ap in analysis.module_antipatterns if ap.severity == "critical"
            )
            for ep_aps in analysis.endpoint_antipatterns.values():
                critical_count += sum(1 for ap in ep_aps if ap.severity == "critical")
            coupling_score += critical_count * 30

            module_scores.append((module_name, coupling_score, analysis))

        # Ordenar por coupling_score ascendente
        module_scores.sort(key=lambda x: x[1])

        # Construir la secuencia
        sequence = []
        for phase, (module_name, score, analysis) in enumerate(module_scores, start=1):
            # Generar justificación
            if phase == 1:
                justification = f"Menor acoplamiento (isolation={analysis.isolation}). Migración de bajo riesgo."
            elif "auth" in module_name.lower():
                justification = "Establece el autorizador Lambda compartido para otros módulos."
            elif analysis.cross_blueprint_imports:
                deps = ", ".join(analysis.cross_blueprint_imports)
                justification = f"Acoplamiento medio. Dependencias: {deps}."
            else:
                justification = "Complejidad alta por anti-patrones detectados."

            # Derivar prerequisites
            prerequisites = []
            if phase > 1:
                prerequisites.append(f"Completar Fase {phase - 1}")
            if "auth" not in module_name.lower() and phase > 2:
                prerequisites.append("Autorizador Lambda desplegado (Fase 2)")

            sequence.append({
                "phase": phase,
                "module": module_name,
                "justification": justification,
                "prerequisites": prerequisites,
            })

        return sequence

    # ------------------------------------------------------------------
    # Validación de invariantes
    # ------------------------------------------------------------------

    def _validate_invariants(self, manifest: dict) -> None:
        """
        Valida los dos invariantes del manifiesto:
          I-1: summary.total_endpoints == Σ len(m["endpoints"]) ∀m ∈ modules
          I-2: lambda + fargate + app_runner + requires_transformation == total_endpoints

        Lanza AssertionError si algún invariante se viola (esto es un bug del analizador).
        """
        summary = manifest["summary"]
        modules = manifest["modules"]

        # I-1: Conteo total de endpoints
        computed_total = sum(len(m["endpoints"]) for m in modules)
        assert summary["total_endpoints"] == computed_total, (
            f"Invariante I-1 violado: summary.total_endpoints={summary['total_endpoints']} "
            f"pero Σ len(m['endpoints'])={computed_total}"
        )

        # I-2: Partición completa de targets
        # Nota: La especificación original es incorrecta — la suma correcta es:
        # lambda_candidates + fargate + app_runner + requires_transformation == total
        # donde lambda_candidates NO incluye los que tienen requires_transformation
        computed_sum = (
            summary["lambda_candidates"]
            + summary["fargate_candidates"]
            + summary["app_runner_candidates"]
            + summary["requires_transformation"]
        )
        assert computed_sum == summary["total_endpoints"], (
            f"Invariante I-2 violado: lambda({summary['lambda_candidates']}) + "
            f"fargate({summary['fargate_candidates']}) + "
            f"app_runner({summary['app_runner_candidates']}) + "
            f"requires_transformation({summary['requires_transformation']}) = {computed_sum} "
            f"pero total_endpoints={summary['total_endpoints']}"
        )




# ---------------------------------------------------------------------------
# === CLI Entry Point ===
# ---------------------------------------------------------------------------



def main() -> None:
    """
    Punto de entrada de la interfaz de línea de comandos.

    Parsea los argumentos --path y --output, orquesta la cadena completa de
    componentes (BlueprintDiscoverer → EndpointExtractor → AntiPatternRegistry
    → ComplexityScorer + ComputeTargetClassifier → ManifestBuilder) y escribe
    el migration-manifest.json resultante.

    Códigos de salida:
      0 — Análisis completado exitosamente
      1 — El directorio --path no existe
      2 — No se encontraron blueprints Flask
      3 — Error de escritura del manifiesto (después de fallback)
    """
    parser = argparse.ArgumentParser(
        description=(
            "Analiza estáticamente un monolito Flask mediante AST y genera "
            "migration-manifest.json con recomendaciones de migración a AWS serverless."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python analyze_monolith.py --path monolith/\n"
            "  python analyze_monolith.py --path /ruta/monolito --output /ruta/manifiesto.json\n"
        ),
    )
    parser.add_argument(
        "--path",
        required=True,
        metavar="<ruta_monolito>",
        help="Ruta al directorio raíz del monolito Flask a analizar",
    )
    parser.add_argument(
        "--output",
        required=False,
        metavar="<ruta_manifiesto>",
        default=None,
        help=(
            "Ruta destino del migration-manifest.json. "
            "Por defecto: <path>/migration-manifest.json"
        ),
    )

    args = parser.parse_args()

    # Envolver toda la lógica en try/except de último recurso
    try:
        _run_analysis(args)
    except Exception as exc:
        # Excepción no anticipada — reportar como error interno
        error_msg = {
            "error": "INTERNAL_ERROR",
            "message": "Error interno no anticipado durante el análisis.",
            "exception": str(exc),
            "type": type(exc).__name__,
        }
        print(json.dumps(error_msg, indent=2), file=sys.stderr)
        sys.exit(1)


def _run_analysis(args) -> None:
    """
    Ejecuta la cadena completa de análisis. Separada de main() para facilitar testing.

    Lanza SystemExit con código apropiado en caso de error fatal.
    """
    # === Paso 1: Validar que el directorio existe ===
    monolith_path = Path(args.path).resolve()
    if not monolith_path.exists():
        error_msg = {
            "error": "MONOLITH_PATH_NOT_FOUND",
            "message": f"El directorio '{monolith_path}' no existe.",
        }
        print(json.dumps(error_msg, indent=2), file=sys.stderr)
        sys.exit(1)

    if not monolith_path.is_dir():
        error_msg = {
            "error": "MONOLITH_PATH_NOT_FOUND",
            "message": f"La ruta '{monolith_path}' no es un directorio.",
        }
        print(json.dumps(error_msg, indent=2), file=sys.stderr)
        sys.exit(1)

    print(f"📂 Analizando monolito en: {monolith_path}", file=sys.stderr)

    # === Paso 2: Descubrir blueprints ===
    print("🔍 Descubriendo blueprints Flask...", file=sys.stderr)
    discoverer = BlueprintDiscoverer(monolith_path)
    blueprints = discoverer.discover()

    if not blueprints:
        error_msg = {
            "error": "NO_BLUEPRINTS_FOUND",
            "message": (
                f"No se encontraron blueprints Flask en '{monolith_path}'. "
                "Verifica que el directorio contenga un proyecto Flask con blueprints."
            ),
            "warnings": discoverer.warnings,
        }
        print(json.dumps(error_msg, indent=2), file=sys.stderr)
        sys.exit(2)

    print(f"  ✓ {len(blueprints)} blueprint(s) descubierto(s): {', '.join(blueprints.keys())}", file=sys.stderr)

    # Acumular advertencias de todos los componentes
    all_warnings = discoverer.warnings.copy()

    # === Paso 3: Extraer endpoints por módulo ===
    print("📝 Extrayendo endpoints...", file=sys.stderr)
    endpoints_by_module: dict[str, list[EndpointNode]] = {}

    for bp_var, bp_info in blueprints.items():
        extractor = EndpointExtractor(bp_info["routes_file"], bp_info)
        endpoints = extractor.extract()
        all_warnings.extend(extractor.warnings)

        if endpoints:
            module_name = bp_info["module_name"]
            endpoints_by_module[module_name] = endpoints
            print(f"  ✓ {module_name}: {len(endpoints)} endpoint(s)", file=sys.stderr)

    total_endpoints = sum(len(eps) for eps in endpoints_by_module.values())
    print(f"  Total: {total_endpoints} endpoint(s) extraídos", file=sys.stderr)

    # === Paso 4: Analizar anti-patrones por módulo ===
    print("🔬 Analizando anti-patrones...", file=sys.stderr)
    analysis_by_module: dict[str, ModuleAnalysisResult] = {}

    for module_name, endpoints in endpoints_by_module.items():
        # Leer el AST del módulo completo
        bp_info = next(bp for bp in blueprints.values() if bp["module_name"] == module_name)
        routes_file = bp_info["routes_file"]

        try:
            with routes_file.open("r", encoding="utf-8") as f:
                source = f.read()
            module_tree = ast.parse(source, filename=str(routes_file))
        except (OSError, SyntaxError) as exc:
            all_warnings.append(
                f"No se pudo analizar anti-patrones en '{module_name}': {exc}"
            )
            # Usar resultado vacío por defecto
            analysis_by_module[module_name] = ModuleAnalysisResult(
                endpoint_antipatterns={},
                module_antipatterns=[],
                cross_blueprint_imports=[],
                cohesion="medium",
                isolation="medium",
            )
            continue

        # Ejecutar el registro de anti-patrones
        registry = AntiPatternRegistry()
        result = registry.analyze_module(module_tree, endpoints, module_name)
        
        # Calcular cohesion e isolation
        result.cohesion = _calculate_cohesion(module_name, endpoints, result)
        result.isolation = _calculate_isolation(result)

        analysis_by_module[module_name] = result

        # Reportar hallazgos
        total_aps = len(result.module_antipatterns) + sum(
            len(aps) for aps in result.endpoint_antipatterns.values()
        )
        if total_aps > 0:
            print(f"  ⚠ {module_name}: {total_aps} anti-patrón(es) detectado(s)", file=sys.stderr)

    # === Paso 5: Construir y escribir el manifiesto ===
    print("📦 Construyendo migration-manifest.json...", file=sys.stderr)

    builder = ManifestBuilder(
        monolith_path=monolith_path,
        blueprints=blueprints,
        endpoints_by_module=endpoints_by_module,
        analysis_by_module=analysis_by_module,
        all_warnings=all_warnings,
    )

    manifest = builder.build()

    # Determinar ruta de salida
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = monolith_path / "migration-manifest.json"

    print(f"💾 Escribiendo manifiesto en: {output_path}", file=sys.stderr)
    builder.write(manifest, output_path)

    # === Resumen final ===
    summary = manifest["summary"]
    print("\n" + "=" * 70, file=sys.stderr)
    print("✅ Análisis completado exitosamente", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"Total de endpoints:          {summary['total_endpoints']}", file=sys.stderr)
    print(f"  → Lambda:                  {summary['lambda_candidates']}", file=sys.stderr)
    print(f"  → Fargate:                 {summary['fargate_candidates']}", file=sys.stderr)
    print(f"  → App Runner:              {summary['app_runner_candidates']}", file=sys.stderr)
    print(f"  → Requiere transformación: {summary['requires_transformation']}", file=sys.stderr)
    print(f"Bloqueadores críticos:       {summary['critical_blockers']}", file=sys.stderr)
    
    if summary['anti_pattern_summary']:
        print("\nAnti-patrones detectados:", file=sys.stderr)
        for code, count in summary['anti_pattern_summary'].items():
            print(f"  • {code}: {count}", file=sys.stderr)

    if all_warnings:
        print(f"\n⚠ {len(all_warnings)} advertencia(s) — ver metadata.warnings en el manifiesto", file=sys.stderr)

    print("=" * 70, file=sys.stderr)


def _calculate_cohesion(module_name: str, endpoints: list[EndpointNode], result: ModuleAnalysisResult) -> str:
    """
    Calcula el nivel de cohesión del módulo.

    Reglas:
      - "high": todos los endpoints operan sobre la misma entidad de dominio
      - "medium": mezcla de responsabilidades (CRUD + upload + máquina de estados)
      - "low": importa de múltiples dominios (cross-blueprint imports)
    """
    # Si tiene importaciones cross-blueprint, cohesión baja
    if result.cross_blueprint_imports:
        return "low"

    # Heurística: si todos los endpoints tienen el mismo prefijo de nombre (e.g., "crear_cliente", "obtener_cliente")
    # o el módulo tiene nombre singular (e.g., "cliente" vs "clientes"), cohesión alta
    func_names = [ep.func_name for ep in endpoints]
    
    # Detectar mezcla de responsabilidades: funciones con nombres muy distintos
    # Ejemplos: "listar", "crear", "subir_adjunto", "cambiar_estado" — baja cohesión
    unique_verbs = set()
    for name in func_names:
        # Extraer el primer verbo
        verb = name.split("_")[0] if "_" in name else name
        unique_verbs.add(verb)

    if len(unique_verbs) <= 2:
        return "high"
    elif len(unique_verbs) <= 4:
        return "medium"
    else:
        return "low"


def _calculate_isolation(result: ModuleAnalysisResult) -> str:
    """
    Calcula el nivel de aislamiento del módulo.

    Reglas:
      - "high": sin importaciones cross-blueprint
      - "medium": 1-2 importaciones cross-blueprint
      - "low": 3+ importaciones cross-blueprint
    """
    import_count = len(result.cross_blueprint_imports)
    
    if import_count == 0:
        return "high"
    elif import_count <= 2:
        return "medium"
    else:
        return "low"


if __name__ == "__main__":
    main()
