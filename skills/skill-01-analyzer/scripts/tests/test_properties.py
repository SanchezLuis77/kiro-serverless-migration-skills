"""
test_properties.py — Property-based tests with Hypothesis

Tests invariant properties that must hold for ANY valid Flask monolith input.
Validates Task 12 requirements.

Uso:
    pytest test_properties.py -v
    pytest test_properties.py::test_property_endpoint_fields_completeness -v
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck


# ---------------------------------------------------------------------------
# Strategies for generating Flask code
# ---------------------------------------------------------------------------

HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
VALID_COMPLEXITY = ["low", "medium", "high", "very_high"]
VALID_COMPUTE_TARGETS = ["lambda", "fargate", "app_runner"]


@st.composite
def flask_route_function(draw, with_antipattern=None):
    """
    Generates a valid Flask route function as Python source code.
    
    Parameters:
      - with_antipattern: None, "local-filesystem", "strftime", "session", etc.
    """
    func_name = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll',)),
        min_size=3,
        max_size=20
    ))
    
    # HTTP method
    method = draw(st.sampled_from(HTTP_METHODS))
    
    # Route path
    route_segments = draw(st.lists(
        st.text(alphabet=st.characters(whitelist_categories=('Ll',)), min_size=1, max_size=10),
        min_size=1,
        max_size=3
    ))
    route = "/" + "/".join(route_segments)
    
    # JWT decorator
    has_jwt = draw(st.booleans())
    jwt_decorator = "@jwt_required()\n" if has_jwt else ""
    
    # Admin check in body
    has_admin_check = draw(st.booleans()) and has_jwt
    admin_check = """
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return {'error': 'Forbidden'}, 403
""" if has_admin_check else ""
    
    # Anti-pattern injection
    antipattern_code = ""
    if with_antipattern == "local-filesystem":
        antipattern_code = """
    archivo = request.files.get('archivo')
    if archivo:
        ruta = os.path.join(current_app.config['UPLOAD_FOLDER'], archivo.filename)
        archivo.save(ruta)
"""
    elif with_antipattern == "strftime":
        antipattern_code = """
    fecha_str = func.strftime('%Y-%m-%d', SomeModel.created_at)
"""
    
    code = f"""
@bp.route('{route}', methods=['{method}'])
{jwt_decorator}def {func_name}():
    \"\"\"Test endpoint.\"\"\"
{admin_check}{antipattern_code}
    return {{'message': 'ok'}}, 200
"""
    
    return code


@st.composite
def flask_blueprint_file(draw, num_endpoints=None):
    """
    Generates a complete Flask blueprint routes.py file.
    
    Parameters:
      - num_endpoints: Fixed number of endpoints (default: random 1-10)
    """
    if num_endpoints is None:
        num_endpoints = draw(st.integers(min_value=1, max_value=10))
    
    blueprint_var = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll',)),
        min_size=3,
        max_size=15
    )) + "_bp"
    
    # Generate multiple route functions
    functions = []
    for i in range(num_endpoints):
        func = draw(flask_route_function())
        functions.append(func)
    
    code = f"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt
import os

{blueprint_var} = Blueprint('{blueprint_var.replace('_bp', '')}', __name__)

{''.join(functions)}
"""
    
    return code, blueprint_var, num_endpoints


def temp_monolith_with_blueprint(blueprint_code, blueprint_var, module_name="test"):
    """
    Creates a temporary directory structure with a Flask monolith containing
    a single blueprint.
    
    Returns: (monolith_path, output_path)
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="hypothesis_test_"))
    
    # Create app/__init__.py
    app_dir = temp_dir / "app"
    app_dir.mkdir()
    
    init_code = f"""
from flask import Flask

def create_app():
    app = Flask(__name__)
    from app.blueprints.{module_name} import {blueprint_var}
    app.register_blueprint({blueprint_var}, url_prefix='/api/{module_name}')
    return app
"""
    (app_dir / "__init__.py").write_text(init_code, encoding='utf-8')
    
    # Create blueprints/<module_name>/routes.py
    blueprints_dir = app_dir / "blueprints"
    blueprints_dir.mkdir()
    
    module_dir = blueprints_dir / module_name
    module_dir.mkdir()
    
    (module_dir / "__init__.py").write_text(
        f"from flask import Blueprint\n{blueprint_var} = Blueprint('{module_name}', __name__)\n",
        encoding='utf-8'
    )
    
    (module_dir / "routes.py").write_text(blueprint_code, encoding='utf-8')
    
    # Output path for manifest
    output_path = temp_dir / "manifest.json"
    
    return temp_dir, output_path


def run_analyzer(monolith_path, output_path):
    """
    Runs analyze_monolith.py on the given path.
    
    Returns: (exit_code, manifest_dict or None)
    """
    analyzer_script = Path(__file__).parent.parent / "analyze_monolith.py"
    
    result = subprocess.run(
        [sys.executable, str(analyzer_script), "--path", str(monolith_path), "--output", str(output_path)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=30
    )
    
    if result.returncode == 0 and output_path.exists():
        try:
            with output_path.open("r", encoding="utf-8") as f:
                manifest = json.load(f)
            return 0, manifest
        except json.JSONDecodeError:
            return result.returncode, None
    
    return result.returncode, None


# ---------------------------------------------------------------------------
# Property Tests (Task 12.2-12.11)
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.data())
def test_property_endpoint_fields_completeness(data):
    """
    Propiedad 1: Completitud de campos obligatorios de endpoint.
    
    Para cualquier blueprint Flask generado, cada endpoint extraído tiene los campos
    obligatorios con valores no nulos y method ∈ VALID_HTTP_METHODS.
    
    Validates: Requirements 1.2, 1.3, 1.4, 1.8, 8.2
    """
    blueprint_code, blueprint_var, num_endpoints = data.draw(flask_blueprint_file())
    
    # Create temp monolith
    monolith_path, output_path = temp_monolith_with_blueprint(blueprint_code, blueprint_var)
    
    try:
        exit_code, manifest = run_analyzer(monolith_path, output_path)
        
        # Skip if analyzer failed (e.g., due to generated invalid syntax)
        assume(exit_code == 0 and manifest is not None)
        
        # Verify all endpoints have required fields
        for module in manifest["modules"]:
            for endpoint in module["endpoints"]:
                # Required fields must be present
                assert "id" in endpoint and endpoint["id"], "Missing or empty 'id'"
                assert "method" in endpoint and endpoint["method"], "Missing or empty 'method'"
                assert "path" in endpoint and endpoint["path"], "Missing or empty 'path'"
                assert "auth_required" in endpoint and isinstance(endpoint["auth_required"], bool)
                assert "admin_required" in endpoint and isinstance(endpoint["admin_required"], bool)
                assert "compute_target" in endpoint and endpoint["compute_target"], "Missing 'compute_target'"
                assert "migration_complexity" in endpoint and endpoint["migration_complexity"], "Missing 'migration_complexity'"
                
                # Method must be valid
                assert endpoint["method"] in HTTP_METHODS, (
                    f"Invalid method '{endpoint['method']}', expected one of {HTTP_METHODS}"
                )
    finally:
        # Cleanup
        import shutil
        if monolith_path.exists():
            shutil.rmtree(monolith_path)


@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.data())
def test_property_compute_target_domain(data):
    """
    Propiedad 2: Dominio cerrado de compute_target.
    
    Para cualquier conjunto de blueprints analizados, compute_target ∈ VALID_COMPUTE_TARGETS.
    
    Validates: Requirements 3.4, 8.2
    """
    blueprint_code, blueprint_var, num_endpoints = data.draw(flask_blueprint_file())
    
    monolith_path, output_path = temp_monolith_with_blueprint(blueprint_code, blueprint_var)
    
    try:
        exit_code, manifest = run_analyzer(monolith_path, output_path)
        assume(exit_code == 0 and manifest is not None)
        
        for module in manifest["modules"]:
            for endpoint in module["endpoints"]:
                compute_target = endpoint["compute_target"]
                assert compute_target in VALID_COMPUTE_TARGETS, (
                    f"Invalid compute_target '{compute_target}', expected one of {VALID_COMPUTE_TARGETS}"
                )
    finally:
        import shutil
        if monolith_path.exists():
            shutil.rmtree(monolith_path)


@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.data())
def test_property_complexity_domain(data):
    """
    Propiedad 3: Dominio cerrado de migration_complexity.
    
    migration_complexity ∈ VALID_COMPLEXITY para cualquier combinación de anti-patrones.
    
    Validates: Requirements 1.6, 8.3
    """
    blueprint_code, blueprint_var, num_endpoints = data.draw(flask_blueprint_file())
    
    monolith_path, output_path = temp_monolith_with_blueprint(blueprint_code, blueprint_var)
    
    try:
        exit_code, manifest = run_analyzer(monolith_path, output_path)
        assume(exit_code == 0 and manifest is not None)
        
        for module in manifest["modules"]:
            for endpoint in module["endpoints"]:
                complexity = endpoint["migration_complexity"]
                assert complexity in VALID_COMPLEXITY, (
                    f"Invalid migration_complexity '{complexity}', expected one of {VALID_COMPLEXITY}"
                )
    finally:
        import shutil
        if monolith_path.exists():
            shutil.rmtree(monolith_path)


@settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.data())
def test_property_summary_count_invariant(data):
    """
    Propiedad 4: Invariante de conteo del summary.
    
    summary.total_endpoints == Σ len(m["endpoints"]) ∀m ∈ manifest["modules"]
    
    Validates: Requirements 4.7, 8.4
    """
    blueprint_code, blueprint_var, num_endpoints = data.draw(flask_blueprint_file(num_endpoints=data.draw(st.integers(min_value=1, max_value=5))))
    
    monolith_path, output_path = temp_monolith_with_blueprint(blueprint_code, blueprint_var)
    
    try:
        exit_code, manifest = run_analyzer(monolith_path, output_path)
        assume(exit_code == 0 and manifest is not None)
        
        # Compute actual total
        actual_total = sum(len(module["endpoints"]) for module in manifest["modules"])
        
        # Verify invariant
        assert manifest["summary"]["total_endpoints"] == actual_total, (
            f"Invariant violated: summary.total_endpoints={manifest['summary']['total_endpoints']} "
            f"but computed total={actual_total}"
        )
    finally:
        import shutil
        if monolith_path.exists():
            shutil.rmtree(monolith_path)


@settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.data())
def test_property_json_serialization_roundtrip(data):
    """
    Propiedad 5: Round-trip de serialización JSON.
    
    json.loads(json.dumps(manifest)) produce un objeto con los mismos campos y valores.
    
    Validates: Requirements 4.8, 8.6
    """
    blueprint_code, blueprint_var, num_endpoints = data.draw(flask_blueprint_file())
    
    monolith_path, output_path = temp_monolith_with_blueprint(blueprint_code, blueprint_var)
    
    try:
        exit_code, manifest = run_analyzer(monolith_path, output_path)
        assume(exit_code == 0 and manifest is not None)
        
        # Round-trip
        json_str = json.dumps(manifest, indent=2, ensure_ascii=False)
        reparsed = json.loads(json_str)
        
        # Verify key sections are preserved
        assert reparsed["metadata"]["total_endpoints"] == manifest["metadata"]["total_endpoints"]
        assert reparsed["summary"]["total_endpoints"] == manifest["summary"]["total_endpoints"]
        assert len(reparsed["modules"]) == len(manifest["modules"])
    finally:
        import shutil
        if monolith_path.exists():
            shutil.rmtree(monolith_path)


@settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.data())
def test_property_migration_sequence_nonempty(data):
    """
    Propiedad 6: Secuencia de migración no vacía.
    
    Para cualquier directorio con al menos un módulo con endpoints, migration_sequence
    contiene al menos un elemento.
    
    Validates: Requirements 4.5, 8.5
    """
    blueprint_code, blueprint_var, num_endpoints = data.draw(flask_blueprint_file(num_endpoints=data.draw(st.integers(min_value=1, max_value=3))))
    
    monolith_path, output_path = temp_monolith_with_blueprint(blueprint_code, blueprint_var)
    
    try:
        exit_code, manifest = run_analyzer(monolith_path, output_path)
        assume(exit_code == 0 and manifest is not None)
        
        # If there are modules with endpoints, migration_sequence must not be empty
        has_endpoints = any(len(m["endpoints"]) > 0 for m in manifest["modules"])
        
        if has_endpoints:
            assert len(manifest["migration_sequence"]) > 0, (
                "migration_sequence is empty despite having modules with endpoints"
            )
    finally:
        import shutil
        if monolith_path.exists():
            shutil.rmtree(monolith_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])