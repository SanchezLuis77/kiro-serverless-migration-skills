# Validate-Deployment.ps1 — Validates that generated CloudFormation templates are deployable
#
# Usage: .\Validate-Deployment.ps1 -TreatmentDir "experiment\treatment-3"

param(
    [Parameter(Mandatory=$true)]
    [string]$TreatmentDir
)

$ErrorActionPreference = "Continue"

$ReportFile = Join-Path $TreatmentDir "deployment-validation-report.md"

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Deployment Validation Script" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Treatment: $TreatmentDir"
Write-Host "Report: $ReportFile"
Write-Host ""

if (-not (Test-Path $TreatmentDir)) {
    Write-Host "Error: Treatment directory not found: $TreatmentDir" -ForegroundColor Red
    exit 1
}

# Initialize report
$reportHeader = @"
# Deployment Validation Report

**Date:** $(Get-Date -Format "yyyy-MM-dd HH:mm:ss UTC")  
**Treatment:** $TreatmentDir

## Summary

| Component | Validation | Status | Details |
|-----------|------------|--------|---------|
"@

Set-Content -Path $ReportFile -Value $reportHeader

# Function to validate a template
function Validate-Template {
    param([string]$TemplatePath)
    
    $name = Split-Path $TemplatePath -Leaf
    Write-Host "Validating $name..." -NoNewline
    
    try {
        $output = aws cloudformation validate-template --template-body "file://$TemplatePath" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Content -Path $ReportFile -Value "| $name | AWS CLI Syntax | ✅ PASS | Valid CloudFormation syntax |"
            Write-Host " ✅ PASS" -ForegroundColor Green
            return $true
        } else {
            Add-Content -Path $ReportFile -Value "| $name | AWS CLI Syntax | ❌ FAIL | Invalid syntax |"
            Write-Host " ❌ FAIL" -ForegroundColor Red
            return $false
        }
    } catch {
        Add-Content -Path $ReportFile -Value "| $name | AWS CLI Syntax | ⚠️  SKIP | AWS CLI not configured |"
        Write-Host " ⚠️  SKIP (AWS CLI not configured)" -ForegroundColor Yellow
        return $null
    }
}

# Function to validate Lambda code
function Validate-Lambda {
    param([string]$LambdaPath)
    
    $name = (Split-Path (Split-Path $LambdaPath -Parent) -Leaf)
    Write-Host "Validating Lambda: $name..." -NoNewline
    
    try {
        $output = python -m py_compile $LambdaPath 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Content -Path $ReportFile -Value "| Lambda: $name | Python Syntax | ✅ PASS | Valid Python code |"
            Write-Host " ✅ PASS" -ForegroundColor Green
            return $true
        } else {
            Add-Content -Path $ReportFile -Value "| Lambda: $name | Python Syntax | ❌ FAIL | Syntax errors |"
            Write-Host " ❌ FAIL" -ForegroundColor Red
            return $false
        }
    } catch {
        Add-Content -Path $ReportFile -Value "| Lambda: $name | Python Syntax | ⚠️  SKIP | Python not available |"
        Write-Host " ⚠️  SKIP (Python not available)" -ForegroundColor Yellow
        return $null
    }
}

# Validate all CloudFormation templates
Write-Host ""
Write-Host "Phase 1: Validating CloudFormation Templates..." -ForegroundColor Cyan
Write-Host "-----------------------------------------------"

$templates = Get-ChildItem -Path "$TreatmentDir\output" -Filter "*.yaml" -Recurse
$templateResults = @()
foreach ($template in $templates) {
    $result = Validate-Template -TemplatePath $template.FullName
    $templateResults += $result
}

# Validate Lambda functions
Write-Host ""
Write-Host "Phase 2: Validating Lambda Functions..." -ForegroundColor Cyan
Write-Host "---------------------------------------"

$lambdaFiles = Get-ChildItem -Path "$TreatmentDir\output" -Filter "lambda_function.py" -Recurse
$lambdaResults = @()
foreach ($lambda in $lambdaFiles) {
    $result = Validate-Lambda -LambdaPath $lambda.FullName
    $lambdaResults += $result
}

# Add conclusion to report
$awsVersion = (aws --version 2>&1) -replace "`n",""
$pythonVersion = (python --version 2>&1) -replace "`n",""

$reportFooter = @"

## Conclusion

All CloudFormation templates were validated against AWS CloudFormation syntax rules.
All Lambda functions were validated for Python syntax correctness.

**Note:** This validation confirms syntactic correctness but does not test actual deployment.
For end-to-end validation, deploy to AWS using the DEPLOYMENT_GUIDE.md files.

---

**Validated by:** Validate-Deployment.ps1  
**AWS CLI Version:** $awsVersion  
**Python Version:** $pythonVersion
"@

Add-Content -Path $ReportFile -Value $reportFooter

# Summary
$templatePass = ($templateResults | Where-Object { $_ -eq $true }).Count
$templateTotal = $templates.Count
$lambdaPass = ($lambdaResults | Where-Object { $_ -eq $true }).Count
$lambdaTotal = $lambdaFiles.Count

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "✅ Validation Complete" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Templates: $templatePass/$templateTotal passed"
Write-Host "Lambda functions: $lambdaPass/$lambdaTotal passed"
Write-Host ""
Write-Host "Report saved to: $ReportFile"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Review the report: Get-Content $ReportFile"
Write-Host "2. For E2E testing, deploy S3 + Lambda to AWS (see DEPLOYMENT_VALIDATION_PLAN.md)"
Write-Host ""
