#!/bin/bash
# validate_deployment.sh — Validates that generated CloudFormation templates are deployable
# 
# Usage: bash validate_deployment.sh <treatment_dir>
# Example: bash validate_deployment.sh experiment/treatment-3

set -e  # Exit on error

TREATMENT_DIR=$1
REPORT_FILE="$TREATMENT_DIR/deployment-validation-report.md"

if [ -z "$TREATMENT_DIR" ]; then
  echo "Usage: $0 <treatment_dir>"
  exit 1
fi

if [ ! -d "$TREATMENT_DIR" ]; then
  echo "Error: Treatment directory not found: $TREATMENT_DIR"
  exit 1
fi

echo "=================================="
echo "Deployment Validation Script"
echo "=================================="
echo ""
echo "Treatment: $TREATMENT_DIR"
echo "Report: $REPORT_FILE"
echo ""

# Initialize report
cat > "$REPORT_FILE" << 'EOF'
# Deployment Validation Report

**Date:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")  
**Treatment:** ${TREATMENT_DIR}

## Summary

| Component | Validation | Status | Details |
|-----------|------------|--------|---------|
EOF

# Function to validate a template
validate_template() {
  local template=$1
  local name=$(basename $template)
  
  echo "Validating $name..."
  
  if aws cloudformation validate-template --template-body file://$template > /dev/null 2>&1; then
    echo "| $name | AWS CLI Syntax | ✅ PASS | Valid CloudFormation syntax |" >> "$REPORT_FILE"
    echo "  ✅ PASS"
  else
    echo "| $name | AWS CLI Syntax | ❌ FAIL | Invalid syntax |" >> "$REPORT_FILE"
    echo "  ❌ FAIL"
  fi
}

# Function to validate Lambda code
validate_lambda() {
  local lambda_file=$1
  local name=$(basename $(dirname $lambda_file))
  
  echo "Validating Lambda: $name..."
  
  if python -m py_compile $lambda_file 2>/dev/null; then
    echo "| Lambda: $name | Python Syntax | ✅ PASS | Valid Python code |" >> "$REPORT_FILE"
    echo "  ✅ PASS"
  else
    echo "| Lambda: $name | Python Syntax | ❌ FAIL | Syntax errors |" >> "$REPORT_FILE"
    echo "  ❌ FAIL"
  fi
}

# Validate all CloudFormation templates
echo ""
echo "Phase 1: Validating CloudFormation Templates..."
echo "-----------------------------------------------"

for template in $TREATMENT_DIR/output/**/*.yaml; do
  if [ -f "$template" ]; then
    validate_template $template
  fi
done

# Validate Lambda functions
echo ""
echo "Phase 2: Validating Lambda Functions..."
echo "---------------------------------------"

for lambda_file in $TREATMENT_DIR/output/**/lambda_function.py; do
  if [ -f "$lambda_file" ]; then
    validate_lambda $lambda_file
  fi
done

# Add conclusion to report
cat >> "$REPORT_FILE" << 'EOF'

## Conclusion

All CloudFormation templates were validated against AWS CloudFormation syntax rules.
All Lambda functions were validated for Python syntax correctness.

**Note:** This validation confirms syntactic correctness but does not test actual deployment.
For end-to-end validation, deploy to AWS using the DEPLOYMENT_GUIDE.md files.

---

**Validated by:** validate_deployment.sh  
**AWS CLI Version:** $(aws --version 2>&1)  
**Python Version:** $(python --version 2>&1)
EOF

echo ""
echo "=================================="
echo "✅ Validation Complete"
echo "=================================="
echo ""
echo "Report saved to: $REPORT_FILE"
echo ""
echo "Next steps:"
echo "1. Review the report: cat $REPORT_FILE"
echo "2. For E2E testing, deploy S3 + Lambda to AWS (see DEPLOYMENT_VALIDATION_PLAN.md)"
echo ""
