"""
analyze_results.py — Analiza los resultados de un tratamiento experimental

Calcula métricas de:
  - Cobertura de endpoints
  - Gaps resueltos
  - Completitud de templates
  - Esfuerzo manual
  - Documentación generada

Uso:
    python analyze_results.py --treatment <dir> --output <json_file>
"""

import json
import os
import sys
import ast
import argparse
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

def analyze_templates(treatment_dir: Path) -> Dict[str, Any]:
    """
    Analiza templates CloudFormation en el directorio del tratamiento.
    """
    templates = list(treatment_dir.glob("**/*.yaml")) + list(treatment_dir.glob("**/*.yml"))
    
    total = len(templates)
    valid = 0
    
    for template in templates:
        try:
            content = template.read_text(encoding="utf-8")
            # Validación básica
            if "AWSTemplateFormatVersion" in content and "Resources" in content:
                valid += 1
        except Exception:
            pass
    
    return {
        "total_generated": total,
        "syntactically_valid": valid,
        "deployable": valid,  # Asumimos que válido = deployable
        "template_list": [str(t.relative_to(treatment_dir)) for t in templates]
    }

def analyze_lambda_code(treatment_dir: Path) -> Dict[str, Any]:
    """
    Analiza código Lambda Python generado.
    """
    lambda_files = list(treatment_dir.glob("**/lambda_function.py"))
    
    total = len(lambda_files)
    valid = 0
    has_handler = 0
    
    for lambda_file in lambda_files:
        try:
            content = lambda_file.read_text(encoding="utf-8")
            
            # Validar sintaxis con AST
            try:
                ast.parse(content)
                valid += 1
            except SyntaxError:
                pass
            
            # Verificar lambda_handler
            if "def lambda_handler" in content:
                has_handler += 1
        except Exception:
            pass
    
    return {
        "total_functions": total,
        "syntactically_valid": valid,
        "has_handler": has_handler
    }

def analyze_documentation(treatment_dir: Path) -> Dict[str, Any]:
    """
    Analiza documentación generada (READMEs, guías).
    """
    readme_files = list(treatment_dir.glob("**/README.md"))
    deployment_guides = list(treatment_dir.glob("**/DEPLOYMENT*.md"))
    migration_guides = list(treatment_dir.glob("**/MIGRATION*.md"))
    
    # Estimar páginas (250 palabras = 1 página)
    total_words = 0
    for doc in readme_files + deployment_guides + migration_guides:
        try:
            content = doc.read_text(encoding="utf-8")
            total_words += len(content.split())
        except Exception:
            pass
    
    total_pages = total_words // 250
    
    return {
        "readme_files": len(readme_files),
        "deployment_guides": len(deployment_guides),
        "migration_guides": len(migration_guides),
        "total_pages": total_pages
    }

def analyze_gaps(treatment_dir: Path) -> Dict[str, Any]:
    """
    Analiza si los gaps críticos fueron resueltos.
    Busca keywords en los templates.
    """
    gaps = {
        "GAP-01": False,  # RDS Proxy
        "GAP-02": False,  # S3
        "GAP-03": False   # DynamoDB
    }
    
    templates = list(treatment_dir.glob("**/*.yaml")) + list(treatment_dir.glob("**/*.yml"))
    
    for template in templates:
        try:
            content = template.read_text(encoding="utf-8")
            
            if "DBProxy" in content:
                gaps["GAP-01"] = True
            
            if "AWS::S3::Bucket" in content:
                gaps["GAP-02"] = True
            
            if "AWS::DynamoDB::Table" in content:
                gaps["GAP-03"] = True
        except Exception:
            pass
    
    total_resolved = sum(1 for v in gaps.values() if v)
    
    return {
        **gaps,
        "total_resolved": total_resolved
    }

def analyze_coverage(treatment_dir: Path, manifest_path: Path) -> Dict[str, Any]:
    """
    Analiza cobertura de endpoints comparando con el manifest.
    """
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        
        total_endpoints = manifest["summary"]["total_endpoints"]
        
        # Contar templates generados como proxy de cobertura
        # (cada template potencialmente cubre múltiples endpoints)
        templates = analyze_templates(treatment_dir)
        
        # Heurística: si hay 7 templates (el esperado), asumimos 100% coverage
        expected_templates = 7
        covered_endpoints = min(
            total_endpoints,
            int(total_endpoints * (templates["total_generated"] / expected_templates))
        )
        
        coverage_percentage = (covered_endpoints / total_endpoints) * 100 if total_endpoints > 0 else 0
        
        return {
            "total_endpoints": total_endpoints,
            "covered_endpoints": covered_endpoints,
            "coverage_percentage": round(coverage_percentage, 2)
        }
    except Exception as e:
        print(f"Warning: Could not analyze coverage: {e}")
        return {
            "total_endpoints": 29,
            "covered_endpoints": 0,
            "coverage_percentage": 0.0
        }

def main():
    parser = argparse.ArgumentParser(description="Analiza resultados de un tratamiento experimental")
    parser.add_argument("--treatment", type=Path, required=True, help="Directorio del tratamiento")
    parser.add_argument("--output", type=Path, required=True, help="Archivo JSON de salida")
    parser.add_argument("--manifest", type=Path, help="Ruta al manifest (opcional)")
    
    args = parser.parse_args()
    
    treatment_dir = args.treatment
    
    if not treatment_dir.exists():
        print(f"Error: Treatment directory not found: {treatment_dir}")
        return 1
    
    print(f"Analyzing treatment: {treatment_dir}")
    
    # Buscar manifest
    manifest_path = args.manifest
    if not manifest_path:
        # Buscar en el treatment dir
        possible_manifests = list(treatment_dir.glob("**/migration-manifest.json"))
        if possible_manifests:
            manifest_path = possible_manifests[0]
    
    # Ejecutar análisis
    results = {
        "treatment_dir": str(treatment_dir),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "coverage": analyze_coverage(treatment_dir, manifest_path) if manifest_path else {},
        "gaps_resolved": analyze_gaps(treatment_dir),
        "templates": analyze_templates(treatment_dir),
        "lambda_code": analyze_lambda_code(treatment_dir),
        "documentation": analyze_documentation(treatment_dir)
    }
    
    # Escribir resultados
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Análisis completado:")
    print(f"   - Templates: {results['templates']['total_generated']} ({results['templates']['syntactically_valid']} válidos)")
    print(f"   - Lambda functions: {results['lambda_code']['total_functions']}")
    print(f"   - Documentation: {results['documentation']['total_pages']} páginas")
    print(f"   - Gaps resolved: {results['gaps_resolved']['total_resolved']}/3")
    if results['coverage']:
        print(f"   - Coverage: {results['coverage']['coverage_percentage']}%")
    print(f"\n📄 Reporte guardado en: {args.output}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
