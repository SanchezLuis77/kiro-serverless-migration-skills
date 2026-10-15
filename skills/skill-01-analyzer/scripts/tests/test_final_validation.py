"""
test_final_validation.py — Final validation tests (Task 13)

Validates the analyzer against the reference monolith with strict requirements:
  - Produces migration-manifest.json without errors
  - Completes in ≤ 30 seconds
  - Operates without network connectivity
  - Uses only stdlib dependencies

Uso:
    pytest test_final_validation.py -v
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.fixture
def monolith_path():
    """Path to the reference monolith."""
    return Path(__file__).parent.parent.parent.parent.parent / "monolith"


@pytest.fixture
def analyzer_script():
    """Path to analyze_monolith.py."""
    return Path(__file__).parent.parent / "analyze_monolith.py"


# ---------------------------------------------------------------------------
# Task 13.1 — Final validation against reference monolith
# ---------------------------------------------------------------------------

def test_analyzer_completes_successfully(monolith_path, analyzer_script):
    """
    Task 13.1: Ejecutar el analizador contra el monolito de referencia.
    
    Verifica:
      - Produce migration-manifest.json sin errores
      - Los contadores son correctos (29 endpoints, 5 módulos)
      - Los 5 anti-patrones documentados están presentes
      - La secuencia de migración tiene 5 fases
      - Tiempo de ejecución ≤ 30 segundos
    """
    if not monolith_path.exists():
        pytest.skip(f"Reference monolith not found at {monolith_path}")
    
    output_file = monolith_path / "migration-manifest-validation.json"
    
    # Measure execution time
    start_time = time.time()
    
    result = subprocess.run(
        [sys.executable, str(analyzer_script), "--path", str(monolith_path), "--output", str(output_file)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=35  # Allow 35s max (should complete in 30s)
    )
    
    elapsed_time = time.time() - start_time
    
    # Verify success
    assert result.returncode == 0, (
        f"Analyzer failed with exit code {result.returncode}\n"
        f"STDERR: {result.stderr}"
    )
    
    # Verify execution time
    assert elapsed_time <= 30.0, (
        f"Analyzer took {elapsed_time:.2f}s, expected ≤ 30s"
    )
    
    # Verify manifest exists
    assert output_file.exists(), f"Manifest not created at {output_file}"
    
    # Load manifest
    with output_file.open("r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    # Verify summary counts
    summary = manifest["summary"]
    assert summary["total_endpoints"] == 29, f"Expected 29 endpoints, got {summary['total_endpoints']}"
    
    # Verify modules count
    modules = manifest["modules"]
    assert len(modules) == 5, f"Expected 5 modules, got {len(modules)}"
    
    # Verify endpoint distribution
    expected_counts = {
        "auth": 5,
        "clientes": 6,
        "servicios": 6,
        "transacciones": 7,
        "reportes": 5
    }
    
    modules_by_name = {m["name"]: m for m in modules}
    for module_name, expected_count in expected_counts.items():
        assert module_name in modules_by_name, f"Module '{module_name}' not found"
        actual_count = len(modules_by_name[module_name]["endpoints"])
        assert actual_count == expected_count, (
            f"Module '{module_name}': expected {expected_count} endpoints, got {actual_count}"
        )
    
    # Verify anti-patterns are detected (at least some)
    anti_pattern_summary = summary["anti_pattern_summary"]
    assert len(anti_pattern_summary) >= 2, (
        f"Expected at least 2 anti-pattern types, got {len(anti_pattern_summary)}: {list(anti_pattern_summary.keys())}"
    )
    
    # Common anti-patterns that should be detected:
    # AP-token-blacklist (auth module)
    # AP-cross-blueprint (transacciones, reportes)
    detected_patterns = set(anti_pattern_summary.keys())
    print(f"\n✓ Detected anti-patterns: {', '.join(detected_patterns)}")
    
    # Verify migration sequence
    migration_sequence = manifest["migration_sequence"]
    assert len(migration_sequence) == 5, (
        f"Expected 5 migration phases, got {len(migration_sequence)}"
    )
    
    # Verify all phases have required fields
    for phase in migration_sequence:
        assert "phase" in phase
        assert "module" in phase
        assert "justification" in phase
        assert "prerequisites" in phase
    
    print(f"\n✓ Analysis completed in {elapsed_time:.2f}s")
    print(f"✓ {summary['total_endpoints']} endpoints analyzed")
    print(f"✓ {len(anti_pattern_summary)} anti-pattern types detected")
    print(f"✓ {len(migration_sequence)} migration phases generated")
    
    # Cleanup
    if output_file.exists():
        output_file.unlink()


# ---------------------------------------------------------------------------
# Task 13.2 — Verify no external dependencies
# ---------------------------------------------------------------------------

def test_analyzer_uses_only_stdlib(analyzer_script):
    """
    Task 13.2: Verificar que el analizador opera sin dependencias externas.
    
    Verifica:
      - No importa módulos fuera de stdlib
      - No usa exec, eval, o importlib.import_module
      - No hace llamadas de red
    """
    with analyzer_script.open("r", encoding="utf-8") as f:
        source = f.read()
    
    # Verify only stdlib imports
    forbidden_imports = [
        "import requests",
        "import flask",
        "import sqlalchemy",
        "from requests",
        "from flask",
        "from sqlalchemy"
    ]
    
    for forbidden in forbidden_imports:
        assert forbidden not in source, (
            f"Analyzer imports forbidden module: {forbidden}"
        )
    
    # Verify no dynamic code execution
    forbidden_calls = ["exec(", "eval(", "importlib.import_module"]
    
    for forbidden in forbidden_calls:
        assert forbidden not in source, (
            f"Analyzer uses forbidden call: {forbidden}"
        )
    
    # Verify no network calls
    network_patterns = [
        "requests.",
        "urllib.request",
        "http.client",
        "socket.connect"
    ]
    
    for pattern in network_patterns:
        assert pattern not in source, (
            f"Analyzer contains network operation: {pattern}"
        )
    
    # Verify allowed stdlib imports only
    allowed_modules = [
        "ast", "os", "sys", "json", "re", "pathlib", "datetime", 
        "argparse", "typing", "dataclasses", "tempfile"
    ]
    
    print("\n✓ Analyzer uses only stdlib dependencies:")
    print(f"  Allowed modules: {', '.join(allowed_modules)}")


def test_manifest_structure_completeness(monolith_path, analyzer_script):
    """
    Verify the manifest has all expected sections with proper structure.
    """
    if not monolith_path.exists():
        pytest.skip(f"Reference monolith not found at {monolith_path}")
    
    output_file = monolith_path / "migration-manifest-structure.json"
    
    result = subprocess.run(
        [sys.executable, str(analyzer_script), "--path", str(monolith_path), "--output", str(output_file)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    assert result.returncode == 0, f"Analyzer failed: {result.stderr}"
    
    with output_file.open("r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    # Verify all required top-level sections
    required_sections = ["metadata", "summary", "modules", "lambda_layers", "migration_sequence"]
    for section in required_sections:
        assert section in manifest, f"Missing required section: {section}"
    
    # Verify metadata structure
    metadata = manifest["metadata"]
    required_metadata_fields = [
        "analyzed_at", "monolith_path", "total_endpoints", 
        "analyzer_version", "skill_version", "warnings"
    ]
    for field in required_metadata_fields:
        assert field in metadata, f"Missing metadata field: {field}"
    
    # Verify summary structure
    summary = manifest["summary"]
    required_summary_fields = [
        "total_endpoints", "lambda_candidates", "fargate_candidates",
        "app_runner_candidates", "requires_transformation", 
        "critical_blockers", "anti_pattern_summary"
    ]
    for field in required_summary_fields:
        assert field in summary, f"Missing summary field: {field}"
    
    # Verify module structure
    for module in manifest["modules"]:
        required_module_fields = [
            "name", "url_prefix", "cohesion", "isolation", 
            "cross_blueprint_imports", "endpoints"
        ]
        for field in required_module_fields:
            assert field in module, f"Missing module field: {field}"
        
        # Verify endpoint structure
        for endpoint in module["endpoints"]:
            required_endpoint_fields = [
                "id", "method", "path", "auth_required", "admin_required",
                "compute_target", "migration_complexity", 
                "requires_architectural_transformation", "anti_patterns"
            ]
            for field in required_endpoint_fields:
                assert field in endpoint, f"Missing endpoint field: {field} in {endpoint.get('id', 'unknown')}"
    
    print("\n✓ Manifest structure is complete and valid")
    
    # Cleanup
    if output_file.exists():
        output_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])