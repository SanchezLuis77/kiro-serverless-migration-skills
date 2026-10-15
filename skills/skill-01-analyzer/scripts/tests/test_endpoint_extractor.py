"""
test_endpoint_extractor.py — Pruebas unitarias para EndpointExtractor

Tarea 3.2: Verificar que EndpointExtractor extrae correctamente los endpoints
de los blueprints del monolito de referencia, comprobando:
  - Métodos HTTP y rutas completas (con conversión de parámetros Flask)
  - Flags auth_required y admin_required
  - Múltiples métodos por decorador → múltiples EndpointNode
  - Tolerancia a errores de sintaxis y archivos inexistentes
  - Independencia entre funciones de ruta del mismo archivo

Requisitos validados: 1.2, 1.3, 1.4, 1.5, 1.7, 1.8

Proyecto: Trabajo de Grado — Maestría en Ingeniería de Software
          Pontificia Universidad Javeriana Cali
Autor:    Luis Gerardo Sánchez Ordóñez
"""

import importlib.util
import tempfile
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Carga de analyze_monolith.py mediante importlib.util (archivo standalone)
# ---------------------------------------------------------------------------
_script_path = Path(__file__).parent.parent / "analyze_monolith.py"
_spec = importlib.util.spec_from_file_location("analyze_monolith", _script_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

BlueprintDiscoverer = _mod.BlueprintDiscoverer
EndpointExtractor = _mod.EndpointExtractor
EndpointNode = _mod.EndpointNode
VALID_HTTP_METHODS = _mod.VALID_HTTP_METHODS

# ---------------------------------------------------------------------------
# Rutas al monolito de referencia
# ---------------------------------------------------------------------------
MONOLITH_PATH = Path(__file__).parents[4] / "monolith"

AUTH_ROUTES = MONOLITH_PATH / "app" / "blueprints" / "auth" / "routes.py"
TRANSACCIONES_ROUTES = MONOLITH_PATH / "app" / "blueprints" / "transacciones" / "routes.py"
REPORTES_ROUTES = MONOLITH_PATH / "app" / "blueprints" / "reportes" / "routes.py"
CLIENTES_ROUTES = MONOLITH_PATH / "app" / "blueprints" / "clientes" / "routes.py"
SERVICIOS_ROUTES = MONOLITH_PATH / "app" / "blueprints" / "servicios" / "routes.py"

# ---------------------------------------------------------------------------
# Helpers para crear BlueprintInfo sintéticos
# ---------------------------------------------------------------------------

def make_blueprint_info(prefix: str, module_name: str, routes_file: Path) -> dict:
    """Construye un dict compatible con BlueprintInfo para tests."""
    return {
        "prefix": prefix,
        "routes_file": routes_file,
        "module_name": module_name,
        "bp_variable": f"{module_name}_bp",
    }


def skip_if_no_monolith():
    """Salta el test si el monolito de referencia no está disponible."""
    if not MONOLITH_PATH.is_dir():
        pytest.skip(
            f"Monolito de referencia no encontrado en '{MONOLITH_PATH}'. "
            "Omitiendo test."
        )


# ===========================================================================
# Bloque 1 — Tests sobre auth/routes.py del monolito de referencia
# ===========================================================================

@pytest.fixture(scope="module")
def auth_endpoints():
    """Extrae los endpoints del blueprint auth del monolito de referencia."""
    skip_if_no_monolith()
    info = make_blueprint_info("/api/auth", "auth", AUTH_ROUTES)
    extractor = EndpointExtractor(AUTH_ROUTES, info)
    endpoints = extractor.extract()
    return endpoints, extractor.warnings


class TestAuthBlueprint:
    """
    Verifica los 5 endpoints de auth con sus métodos HTTP, rutas completas
    y flags auth_required/admin_required correctos.

    Validates: Requirements 1.2, 1.3, 1.4, 1.5
    """

    def test_exactly_5_endpoints(self, auth_endpoints):
        """El módulo auth tiene exactamente 5 endpoints."""
        endpoints, _ = auth_endpoints
        assert len(endpoints) == 5, (
            f"Se esperaban 5 endpoints en auth, se encontraron {len(endpoints)}. "
            f"IDs: {[e.endpoint_id for e in endpoints]}"
        )

    def test_no_warnings(self, auth_endpoints):
        """No deben generarse advertencias al analizar auth/routes.py."""
        _, warnings = auth_endpoints
        assert warnings == [], f"Warnings inesperados: {warnings}"

    def test_register_endpoint(self, auth_endpoints):
        """POST /api/auth/register — público, sin admin."""
        endpoints, _ = auth_endpoints
        ep = next((e for e in endpoints if e.func_name == "register"), None)
        assert ep is not None, "Endpoint 'register' no encontrado"
        assert ep.method == "POST"
        assert ep.full_path == "/api/auth/register"
        assert ep.relative_path == "/register"
        assert ep.auth_required is False
        assert ep.admin_required is False
        assert ep.endpoint_id == "auth.register"
        assert ep.module_name == "auth"

    def test_login_endpoint(self, auth_endpoints):
        """POST /api/auth/login — público, sin admin."""
        endpoints, _ = auth_endpoints
        ep = next((e for e in endpoints if e.func_name == "login"), None)
        assert ep is not None, "Endpoint 'login' no encontrado"
        assert ep.method == "POST"
        assert ep.full_path == "/api/auth/login"
        assert ep.auth_required is False
        assert ep.admin_required is False

    def test_perfil_endpoint(self, auth_endpoints):
        """GET /api/auth/me — protegido por JWT, sin admin."""
        endpoints, _ = auth_endpoints
        ep = next((e for e in endpoints if e.func_name == "perfil"), None)
        assert ep is not None, "Endpoint 'perfil' no encontrado"
        assert ep.method == "GET"
        assert ep.full_path == "/api/auth/me"
        assert ep.auth_required is True
        assert ep.admin_required is False

    def test_logout_endpoint(self, auth_endpoints):
        """POST /api/auth/logout — protegido por JWT, sin admin."""
        endpoints, _ = auth_endpoints
        ep = next((e for e in endpoints if e.func_name == "logout"), None)
        assert ep is not None, "Endpoint 'logout' no encontrado"
        assert ep.method == "POST"
        assert ep.full_path == "/api/auth/logout"
        assert ep.auth_required is True
        assert ep.admin_required is False

    def test_cambiar_password_endpoint(self, auth_endpoints):
        """PUT /api/auth/password — protegido por JWT, sin admin."""
        endpoints, _ = auth_endpoints
        ep = next((e for e in endpoints if e.func_name == "cambiar_password"), None)
        assert ep is not None, "Endpoint 'cambiar_password' no encontrado"
        assert ep.method == "PUT"
        assert ep.full_path == "/api/auth/password"
        assert ep.auth_required is True
        assert ep.admin_required is False

    def test_all_methods_are_valid_http(self, auth_endpoints):
        """Todos los métodos HTTP deben pertenecer al conjunto válido. (Req 1.8)"""
        endpoints, _ = auth_endpoints
        for ep in endpoints:
            assert ep.method in VALID_HTTP_METHODS, (
                f"Método inválido '{ep.method}' en endpoint '{ep.endpoint_id}'"
            )

    def test_endpoint_ids_are_module_dot_funcname(self, auth_endpoints):
        """endpoint_id == '<module_name>.<func_name>' para todos los endpoints."""
        endpoints, _ = auth_endpoints
        for ep in endpoints:
            assert ep.endpoint_id == f"auth.{ep.func_name}", (
                f"endpoint_id incorrecto: '{ep.endpoint_id}' para función '{ep.func_name}'"
            )


# ===========================================================================
# Bloque 2 — Tests sobre transacciones/routes.py del monolito de referencia
# ===========================================================================

@pytest.fixture(scope="module")
def transacciones_endpoints():
    """Extrae los endpoints del blueprint transacciones del monolito de referencia."""
    skip_if_no_monolith()
    info = make_blueprint_info(
        "/api/transacciones", "transacciones", TRANSACCIONES_ROUTES
    )
    extractor = EndpointExtractor(TRANSACCIONES_ROUTES, info)
    endpoints = extractor.extract()
    return endpoints, extractor.warnings


class TestTransaccionesBlueprint:
    """
    Verifica los 7 endpoints de transacciones, con énfasis en:
    - Conversión de parámetros Flask <int:var> → {var}
    - Detección de admin_required en cancelar_orden

    Validates: Requirements 1.2, 1.3, 1.4
    """

    def test_exactly_7_endpoints(self, transacciones_endpoints):
        """El módulo transacciones tiene exactamente 7 endpoints."""
        endpoints, _ = transacciones_endpoints
        assert len(endpoints) == 7, (
            f"Se esperaban 7 endpoints en transacciones, se encontraron {len(endpoints)}. "
            f"IDs: {[e.endpoint_id for e in endpoints]}"
        )

    def test_subir_adjunto_path_conversion(self, transacciones_endpoints):
        """
        POST /<int:orden_id>/adjunto debe convertir <int:orden_id> a {orden_id}.
        full_path = /api/transacciones/{orden_id}/adjunto
        """
        endpoints, _ = transacciones_endpoints
        ep = next((e for e in endpoints if e.func_name == "subir_adjunto"), None)
        assert ep is not None, "Endpoint 'subir_adjunto' no encontrado"
        assert ep.method == "POST"
        assert ep.full_path == "/api/transacciones/{orden_id}/adjunto", (
            f"full_path incorrecto: '{ep.full_path}'"
        )
        assert ep.relative_path == "/<int:orden_id>/adjunto"
        assert ep.auth_required is True
        assert ep.admin_required is False  # no tiene chequeo de admin

    def test_cancelar_orden_admin_required(self, transacciones_endpoints):
        """
        DELETE /<int:orden_id> — cancelar_orden tiene claims.get('rol') != 'admin'
        en su cuerpo → admin_required debe ser True.
        """
        endpoints, _ = transacciones_endpoints
        ep = next((e for e in endpoints if e.func_name == "cancelar_orden"), None)
        assert ep is not None, "Endpoint 'cancelar_orden' no encontrado"
        assert ep.method == "DELETE"
        assert ep.full_path == "/api/transacciones/{orden_id}"
        assert ep.auth_required is True
        assert ep.admin_required is True, (
            "cancelar_orden tiene chequeo de rol 'admin' → admin_required debe ser True"
        )

    def test_listar_ordenes_no_admin(self, transacciones_endpoints):
        """GET /api/transacciones/ — solo JWT, sin chequeo de admin."""
        endpoints, _ = transacciones_endpoints
        ep = next((e for e in endpoints if e.func_name == "listar_ordenes"), None)
        assert ep is not None, "Endpoint 'listar_ordenes' no encontrado"
        assert ep.method == "GET"
        assert ep.auth_required is True
        assert ep.admin_required is False

    def test_all_endpoints_have_valid_methods(self, transacciones_endpoints):
        """Todos los métodos HTTP son del conjunto válido. (Req 1.8)"""
        endpoints, _ = transacciones_endpoints
        for ep in endpoints:
            assert ep.method in VALID_HTTP_METHODS


# ===========================================================================
# Bloque 3 — Tests sobre reportes/routes.py del monolito de referencia
# ===========================================================================

@pytest.fixture(scope="module")
def reportes_endpoints():
    """Extrae los endpoints del blueprint reportes del monolito de referencia."""
    skip_if_no_monolith()
    info = make_blueprint_info("/api/reportes", "reportes", REPORTES_ROUTES)
    extractor = EndpointExtractor(REPORTES_ROUTES, info)
    endpoints = extractor.extract()
    return endpoints, extractor.warnings


class TestReportesBlueprint:
    """
    Verifica los 5 endpoints de reportes, con énfasis en:
    - Admin required para los endpoints de KPIs/ingresos/técnicos/cache
    - servicios_mas_solicitados sin admin (solo JWT)

    Validates: Requirements 1.3, 1.4
    """

    def test_exactly_5_endpoints(self, reportes_endpoints):
        """El módulo reportes tiene exactamente 5 endpoints."""
        endpoints, _ = reportes_endpoints
        assert len(endpoints) == 5, (
            f"Se esperaban 5 endpoints en reportes, se encontraron {len(endpoints)}."
        )

    def test_resumen_negocio_admin_required(self, reportes_endpoints):
        """GET /api/reportes/resumen — tiene if claims.get('rol') != 'admin' → admin_required=True."""
        endpoints, _ = reportes_endpoints
        ep = next((e for e in endpoints if e.func_name == "resumen_negocio"), None)
        assert ep is not None, "Endpoint 'resumen_negocio' no encontrado"
        assert ep.method == "GET"
        assert ep.full_path == "/api/reportes/resumen"
        assert ep.auth_required is True
        assert ep.admin_required is True

    def test_reporte_ingresos_admin_required(self, reportes_endpoints):
        """GET /api/reportes/ingresos — admin required."""
        endpoints, _ = reportes_endpoints
        ep = next((e for e in endpoints if e.func_name == "reporte_ingresos"), None)
        assert ep is not None
        assert ep.admin_required is True

    def test_reporte_tecnicos_admin_required(self, reportes_endpoints):
        """GET /api/reportes/tecnicos — admin required."""
        endpoints, _ = reportes_endpoints
        ep = next((e for e in endpoints if e.func_name == "reporte_tecnicos"), None)
        assert ep is not None
        assert ep.admin_required is True

    def test_servicios_mas_solicitados_not_admin(self, reportes_endpoints):
        """
        GET /api/reportes/servicios-top — no tiene chequeo de admin
        (cualquier usuario autenticado puede consultarlo).
        """
        endpoints, _ = reportes_endpoints
        ep = next(
            (e for e in endpoints if e.func_name == "servicios_mas_solicitados"), None
        )
        assert ep is not None, "Endpoint 'servicios_mas_solicitados' no encontrado"
        assert ep.auth_required is True
        assert ep.admin_required is False

    def test_estado_cache_admin_required(self, reportes_endpoints):
        """GET /api/reportes/estado-cache — admin required."""
        endpoints, _ = reportes_endpoints
        ep = next((e for e in endpoints if e.func_name == "estado_cache"), None)
        assert ep is not None
        assert ep.admin_required is True


# ===========================================================================
# Bloque 4 — Tests de conteo global (todos los módulos combinados)
# ===========================================================================

@pytest.fixture(scope="module")
def all_endpoints():
    """
    Extrae todos los endpoints del monolito de referencia usando
    BlueprintDiscoverer + EndpointExtractor para todos los blueprints.
    """
    skip_if_no_monolith()
    disc = BlueprintDiscoverer(MONOLITH_PATH)
    blueprints = disc.discover()
    result = {}
    for bp_var, info in blueprints.items():
        extractor = EndpointExtractor(info["routes_file"], info)
        endpoints = extractor.extract()
        result[info["module_name"]] = endpoints
    return result


class TestGlobalEndpointCount:
    """
    Verifica el conteo total de endpoints descubiertos en el monolito de referencia.

    Validates: Requirements 1.5
    """

    def test_total_29_endpoints(self, all_endpoints):
        """Total de endpoints en todos los módulos debe ser 29."""
        total = sum(len(eps) for eps in all_endpoints.values())
        assert total == 29, (
            f"Se esperaban 29 endpoints totales, se encontraron {total}. "
            f"Por módulo: { {m: len(e) for m, e in all_endpoints.items()} }"
        )

    def test_auth_has_5_endpoints(self, all_endpoints):
        assert len(all_endpoints.get("auth", [])) == 5

    def test_clientes_has_6_endpoints(self, all_endpoints):
        assert len(all_endpoints.get("clientes", [])) == 6

    def test_servicios_has_6_endpoints(self, all_endpoints):
        assert len(all_endpoints.get("servicios", [])) == 6

    def test_transacciones_has_7_endpoints(self, all_endpoints):
        assert len(all_endpoints.get("transacciones", [])) == 7

    def test_reportes_has_5_endpoints(self, all_endpoints):
        assert len(all_endpoints.get("reportes", [])) == 5


# ===========================================================================
# Bloque 5 — Tests sintéticos (sin depender del monolito de referencia)
# ===========================================================================

def _write_routes_file(directory: Path, content: str) -> Path:
    """Escribe un archivo routes.py en el directorio dado y retorna su Path."""
    routes = directory / "routes.py"
    routes.write_text(textwrap.dedent(content), encoding="utf-8")
    return routes


class TestSyntheticEndpoints:
    """
    Tests con blueprints generados sintéticamente para validar la lógica
    de extracción en casos controlados, sin depender del monolito.

    Validates: Requirements 1.2, 1.3, 1.4, 1.7, 1.8
    """

    def test_default_method_is_get(self, tmp_path):
        """
        Un decorador @bp.route('/ruta') sin keyword 'methods' debe producir
        un EndpointNode con method='GET'.
        """
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            test_bp = Blueprint('test', __name__)

            @test_bp.route('/ping')
            def ping():
                return 'pong'
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 1
        assert endpoints[0].method == "GET"
        assert endpoints[0].full_path == "/api/test/ping"

    def test_multiple_methods_produce_multiple_nodes(self, tmp_path):
        """
        methods=['GET', 'POST'] en un solo decorador → 2 EndpointNode distintos,
        uno por método. (Req 1.7)
        """
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            test_bp = Blueprint('test', __name__)

            @test_bp.route('/items', methods=['GET', 'POST'])
            def items():
                pass
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 2
        methods = {ep.method for ep in endpoints}
        assert methods == {"GET", "POST"}
        # Ambos deben apuntar a la misma ruta y función
        for ep in endpoints:
            assert ep.full_path == "/api/test/items"
            assert ep.func_name == "items"
            assert ep.endpoint_id == "test.items"

    def test_flask_path_param_conversion(self, tmp_path):
        """
        <int:item_id> en la ruta del decorador debe convertirse a {item_id}
        en full_path. (Req 1.2)
        """
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            test_bp = Blueprint('test', __name__)

            @test_bp.route('/<int:item_id>/detail', methods=['GET'])
            def detail(item_id):
                pass
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 1
        assert endpoints[0].full_path == "/api/test/{item_id}/detail"
        assert endpoints[0].relative_path == "/<int:item_id>/detail"

    def test_string_type_path_param_conversion(self, tmp_path):
        """<string:slug> debe convertirse a {slug}."""
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            test_bp = Blueprint('test', __name__)

            @test_bp.route('/<string:slug>', methods=['GET'])
            def by_slug(slug):
                pass
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 1
        assert endpoints[0].full_path == "/api/test/{slug}"

    def test_untyped_path_param_conversion(self, tmp_path):
        """<nombre> sin tipo debe convertirse a {nombre}."""
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            test_bp = Blueprint('test', __name__)

            @test_bp.route('/<nombre>', methods=['GET'])
            def by_nombre(nombre):
                pass
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 1
        assert endpoints[0].full_path == "/api/test/{nombre}"

    def test_jwt_required_decorator_sets_auth_required(self, tmp_path):
        """
        @jwt_required() en el decorator_list debe establecer auth_required=True.
        (Req 1.3)
        """
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            from flask_jwt_extended import jwt_required
            test_bp = Blueprint('test', __name__)

            @test_bp.route('/protected', methods=['GET'])
            @jwt_required()
            def protected():
                pass
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 1
        assert endpoints[0].auth_required is True

    def test_no_jwt_required_sets_auth_required_false(self, tmp_path):
        """
        Sin decorador @jwt_required, auth_required debe ser False. (Req 1.3)
        """
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            test_bp = Blueprint('test', __name__)

            @test_bp.route('/public', methods=['GET'])
            def public_endpoint():
                pass
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 1
        assert endpoints[0].auth_required is False

    def test_admin_required_via_claims_get_rol(self, tmp_path):
        """
        claims.get('rol') != 'admin' en el cuerpo debe establecer
        admin_required=True. (Req 1.4)
        """
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            from flask_jwt_extended import jwt_required, get_jwt
            test_bp = Blueprint('test', __name__)

            @test_bp.route('/admin-only', methods=['GET'])
            @jwt_required()
            def admin_only():
                claims = get_jwt()
                if claims.get('rol') != 'admin':
                    return 'forbidden', 403
                return 'ok'
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 1
        assert endpoints[0].admin_required is True

    def test_admin_required_via_get_jwt_subscript(self, tmp_path):
        """
        get_jwt()['rol'] != 'admin' en el cuerpo debe establecer
        admin_required=True. (Req 1.4)
        """
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            from flask_jwt_extended import jwt_required, get_jwt
            test_bp = Blueprint('test', __name__)

            @test_bp.route('/admin2', methods=['POST'])
            @jwt_required()
            def admin2():
                if get_jwt()['rol'] != 'admin':
                    return 'no', 403
                return 'yes'
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 1
        assert endpoints[0].admin_required is True

    def test_no_admin_check_sets_admin_required_false(self, tmp_path):
        """
        Sin chequeo de rol 'admin', admin_required debe ser False. (Req 1.4)
        """
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            from flask_jwt_extended import jwt_required
            test_bp = Blueprint('test', __name__)

            @test_bp.route('/me', methods=['GET'])
            @jwt_required()
            def me():
                return 'my profile'
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 1
        assert endpoints[0].admin_required is False

    def test_syntax_error_returns_empty_with_warning(self, tmp_path):
        """
        Un archivo con error de sintaxis no debe lanzar excepciones:
        retorna [] y registra una advertencia. (Req 5.2)
        """
        routes = tmp_path / "routes.py"
        routes.write_text("def broken(\n    # EOF sin cerrar paréntesis\n", encoding="utf-8")
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert endpoints == [], "Debe retornar lista vacía ante error de sintaxis"
        assert len(extractor.warnings) > 0, "Debe registrar advertencia"

    def test_nonexistent_file_returns_empty_with_warning(self, tmp_path):
        """
        Un archivo inexistente no debe lanzar excepciones:
        retorna [] y registra una advertencia.
        """
        routes = tmp_path / "nonexistent_routes.py"
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert endpoints == []
        assert len(extractor.warnings) > 0

    def test_file_with_no_routes_returns_empty(self, tmp_path):
        """
        Un archivo Python sin decoradores @bp.route retorna []. (Req 1.7)
        """
        routes = _write_routes_file(tmp_path, """
            # Archivo Python sin blueprints ni rutas
            def helper():
                return 42
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert endpoints == []

    def test_multiple_routes_in_same_file_independent(self, tmp_path):
        """
        Múltiples funciones de ruta en el mismo archivo son procesadas de
        forma independiente. (Req 2.9 — independencia de detección)
        """
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            from flask_jwt_extended import jwt_required, get_jwt
            test_bp = Blueprint('test', __name__)

            @test_bp.route('/public', methods=['GET'])
            def public_view():
                return 'public'

            @test_bp.route('/protected', methods=['GET'])
            @jwt_required()
            def protected_view():
                return 'protected'

            @test_bp.route('/admin', methods=['GET'])
            @jwt_required()
            def admin_view():
                claims = get_jwt()
                if claims.get('rol') != 'admin':
                    return 'no', 403
                return 'yes'
        """)
        info = make_blueprint_info("/api/test", "test", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 3

        ep_public = next(e for e in endpoints if e.func_name == "public_view")
        assert ep_public.auth_required is False
        assert ep_public.admin_required is False

        ep_protected = next(e for e in endpoints if e.func_name == "protected_view")
        assert ep_protected.auth_required is True
        assert ep_protected.admin_required is False

        ep_admin = next(e for e in endpoints if e.func_name == "admin_view")
        assert ep_admin.auth_required is True
        assert ep_admin.admin_required is True

    def test_endpoint_id_format(self, tmp_path):
        """
        endpoint_id debe tener el formato '<module_name>.<func_name>'.
        """
        routes = _write_routes_file(tmp_path, """
            from flask import Blueprint
            mymod_bp = Blueprint('mymod', __name__)

            @mymod_bp.route('/foo', methods=['POST'])
            def foo_handler():
                pass
        """)
        info = make_blueprint_info("/api/mymod", "mymod", routes)
        extractor = EndpointExtractor(routes, info)
        endpoints = extractor.extract()

        assert len(endpoints) == 1
        assert endpoints[0].endpoint_id == "mymod.foo_handler"
        assert endpoints[0].module_name == "mymod"
        assert endpoints[0].func_name == "foo_handler"
