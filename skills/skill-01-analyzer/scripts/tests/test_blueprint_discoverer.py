"""
test_blueprint_discoverer.py — Pruebas unitarias para BlueprintDiscoverer

Tarea 2.2: Verificar que BlueprintDiscoverer descubre correctamente los
5 blueprints del monolito de referencia (auth, clientes, servicios,
transacciones, reportes) con sus url_prefix, nombres de módulo y archivos
routes.py existentes.

Requisitos validados: 1.1 (recorrido recursivo), 1.5 (exactamente 5 blueprints)

Proyecto: Trabajo de Grado — Maestría en Ingeniería de Software
          Pontificia Universidad Javeriana Cali
Autor:    Luis Gerardo Sánchez Ordóñez
"""

import sys
import tempfile
import importlib.util
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
BlueprintInfo = _mod.BlueprintInfo

# ---------------------------------------------------------------------------
# Constante de ruta al monolito de referencia
# ---------------------------------------------------------------------------
# __file__ está en skills/skill-01-analyzer/scripts/tests/
# parents[4] = workspace root (kiro-serverless-migration-skills/), luego entrar a monolith/
MONOLITH_PATH = Path(__file__).parents[4] / "monolith"

# Blueprints esperados: {variable_name: (url_prefix, module_name)}
EXPECTED_BLUEPRINTS = {
    "auth_bp":         ("/api/auth",         "auth"),
    "clientes_bp":     ("/api/clientes",     "clientes"),
    "servicios_bp":    ("/api/servicios",    "servicios"),
    "transacciones_bp": ("/api/transacciones", "transacciones"),
    "reportes_bp":     ("/api/reportes",     "reportes"),
}


# ---------------------------------------------------------------------------
# Fixture compartida: resultado de discover() sobre el monolito de referencia
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def discovery_result():
    """
    Ejecuta BlueprintDiscoverer.discover() una sola vez contra el monolito de
    referencia y devuelve (discoverer, result) para reutilización entre tests.
    """
    if not MONOLITH_PATH.is_dir():
        pytest.skip(
            f"Monolito de referencia no encontrado en '{MONOLITH_PATH}'. "
            "Omitiendo tests que dependen del monolito."
        )
    discoverer = BlueprintDiscoverer(MONOLITH_PATH)
    result = discoverer.discover()
    return discoverer, result


# ---------------------------------------------------------------------------
# Test 1: Exactamente 5 blueprints descubiertos sin advertencias
# ---------------------------------------------------------------------------

def test_discovers_exactly_5_blueprints(discovery_result):
    """
    Verifica que BlueprintDiscoverer descubre exactamente 5 blueprints en el
    monolito de referencia y que no se generan advertencias durante el proceso.

    Validates: Requirements 1.1, 1.5
    """
    discoverer, result = discovery_result

    assert len(result) == 5, (
        f"Se esperaban 5 blueprints, se encontraron {len(result)}. "
        f"Blueprints hallados: {list(result.keys())}"
    )
    assert discoverer.warnings == [], (
        f"Se esperaban 0 advertencias, se encontraron {len(discoverer.warnings)}. "
        f"Advertencias: {discoverer.warnings}"
    )


# ---------------------------------------------------------------------------
# Test 2: Variables de blueprint y sus url_prefix correctos
# ---------------------------------------------------------------------------

def test_blueprint_variables_and_prefixes(discovery_result):
    """
    Verifica que cada variable de blueprint mapea exactamente al url_prefix
    esperado según el registro en app/__init__.py del monolito de referencia.

    Validates: Requirements 1.1, 1.5
    """
    _, result = discovery_result

    for bp_var, (expected_prefix, _) in EXPECTED_BLUEPRINTS.items():
        assert bp_var in result, (
            f"La variable de blueprint '{bp_var}' no fue descubierta. "
            f"Blueprints disponibles: {list(result.keys())}"
        )
        actual_prefix = result[bp_var]["prefix"]
        assert actual_prefix == expected_prefix, (
            f"Para '{bp_var}': se esperaba prefix='{expected_prefix}', "
            f"se obtuvo '{actual_prefix}'"
        )


# ---------------------------------------------------------------------------
# Test 3: Nombres de módulo inferidos correctamente
# ---------------------------------------------------------------------------

def test_module_names_inferred_correctly(discovery_result):
    """
    Verifica que el module_name de cada blueprint se infiere correctamente
    a partir del directorio padre del archivo routes.py descubierto.

    Validates: Requirements 1.1
    """
    _, result = discovery_result

    for bp_var, (_, expected_module_name) in EXPECTED_BLUEPRINTS.items():
        assert bp_var in result, (
            f"La variable de blueprint '{bp_var}' no fue descubierta."
        )
        actual_module_name = result[bp_var]["module_name"]
        assert actual_module_name == expected_module_name, (
            f"Para '{bp_var}': se esperaba module_name='{expected_module_name}', "
            f"se obtuvo '{actual_module_name}'"
        )


# ---------------------------------------------------------------------------
# Test 4: Los archivos routes.py existen en el sistema de archivos
# ---------------------------------------------------------------------------

def test_routes_files_exist(discovery_result):
    """
    Verifica que cada routes_file reportado por el descubridor apunta a un
    archivo que realmente existe en el sistema de archivos.

    Validates: Requirements 1.1
    """
    _, result = discovery_result

    for bp_var, info in result.items():
        routes_file = info["routes_file"]
        assert Path(routes_file).is_file(), (
            f"El archivo routes.py reportado para '{bp_var}' no existe: "
            f"'{routes_file}'"
        )


# ---------------------------------------------------------------------------
# Test 5: Ruta inexistente devuelve dict vacío con advertencia
# ---------------------------------------------------------------------------

def test_nonexistent_path_returns_empty():
    """
    Verifica que BlueprintDiscoverer no falla cuando la ruta no existe:
    devuelve un dict vacío y registra al menos una advertencia.

    Validates: Requirements 5.4 (tolerancia a fallos, sin excepciones)
    """
    nonexistent = Path("/ruta/que/definitivamente/no/existe/en/ningun/sistema")
    discoverer = BlueprintDiscoverer(nonexistent)
    result = discoverer.discover()

    assert result == {}, (
        f"Se esperaba dict vacío para ruta inexistente, se obtuvo: {result}"
    )
    assert len(discoverer.warnings) > 0, (
        "Se esperaba al menos una advertencia para ruta inexistente, "
        "pero warnings está vacío."
    )


# ---------------------------------------------------------------------------
# Test 6: Directorio vacío devuelve dict vacío (sin lanzar excepciones)
# ---------------------------------------------------------------------------

def test_empty_directory_returns_empty():
    """
    Verifica que BlueprintDiscoverer devuelve un dict vacío para un directorio
    vacío, sin lanzar excepciones y pudiendo registrar advertencias.

    Validates: Requirements 5.4 (tolerancia a fallos, sin excepciones)
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        discoverer = BlueprintDiscoverer(Path(tmp_dir))
        result = discoverer.discover()

    assert result == {}, (
        f"Se esperaba dict vacío para directorio vacío, se obtuvo: {result}"
    )
    # Las advertencias son opcionales — solo verificamos que no se lanzaron excepciones
    assert isinstance(discoverer.warnings, list), (
        "discoverer.warnings debe ser una lista."
    )
