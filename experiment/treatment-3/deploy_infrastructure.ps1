# Deploy Infrastructure - Automated Deployment Script
# This script deploys all generated CloudFormation templates in the correct order
# and captures results for thesis validation

param(
    [switch]$SkipRDS = $false,
    [switch]$DryRun = $false,
    [string]$Region = "us-east-1",
    [string]$ProjectPrefix = "kiro-migration"
)

$ErrorActionPreference = "Stop"
$OutputDir = "deployment_results"
$TemplateDir = "output"
$LogFile = "$OutputDir/deployment_log_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"

# Create output directory
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Write-Log {
    param($Message, $Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$Level] $Message"
    Write-Host $LogMessage
    
    # Use mutex to prevent concurrent file access
    $MaxRetries = 5
    $RetryCount = 0
    $Success = $false
    
    while (-not $Success -and $RetryCount -lt $MaxRetries) {
        try {
            Add-Content -Path $LogFile -Value $LogMessage -ErrorAction Stop
            $Success = $true
        } catch {
            $RetryCount++
            Start-Sleep -Milliseconds 100
        }
    }
}

function Wait-ForStackComplete {
    param(
        [string]$StackName,
        [int]$TimeoutMinutes = 60
    )
    
    Write-Log "Waiting for stack '$StackName' to complete..."
    $StartTime = Get-Date
    
    while ($true) {
        $Stack = aws cloudformation describe-stacks --stack-name $StackName --region $Region 2>$null | ConvertFrom-Json
        
        if (-not $Stack) {
            Write-Log "Stack not found or error occurred" "ERROR"
            return $false
        }
        
        $Status = $Stack.Stacks[0].StackStatus
        Write-Log "Stack status: $Status"
        
        if ($Status -match "COMPLETE$") {
            Write-Log "Stack completed successfully!" "SUCCESS"
            return $true
        }
        
        if ($Status -match "FAILED$" -or $Status -match "ROLLBACK") {
            Write-Log "Stack deployment failed with status: $Status" "ERROR"
            
            # Get failure reason
            $Events = aws cloudformation describe-stack-events --stack-name $StackName --region $Region --max-items 10 | ConvertFrom-Json
            foreach ($Event in $Events.StackEvents) {
                if ($Event.ResourceStatus -match "FAILED") {
                    Write-Log "Failure reason: $($Event.ResourceStatusReason)" "ERROR"
                }
            }
            return $false
        }
        
        # Check timeout
        $Elapsed = (Get-Date) - $StartTime
        if ($Elapsed.TotalMinutes -gt $TimeoutMinutes) {
            Write-Log "Timeout waiting for stack" "ERROR"
            return $false
        }
        
        Start-Sleep -Seconds 30
    }
}

function Deploy-Stack {
    param(
        [string]$StackName,
        [string]$TemplateFile,
        [hashtable]$Parameters = @{},
        [int]$TimeoutMinutes = 60
    )
    
    Write-Log "========================================" "INFO"
    Write-Log "Deploying stack: $StackName" "INFO"
    Write-Log "Template: $TemplateFile" "INFO"
    Write-Log "========================================" "INFO"
    
    if ($DryRun) {
        Write-Log "DRY RUN - Would deploy $StackName" "INFO"
        return $true
    }
    
    # Check if template exists
    if (-not (Test-Path $TemplateFile)) {
        Write-Log "Template file not found: $TemplateFile" "ERROR"
        return $false
    }
    
    # Validate template
    Write-Log "Validating template..."
    try {
        aws cloudformation validate-template --template-body file://$TemplateFile --region $Region | Out-Null
        Write-Log "Template validation successful" "SUCCESS"
    } catch {
        Write-Log "Template validation failed: $_" "ERROR"
        return $false
    }
    
    # Build parameter string
    $ParamString = ""
    if ($Parameters.Count -gt 0) {
        $ParamArray = @()
        foreach ($Key in $Parameters.Keys) {
            $ParamArray += "ParameterKey=$Key,ParameterValue=$($Parameters[$Key])"
        }
        $ParamString = "--parameters " + ($ParamArray -join " ")
    }
    
    # Check if stack exists
    $StackExists = $false
    try {
        $ExistingStack = aws cloudformation describe-stacks --stack-name $StackName --region $Region 2>$null
        if ($ExistingStack) {
            $StackExists = $true
            Write-Log "Stack already exists, will update" "INFO"
        }
    } catch {
        Write-Log "Stack does not exist, will create" "INFO"
    }
    
    # Deploy stack
    try {
        if ($StackExists) {
            Write-Log "Updating stack..."
            $Command = "aws cloudformation update-stack --stack-name $StackName --template-body file://$TemplateFile --region $Region $ParamString --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND"
            Invoke-Expression $Command | Out-Null
        } else {
            Write-Log "Creating stack..."
            $Command = "aws cloudformation create-stack --stack-name $StackName --template-body file://$TemplateFile --region $Region $ParamString --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND"
            Invoke-Expression $Command | Out-Null
        }
        
        # Wait for completion
        $Success = Wait-ForStackComplete -StackName $StackName -TimeoutMinutes $TimeoutMinutes
        
        if ($Success) {
            # Get outputs
            $Stack = aws cloudformation describe-stacks --stack-name $StackName --region $Region | ConvertFrom-Json
            $Outputs = $Stack.Stacks[0].Outputs
            
            Write-Log "Stack outputs:" "SUCCESS"
            foreach ($Output in $Outputs) {
                Write-Log "  $($Output.OutputKey): $($Output.OutputValue)" "SUCCESS"
            }
            
            # Save outputs to file
            $OutputFile = "$OutputDir/$StackName-outputs.json"
            $Outputs | ConvertTo-Json -Depth 10 | Set-Content $OutputFile
            Write-Log "Outputs saved to: $OutputFile" "INFO"
        }
        
        return $Success
        
    } catch {
        Write-Log "Error deploying stack: $_" "ERROR"
        return $false
    }
}

function Get-StackOutput {
    param(
        [string]$StackName,
        [string]$OutputKey
    )
    
    try {
        $Stack = aws cloudformation describe-stacks --stack-name $StackName --region $Region | ConvertFrom-Json
        $Output = $Stack.Stacks[0].Outputs | Where-Object { $_.OutputKey -eq $OutputKey }
        return $Output.OutputValue
    } catch {
        Write-Log "Error getting stack output: $_" "ERROR"
        return $null
    }
}

# =============================================================================
# MAIN DEPLOYMENT WORKFLOW
# =============================================================================

Write-Log "========================================" "INFO"
Write-Log "KIRO SERVERLESS MIGRATION DEPLOYMENT" "INFO"
Write-Log "========================================" "INFO"
Write-Log "Region: $Region" "INFO"
Write-Log "Project Prefix: $ProjectPrefix" "INFO"
Write-Log "Skip RDS: $SkipRDS" "INFO"
Write-Log "Dry Run: $DryRun" "INFO"
Write-Log "========================================" "INFO"

# Check AWS credentials
Write-Log "Checking AWS credentials..."
try {
    $Identity = aws sts get-caller-identity --region $Region | ConvertFrom-Json
    Write-Log "AWS Account: $($Identity.Account)" "SUCCESS"
    Write-Log "AWS User: $($Identity.Arn)" "SUCCESS"
} catch {
    Write-Log "AWS credentials not configured. Please run 'aws configure'" "ERROR"
    exit 1
}

$DeploymentResults = @{
    StartTime = Get-Date
    Stacks = @()
    Success = $true
}

# =============================================================================
# PHASE 1: NETWORK INFRASTRUCTURE (VPC)
# =============================================================================

Write-Log ""
Write-Log "PHASE 1: Deploying Network Infrastructure (VPC)" "INFO"
Write-Log "Estimated time: 5-10 minutes" "INFO"

$VpcStackName = "$ProjectPrefix-vpc"
$VpcTemplate = "$TemplateDir/persistence/template-vpc.yaml"

$VpcSuccess = Deploy-Stack -StackName $VpcStackName -TemplateFile $VpcTemplate -TimeoutMinutes 15

$DeploymentResults.Stacks += @{
    Name = $VpcStackName
    Phase = "Phase 1 - Network"
    Success = $VpcSuccess
    Template = $VpcTemplate
}

if (-not $VpcSuccess) {
    Write-Log "VPC deployment failed. Cannot continue." "ERROR"
    $DeploymentResults.Success = $false
    $DeploymentResults | ConvertTo-Json -Depth 10 | Set-Content "$OutputDir/deployment_results.json"
    exit 1
}

# Get VPC outputs
$VpcId = Get-StackOutput -StackName $VpcStackName -OutputKey "VPCId"
$PrivateSubnet1 = Get-StackOutput -StackName $VpcStackName -OutputKey "PrivateSubnet1"
$PrivateSubnet2 = Get-StackOutput -StackName $VpcStackName -OutputKey "PrivateSubnet2"
$SecurityGroup = Get-StackOutput -StackName $VpcStackName -OutputKey "LambdaSecurityGroup"

Write-Log "VPC ID: $VpcId" "SUCCESS"

# =============================================================================
# PHASE 2: DATABASE (RDS) - OPTIONAL
# =============================================================================

if (-not $SkipRDS) {
    Write-Log ""
    Write-Log "PHASE 2: Deploying Database (RDS Aurora Serverless)" "INFO"
    Write-Log "Estimated time: 30-60 minutes" "INFO"
    Write-Log "WARNING: This is the most expensive component (~$88/month)" "INFO"
    
    $RdsStackName = "$ProjectPrefix-rds"
    $RdsTemplate = "$TemplateDir/persistence/template-rds.yaml"
    
    $RdsParams = @{
        VPCId = $VpcId
        PrivateSubnetIds = "$PrivateSubnet1,$PrivateSubnet2"
        LambdaSecurityGroupId = $SecurityGroup
    }
    
    $RdsSuccess = Deploy-Stack -StackName $RdsStackName -TemplateFile $RdsTemplate -Parameters $RdsParams -TimeoutMinutes 90
    
    $DeploymentResults.Stacks += @{
        Name = $RdsStackName
        Phase = "Phase 2 - Database (RDS)"
        Success = $RdsSuccess
        Template = $RdsTemplate
    }
    
    if (-not $RdsSuccess) {
        Write-Log "RDS deployment failed. Continuing with remaining components..." "WARNING"
    }
} else {
    Write-Log ""
    Write-Log "PHASE 2: Skipping RDS deployment (--SkipRDS flag set)" "INFO"
}

# =============================================================================
# PHASE 3: DYNAMODB + LAMBDA AUTHORIZER
# =============================================================================

Write-Log ""
Write-Log "PHASE 3: Deploying DynamoDB Tables" "INFO"
Write-Log "Estimated time: 5-10 minutes" "INFO"

# Note: DynamoDB tables are typically embedded in the strangler-fig template
# For this deployment, we'll check if there's a separate DynamoDB template

$DynamoDbTemplates = Get-ChildItem -Path $TemplateDir -Recurse -Filter "*dynamodb*.yaml"
if ($DynamoDbTemplates) {
    foreach ($Template in $DynamoDbTemplates) {
        $StackName = "$ProjectPrefix-dynamodb-$($Template.BaseName)"
        $Success = Deploy-Stack -StackName $StackName -TemplateFile $Template.FullName -TimeoutMinutes 15
        
        $DeploymentResults.Stacks += @{
            Name = $StackName
            Phase = "Phase 3 - DynamoDB"
            Success = $Success
            Template = $Template.FullName
        }
    }
} else {
    Write-Log "No separate DynamoDB templates found (may be embedded in API Gateway template)" "INFO"
}

# =============================================================================
# PHASE 4: API GATEWAY + AUTHORIZER
# =============================================================================

Write-Log ""
Write-Log "PHASE 4: Deploying API Gateway + Lambda Authorizer" "INFO"
Write-Log "Estimated time: 10-15 minutes" "INFO"

# Deploy Lambda Authorizer first
$AuthorizerStackName = "$ProjectPrefix-authorizer"
$AuthorizerTemplate = "$TemplateDir/strangler/template-authorizer.yaml"

if (Test-Path $AuthorizerTemplate) {
    $AuthorizerParams = @{
        JWTSecretKey = "your-secret-key-change-in-production-$(Get-Random)"
    }
    
    $AuthorizerSuccess = Deploy-Stack -StackName $AuthorizerStackName -TemplateFile $AuthorizerTemplate -Parameters $AuthorizerParams -TimeoutMinutes 15
    
    $DeploymentResults.Stacks += @{
        Name = $AuthorizerStackName
        Phase = "Phase 4 - Lambda Authorizer"
        Success = $AuthorizerSuccess
        Template = $AuthorizerTemplate
    }
}

# Deploy API Gateway
$ApiGatewayStackName = "$ProjectPrefix-api-gateway"
$ApiGatewayTemplate = "$TemplateDir/strangler/template-api-gateway.yaml"

if (Test-Path $ApiGatewayTemplate) {
    $ApiParams = @{
        VPCId = $VpcId
        PrivateSubnetIds = "$PrivateSubnet1,$PrivateSubnet2"
    }
    
    # Only add LambdaSecurityGroupId if SecurityGroup is not empty
    if ($SecurityGroup) {
        $ApiParams.LambdaSecurityGroupId = $SecurityGroup
    }
    
    $ApiSuccess = Deploy-Stack -StackName $ApiGatewayStackName -TemplateFile $ApiGatewayTemplate -Parameters $ApiParams -TimeoutMinutes 20
    
    $DeploymentResults.Stacks += @{
        Name = $ApiGatewayStackName
        Phase = "Phase 4 - API Gateway"
        Success = $ApiSuccess
        Template = $ApiGatewayTemplate
    }
    
    if ($ApiSuccess) {
        $ApiUrl = Get-StackOutput -StackName $ApiGatewayStackName -OutputKey "APIGatewayURL"
        Write-Log "API Gateway URL: $ApiUrl" "SUCCESS"
    }
}

# =============================================================================
# PHASE 5: S3 + LAMBDA PRESIGNED URL
# =============================================================================

Write-Log ""
Write-Log "PHASE 5: Deploying S3 Bucket + Lambda Presigned URL Function" "INFO"
Write-Log "Estimated time: 10-15 minutes" "INFO"

$S3StackName = "$ProjectPrefix-s3"
$S3Template = "$TemplateDir/uploads/template-s3.yaml"

if (Test-Path $S3Template) {
    $S3Success = Deploy-Stack -StackName $S3StackName -TemplateFile $S3Template -TimeoutMinutes 15
    
    $DeploymentResults.Stacks += @{
        Name = $S3StackName
        Phase = "Phase 5 - S3 Bucket"
        Success = $S3Success
        Template = $S3Template
    }
    
    if ($S3Success) {
        $BucketName = Get-StackOutput -StackName $S3StackName -OutputKey "BucketName"
        Write-Log "S3 Bucket: $BucketName" "SUCCESS"
    }
}

# Deploy Lambda Presigned URL function
$PresignedStackName = "$ProjectPrefix-presigned-lambda"
$PresignedTemplate = "$TemplateDir/uploads/template-presigned-lambda.yaml"

if (Test-Path $PresignedTemplate) {
    $PresignedParams = @{}
    if ($BucketName) {
        $PresignedParams.BucketName = $BucketName
    }
    
    $PresignedSuccess = Deploy-Stack -StackName $PresignedStackName -TemplateFile $PresignedTemplate -Parameters $PresignedParams -TimeoutMinutes 15
    
    $DeploymentResults.Stacks += @{
        Name = $PresignedStackName
        Phase = "Phase 5 - Lambda Presigned URL"
        Success = $PresignedSuccess
        Template = $PresignedTemplate
    }
}

# =============================================================================
# DEPLOYMENT SUMMARY
# =============================================================================

$DeploymentResults.EndTime = Get-Date
$DeploymentResults.Duration = ($DeploymentResults.EndTime - $DeploymentResults.StartTime).ToString()

Write-Log ""
Write-Log "========================================" "INFO"
Write-Log "DEPLOYMENT SUMMARY" "INFO"
Write-Log "========================================" "INFO"
Write-Log "Total Duration: $($DeploymentResults.Duration)" "INFO"
Write-Log ""

$SuccessCount = ($DeploymentResults.Stacks | Where-Object { $_.Success }).Count
$TotalCount = $DeploymentResults.Stacks.Count

Write-Log "Stacks Deployed: $SuccessCount / $TotalCount" "INFO"
Write-Log ""

foreach ($Stack in $DeploymentResults.Stacks) {
    $Status = if ($Stack.Success) { "SUCCESS" } else { "FAILED" }
    $Symbol = if ($Stack.Success) { "[OK]" } else { "[FAIL]" }
    Write-Log "$Symbol $($Stack.Phase): $($Stack.Name) - $Status" $(if ($Stack.Success) { "SUCCESS" } else { "ERROR" })
}

# Save results
$DeploymentResults | ConvertTo-Json -Depth 10 | Set-Content "$OutputDir/deployment_results.json"
Write-Log ""
Write-Log "Deployment results saved to: $OutputDir/deployment_results.json" "INFO"
Write-Log "Deployment log saved to: $LogFile" "INFO"

# =============================================================================
# NEXT STEPS
# =============================================================================

Write-Log ""
Write-Log "========================================" "INFO"
Write-Log "NEXT STEPS" "INFO"
Write-Log "========================================" "INFO"
Write-Log "1. Run end-to-end tests: .\test_deployment.ps1" "INFO"
Write-Log "2. Capture screenshots for thesis documentation" "INFO"
Write-Log "3. IMPORTANT: Run cleanup when done: .\cleanup_infrastructure.ps1" "INFO"
Write-Log ""

if ($SuccessCount -eq $TotalCount) {
    Write-Log "All stacks deployed successfully!" "SUCCESS"
    exit 0
} else {
    Write-Log "Some stacks failed to deploy. Check logs for details." "WARNING"
    exit 1
}
