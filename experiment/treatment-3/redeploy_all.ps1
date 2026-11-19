# Script de Redespliegue Automático Completo
# Tiempo estimado: 20 minutos
# Costo: ~$5/día mientras esté activo

param(
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "REDESPLIEGUE AUTOMÁTICO COMPLETO" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Tiempo estimado: 20 minutos" -ForegroundColor Yellow
Write-Host "Región: $Region" -ForegroundColor Yellow
Write-Host ""

# Verificar credenciales AWS
Write-Host "[1/7] Verificando credenciales AWS..." -ForegroundColor Cyan
try {
    $identity = aws sts get-caller-identity --region $Region | ConvertFrom-Json
    Write-Host "✓ Cuenta AWS: $($identity.Account)" -ForegroundColor Green
    Write-Host "✓ Usuario: $($identity.Arn)" -ForegroundColor Green
} catch {
    Write-Host "✗ Error: AWS CLI no configurado. Ejecuta 'aws configure'" -ForegroundColor Red
    exit 1
}

# Crear bucket único para código Lambda
Write-Host "`n[2/7] Creando bucket S3 para código Lambda..." -ForegroundColor Cyan
$bucket = "kiro-lambda-code-$(Get-Random -Minimum 1000 -Maximum 9999)"
aws s3 mb s3://$bucket --region $Region
Write-Host "✓ Bucket creado: $bucket" -ForegroundColor Green

# Empaquetar y subir Lambdas
Write-Host "`n[3/7] Empaquetando y subiendo funciones Lambda..." -ForegroundColor Cyan
$baseDir = "$PSScriptRoot\monolith\serverless_taller"
$functions = @("auth", "clientes", "servicios", "transacciones", "reportes")

foreach ($func in $functions) {
    $funcDir = "$baseDir\functions\$func"
    $sharedDir = "$baseDir\shared"
    $tempDir = "$env:TEMP\lambda_$func"
    $zipFile = "$env:TEMP\$func.zip"
    
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    
    Copy-Item "$funcDir\handler.py" "$tempDir\" -Force
    Copy-Item "$sharedDir\*" "$tempDir\" -Recurse -Force
    
    if (Test-Path $zipFile) { Remove-Item $zipFile -Force }
    Compress-Archive -Path "$tempDir\*" -DestinationPath $zipFile -Force
    aws s3 cp $zipFile s3://$bucket/$func.zip --region $Region
    
    Write-Host "  ✓ $func.zip" -ForegroundColor Green
    Remove-Item $tempDir -Recurse -Force
}

# Empaquetar Authorizer
$authDir = "$PSScriptRoot\output\strangler\authorizer"
Compress-Archive -Path "$authDir\*" -DestinationPath "$env:TEMP\authorizer.zip" -Force
aws s3 cp "$env:TEMP\authorizer.zip" s3://$bucket/authorizer.zip --region $Region
Write-Host "  ✓ authorizer.zip" -ForegroundColor Green

# Desplegar VPC
Write-Host "`n[4/7] Desplegando VPC (3-5 minutos)..." -ForegroundColor Cyan
aws cloudformation create-stack `
  --stack-name kiro-migration-vpc `
  --template-body file://$PSScriptRoot/output/persistence/template-vpc.yaml `
  --region $Region | Out-Null

aws cloudformation wait stack-create-complete --stack-name kiro-migration-vpc --region $Region
Write-Host "✓ VPC desplegada" -ForegroundColor Green

# Obtener outputs de VPC
$vpcStack = aws cloudformation describe-stacks --stack-name kiro-migration-vpc --region $Region | ConvertFrom-Json
$vpcOutputs = @{}
foreach ($output in $vpcStack.Stacks[0].Outputs) {
    $vpcOutputs[$output.OutputKey] = $output.OutputValue
}

Write-Host "  VPC ID: $($vpcOutputs.VPCId)" -ForegroundColor Gray
Write-Host "  Subnet 1: $($vpcOutputs.PrivateSubnet1Id)" -ForegroundColor Gray
Write-Host "  Subnet 2: $($vpcOutputs.PrivateSubnet2Id)" -ForegroundColor Gray

# Desplegar S3
Write-Host "`n[5/7] Desplegando S3 (2 minutos)..." -ForegroundColor Cyan
aws cloudformation create-stack `
  --stack-name kiro-migration-s3 `
  --template-body file://$PSScriptRoot/output/uploads/template-s3.yaml `
  --region $Region | Out-Null

aws cloudformation wait stack-create-complete --stack-name kiro-migration-s3 --region $Region
Write-Host "✓ S3 desplegado" -ForegroundColor Green

# Desplegar Authorizer
Write-Host "`n[6/7] Desplegando Authorizer + DynamoDB (3 minutos)..." -ForegroundColor Cyan

# Crear template con parámetro actualizado
$authTemplate = Get-Content "$PSScriptRoot\deploy\template-authorizer-cf.yaml" -Raw
$authTemplate = $authTemplate -replace "Default: 'kiro-lambda-code-2703'", "Default: '$bucket'"
$authTemplate | Set-Content "$env:TEMP\template-authorizer-cf-temp.yaml"

aws cloudformation create-stack `
  --stack-name kiro-migration-authorizer `
  --template-body file://$env:TEMP/template-authorizer-cf-temp.yaml `
  --capabilities CAPABILITY_IAM `
  --region $Region | Out-Null

aws cloudformation wait stack-create-complete --stack-name kiro-migration-authorizer --region $Region
Write-Host "✓ Authorizer + DynamoDB desplegados" -ForegroundColor Green

# Desplegar API Gateway + Lambdas
Write-Host "`n[7/7] Desplegando API Gateway + 5 Lambdas (5-8 minutos)..." -ForegroundColor Cyan

# Crear template con parámetros actualizados
$apiTemplate = Get-Content "$PSScriptRoot\deploy\template-api-complete.yaml" -Raw
$apiTemplate = $apiTemplate -replace "Default: 'kiro-lambda-code-2703'", "Default: '$bucket'"
$apiTemplate = $apiTemplate -replace "Default: 'vpc-054c88795536d72af'", "Default: '$($vpcOutputs.VPCId)'"
$apiTemplate = $apiTemplate -replace "Default: 'subnet-0c24d9c7cbca220d8'", "Default: '$($vpcOutputs.PrivateSubnet1Id)'"
$apiTemplate = $apiTemplate -replace "Default: 'subnet-0d5c8baf0a124a588'", "Default: '$($vpcOutputs.PrivateSubnet2Id)'"
$apiTemplate = $apiTemplate -replace "Default: 'sg-084add8a0cd7696ac'", "Default: '$($vpcOutputs.LambdaSecurityGroupId)'"
$apiTemplate | Set-Content "$env:TEMP\template-api-complete-temp.yaml"

aws cloudformation create-stack `
  --stack-name kiro-migration-api-complete `
  --template-body file://$env:TEMP/template-api-complete-temp.yaml `
  --capabilities CAPABILITY_IAM `
  --region $Region | Out-Null

aws cloudformation wait stack-create-complete --stack-name kiro-migration-api-complete --region $Region
Write-Host "✓ API Gateway + Lambdas desplegados" -ForegroundColor Green

# Obtener API URL
$apiStack = aws cloudformation describe-stacks --stack-name kiro-migration-api-complete --region $Region | ConvertFrom-Json
$apiUrl = ($apiStack.Stacks[0].Outputs | Where-Object { $_.OutputKey -eq "ApiUrl" }).OutputValue

# Resumen final
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "REDESPLIEGUE COMPLETADO ✓" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Stacks desplegados:" -ForegroundColor Yellow
Write-Host "  ✓ kiro-migration-vpc" -ForegroundColor Green
Write-Host "  ✓ kiro-migration-s3" -ForegroundColor Green
Write-Host "  ✓ kiro-migration-authorizer" -ForegroundColor Green
Write-Host "  ✓ kiro-migration-api-complete" -ForegroundColor Green
Write-Host ""
Write-Host "Lambdas desplegadas:" -ForegroundColor Yellow
Write-Host "  ✓ taller-auth (5 endpoints)" -ForegroundColor Green
Write-Host "  ✓ taller-clientes (6 endpoints)" -ForegroundColor Green
Write-Host "  ✓ taller-servicios (6 endpoints)" -ForegroundColor Green
Write-Host "  ✓ taller-transacciones (7 endpoints)" -ForegroundColor Green
Write-Host "  ✓ taller-reportes (5 endpoints)" -ForegroundColor Green
Write-Host "  ✓ taller-jwt-authorizer" -ForegroundColor Green
Write-Host ""
Write-Host "API Gateway URL:" -ForegroundColor Yellow
Write-Host "  $apiUrl" -ForegroundColor White
Write-Host ""
Write-Host "Recursos totales: ~30 AWS resources" -ForegroundColor Yellow
Write-Host "Costo estimado: ~`$5/día" -ForegroundColor Yellow
Write-Host ""
Write-Host "Para eliminar todo: .\cleanup_infrastructure.ps1 -Force" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Guardar información para referencia
@{
    DeploymentDate = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Region = $Region
    LambdaCodeBucket = $bucket
    VPCId = $vpcOutputs.VPCId
    ApiUrl = $apiUrl
} | ConvertTo-Json | Set-Content "$PSScriptRoot\last_deployment.json"

Write-Host "`nInformación guardada en: last_deployment.json" -ForegroundColor Gray
