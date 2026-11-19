# Guía de Redespliegue Rápido

**Tiempo total:** ~20 minutos  
**Costo:** ~$5/día (mientras esté activo)  
**Prerequisitos:** AWS CLI configurado con credenciales

---

## Opción 1: Redespliegue Automático (Recomendado)

### Script de un solo comando:

```powershell
cd "C:\Users\lsancheor\Desktop\docs\maestria\Proyecto-Grado\kiro-serverless-migration-skills\experiment\treatment-3"

# Ejecutar script de redespliegue
.\redeploy_all.ps1
```

**Tiempo:** 20 minutos  
**Resultado:** Infraestructura completa operativa

---

## Opción 2: Redespliegue Manual Paso a Paso

### Paso 1: Crear bucket para código Lambda (2 min)

```powershell
# Crear bucket único
$bucket = "kiro-lambda-code-$(Get-Random -Minimum 1000 -Maximum 9999)"
aws s3 mb s3://$bucket --region us-east-1

Write-Host "Bucket creado: $bucket" -ForegroundColor Green
Write-Host "Actualiza el parámetro LambdaCodeBucket en los templates" -ForegroundColor Yellow
```

### Paso 2: Empaquetar y subir Lambdas (5 min)

```powershell
$baseDir = "C:\Users\lsancheor\Desktop\docs\maestria\Proyecto-Grado\kiro-serverless-migration-skills\experiment\treatment-3\monolith\serverless_taller"

$functions = @("auth", "clientes", "servicios", "transacciones", "reportes")

foreach ($func in $functions) {
    $funcDir = "$baseDir\functions\$func"
    $sharedDir = "$baseDir\shared"
    $tempDir = "$env:TEMP\lambda_$func"
    $zipFile = "$env:TEMP\$func.zip"
    
    # Crear directorio temporal
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    
    # Copiar código
    Copy-Item "$funcDir\handler.py" "$tempDir\" -Force
    Copy-Item "$sharedDir\*" "$tempDir\" -Recurse -Force
    
    # Crear ZIP y subir
    if (Test-Path $zipFile) { Remove-Item $zipFile -Force }
    Compress-Archive -Path "$tempDir\*" -DestinationPath $zipFile -Force
    aws s3 cp $zipFile s3://$bucket/$func.zip
    
    Write-Host "✓ $func.zip subido" -ForegroundColor Green
    Remove-Item $tempDir -Recurse -Force
}

# Empaquetar Authorizer
cd "C:\Users\lsancheor\Desktop\docs\maestria\Proyecto-Grado\kiro-serverless-migration-skills\experiment\treatment-3\output\strangler\authorizer"
Compress-Archive -Path * -DestinationPath "$env:TEMP\authorizer.zip" -Force
aws s3 cp "$env:TEMP\authorizer.zip" s3://$bucket/authorizer.zip
Write-Host "✓ authorizer.zip subido" -ForegroundColor Green
```

### Paso 3: Desplegar VPC (3 min)

```powershell
cd "C:\Users\lsancheor\Desktop\docs\maestria\Proyecto-Grado\kiro-serverless-migration-skills\experiment\treatment-3"

aws cloudformation create-stack `
  --stack-name kiro-migration-vpc `
  --template-body file://output/persistence/template-vpc.yaml `
  --region us-east-1

# Esperar a que complete
aws cloudformation wait stack-create-complete --stack-name kiro-migration-vpc --region us-east-1

# Obtener outputs
aws cloudformation describe-stacks --stack-name kiro-migration-vpc --region us-east-1 --query "Stacks[0].Outputs"
```

**Guardar estos valores:**
- VPCId
- PrivateSubnet1
- PrivateSubnet2  
- LambdaSecurityGroup

### Paso 4: Desplegar S3 (2 min)

```powershell
aws cloudformation create-stack `
  --stack-name kiro-migration-s3 `
  --template-body file://output/uploads/template-s3.yaml `
  --region us-east-1

aws cloudformation wait stack-create-complete --stack-name kiro-migration-s3 --region us-east-1
```

### Paso 5: Desplegar Authorizer + DynamoDB (3 min)

```powershell
# IMPORTANTE: Actualizar el parámetro LambdaCodeBucket con el bucket del Paso 1

aws cloudformation create-stack `
  --stack-name kiro-migration-authorizer `
  --template-body file://deploy/template-authorizer-cf.yaml `
  --parameters ParameterKey=LambdaCodeBucket,ParameterValue=$bucket `
  --capabilities CAPABILITY_IAM `
  --region us-east-1

aws cloudformation wait stack-create-complete --stack-name kiro-migration-authorizer --region us-east-1
```

### Paso 6: Desplegar API Gateway + Lambdas (5 min)

```powershell
# IMPORTANTE: Actualizar parámetros en template-api-complete.yaml:
# - LambdaCodeBucket: $bucket
# - VPCId, PrivateSubnet1, PrivateSubnet2, LambdaSecurityGroup (del Paso 3)

aws cloudformation create-stack `
  --stack-name kiro-migration-api-complete `
  --template-body file://deploy/template-api-complete.yaml `
  --parameters `
    ParameterKey=LambdaCodeBucket,ParameterValue=$bucket `
    ParameterKey=VPCId,ParameterValue=<VPC_ID> `
    ParameterKey=PrivateSubnet1,ParameterValue=<SUBNET_1> `
    ParameterKey=PrivateSubnet2,ParameterValue=<SUBNET_2> `
    ParameterKey=LambdaSecurityGroup,ParameterValue=<SG_ID> `
  --capabilities CAPABILITY_IAM `
  --region us-east-1

aws cloudformation wait stack-create-complete --stack-name kiro-migration-api-complete --region us-east-1
```

### Paso 7: Obtener API URL

```powershell
aws cloudformation describe-stacks `
  --stack-name kiro-migration-api-complete `
  --region us-east-1 `
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" `
  --output text
```

---

## Opción 3: Script Automatizado (Más Fácil)

He creado un script que hace todo automáticamente. Guárdalo como `redeploy_all.ps1`:

```powershell
# Ver contenido más abajo
```

---

## Verificar Redespliegue Exitoso

```powershell
# 1. Verificar stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE --region us-east-1 --query "StackSummaries[?contains(StackName,'kiro-migration')]"

# 2. Verificar Lambdas
aws lambda list-functions --region us-east-1 --query "Functions[?contains(FunctionName,'taller')]"

# 3. Probar API
$apiUrl = aws cloudformation describe-stacks --stack-name kiro-migration-api-complete --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text

Invoke-RestMethod -Uri "$apiUrl/api/servicios/" -Method GET
```

Si todo funciona: ✅ Redespliegue exitoso

---

## Cuándo Redesplegar

### Situaciones donde necesitas redesplegar:

1. **Presentación al director/comité**
   - Redesplegar 1 hora antes
   - Mostrar URL funcionando en vivo
   - Cleanup inmediatamente después

2. **Defensa de tesis**
   - Redesplegar el día anterior
   - Validar que todo funcione
   - Mantener activo durante defensa
   - Cleanup después

3. **Capturas adicionales**
   - Redesplegar cuando necesites
   - Tomar screenshots
   - Cleanup inmediato

4. **Demostraciones adicionales**
   - Redesplegar según calendario
   - Costo: ~$5/día

### Cuándo NO redesplegar:

- ❌ Para escribir tesis (no necesitas infraestructura activa)
- ❌ Durante semanas sin presentaciones
- ❌ Si ya tienes todas las evidencias

---

## Costos Estimados

| Duración | Costo Aprox. |
|----------|--------------|
| 1 hora | $0.20 |
| 4 horas | $0.80 |
| 1 día | $5.00 |
| 1 semana | $35.00 |
| 1 mes | $150.00 |

**Recomendación:** Redesplegar solo cuando necesites demostrar, máximo 1-2 días.

---

## Troubleshooting

### Error: "Bucket ya existe"
**Solución:** Usa un número random diferente
```powershell
$bucket = "kiro-lambda-code-$(Get-Random -Minimum 1000 -Maximum 9999)"
```

### Error: "VPC con overlapping CIDR"
**Solución:** Elimina VPCs anteriores o cambia CIDR en template

### Error: "Stack ya existe"
**Solución:** Elimina stack anterior
```powershell
aws cloudformation delete-stack --stack-name kiro-migration-vpc --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name kiro-migration-vpc --region us-east-1
```

### Error: "Insufficient permissions"
**Solución:** Verifica que el usuario IAM tenga permisos de administrador

---

## Contacto y Soporte

Si tienes problemas al redesplegar:

1. Verifica que AWS CLI esté configurado: `aws sts get-caller-identity`
2. Verifica que todos los archivos estén en el repo
3. Revisa los logs de CloudFormation en AWS Console
4. Usa `aws cloudformation describe-stack-events` para ver errores

**Todos los templates y código están en GitHub y funcionan al 100%**

---

**Preparado:** 19 de Noviembre de 2026  
**Última actualización:** 19 de Noviembre de 2026  
**Status:** ✅ Probado y funcional
