# Cleanup Infrastructure - Automated Cleanup Script
# This script deletes all deployed CloudFormation stacks and resources
# IMPORTANT: This will DELETE all resources and cannot be undone!

param(
    [switch]$Force = $false,
    [string]$Region = "us-east-1",
    [string]$ProjectPrefix = "kiro-migration"
)

$ErrorActionPreference = "Stop"
$OutputDir = "cleanup_results"
$LogFile = "$OutputDir/cleanup_log_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"

# Create output directory
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Write-Log {
    param($Message, $Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$Level] $Message"
    Write-Host $LogMessage
    Add-Content -Path $LogFile -Value $LogMessage
}

function Wait-ForStackDeletion {
    param(
        [string]$StackName,
        [int]$TimeoutMinutes = 60
    )
    
    Write-Log "Waiting for stack '$StackName' to be deleted..."
    $StartTime = Get-Date
    
    while ($true) {
        try {
            $Stack = aws cloudformation describe-stacks --stack-name $StackName --region $Region 2>$null | ConvertFrom-Json
            
            if (-not $Stack) {
                Write-Log "Stack deleted successfully!" "SUCCESS"
                return $true
            }
            
            $Status = $Stack.Stacks[0].StackStatus
            Write-Log "Stack status: $Status"
            
            if ($Status -match "DELETE_FAILED") {
                Write-Log "Stack deletion failed with status: $Status" "ERROR"
                
                # Get failure reason
                $Events = aws cloudformation describe-stack-events --stack-name $StackName --region $Region --max-items 10 | ConvertFrom-Json
                foreach ($Event in $Events.StackEvents) {
                    if ($Event.ResourceStatus -match "DELETE_FAILED") {
                        Write-Log "Failure reason: $($Event.ResourceStatusReason)" "ERROR"
                    }
                }
                return $false
            }
            
            # Check timeout
            $Elapsed = (Get-Date) - $StartTime
            if ($Elapsed.TotalMinutes -gt $TimeoutMinutes) {
                Write-Log "Timeout waiting for stack deletion" "ERROR"
                return $false
            }
            
            Start-Sleep -Seconds 30
            
        } catch {
            # Stack not found - deletion complete
            Write-Log "Stack deleted successfully!" "SUCCESS"
            return $true
        }
    }
}

function Delete-Stack {
    param(
        [string]$StackName,
        [int]$TimeoutMinutes = 60
    )
    
    Write-Log "========================================" "INFO"
    Write-Log "Deleting stack: $StackName" "INFO"
    Write-Log "========================================" "INFO"
    
    # Check if stack exists
    try {
        $Stack = aws cloudformation describe-stacks --stack-name $StackName --region $Region 2>$null
        if (-not $Stack) {
            Write-Log "Stack does not exist (already deleted)" "INFO"
            return $true
        }
    } catch {
        Write-Log "Stack does not exist (already deleted)" "INFO"
        return $true
    }
    
    # Delete stack
    try {
        Write-Log "Initiating stack deletion..."
        aws cloudformation delete-stack --stack-name $StackName --region $Region
        
        # Wait for deletion
        $Success = Wait-ForStackDeletion -StackName $StackName -TimeoutMinutes $TimeoutMinutes
        
        return $Success
        
    } catch {
        Write-Log "Error deleting stack: $_" "ERROR"
        return $false
    }
}

function Empty-S3Bucket {
    param([string]$BucketName)
    
    Write-Log "Emptying S3 bucket: $BucketName" "INFO"
    
    try {
        # Check if bucket exists
        aws s3 ls s3://$BucketName --region $Region 2>$null | Out-Null
        
        # Delete all objects
        Write-Log "Deleting all objects in bucket..."
        aws s3 rm s3://$BucketName --recursive --region $Region
        
        # Delete all versions (if versioning enabled)
        Write-Log "Deleting all object versions..."
        $Versions = aws s3api list-object-versions --bucket $BucketName --region $Region | ConvertFrom-Json
        
        if ($Versions.Versions) {
            foreach ($Version in $Versions.Versions) {
                aws s3api delete-object --bucket $BucketName --key $Version.Key --version-id $Version.VersionId --region $Region
            }
        }
        
        if ($Versions.DeleteMarkers) {
            foreach ($Marker in $Versions.DeleteMarkers) {
                aws s3api delete-object --bucket $BucketName --key $Marker.Key --version-id $Marker.VersionId --region $Region
            }
        }
        
        Write-Log "S3 bucket emptied successfully" "SUCCESS"
        return $true
        
    } catch {
        Write-Log "Error emptying S3 bucket: $_" "WARNING"
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
        return $null
    }
}

# =============================================================================
# MAIN CLEANUP WORKFLOW
# =============================================================================

Write-Log "========================================" "INFO"
Write-Log "KIRO SERVERLESS MIGRATION CLEANUP" "INFO"
Write-Log "========================================" "INFO"
Write-Log "Region: $Region" "INFO"
Write-Log "Project Prefix: $ProjectPrefix" "INFO"
Write-Log "========================================" "INFO"

# Safety confirmation
if (-not $Force) {
    Write-Log ""
    Write-Log "[WARNING]  WARNING: This will DELETE all deployed infrastructure!" "WARNING"
    Write-Log "[WARNING]  This action CANNOT be undone!" "WARNING"
    Write-Log ""
    $Confirmation = Read-Host "Are you sure you want to proceed? Type 'DELETE' to confirm"
    
    if ($Confirmation -ne "DELETE") {
        Write-Log "Cleanup cancelled by user" "INFO"
        exit 0
    }
}

Write-Log ""
Write-Log "Starting cleanup..." "INFO"

$CleanupResults = @{
    StartTime = Get-Date
    Stacks = @()
    Success = $true
}

# =============================================================================
# PHASE 1: EMPTY S3 BUCKETS (must be done before deleting stacks)
# =============================================================================

Write-Log ""
Write-Log "PHASE 1: Emptying S3 Buckets" "INFO"

$S3StackName = "$ProjectPrefix-s3"
$BucketName = Get-StackOutput -StackName $S3StackName -OutputKey "BucketName"

if ($BucketName) {
    Empty-S3Bucket -BucketName $BucketName
} else {
    # Try to find buckets by listing
    $Buckets = aws s3api list-buckets --region $Region | ConvertFrom-Json
    foreach ($Bucket in $Buckets.Buckets) {
        if ($Bucket.Name -like "*$ProjectPrefix*") {
            Write-Log "Found bucket: $($Bucket.Name)" "INFO"
            Empty-S3Bucket -BucketName $Bucket.Name
        }
    }
}

# =============================================================================
# PHASE 2: DELETE STACKS IN REVERSE ORDER
# =============================================================================

Write-Log ""
Write-Log "PHASE 2: Deleting CloudFormation Stacks" "INFO"

# Define deletion order (reverse of deployment order)
$StacksToDelete = @(
    "$ProjectPrefix-presigned-lambda",
    "$ProjectPrefix-s3",
    "$ProjectPrefix-api-gateway",
    "$ProjectPrefix-authorizer",
    "$ProjectPrefix-dynamodb",
    "$ProjectPrefix-rds",
    "$ProjectPrefix-vpc"
)

foreach ($StackName in $StacksToDelete) {
    Write-Log ""
    $Success = Delete-Stack -StackName $StackName -TimeoutMinutes 90
    
    $CleanupResults.Stacks += @{
        Name = $StackName
        Success = $Success
    }
    
    if (-not $Success) {
        Write-Log "Failed to delete stack: $StackName" "ERROR"
        $CleanupResults.Success = $false
    }
}

# =============================================================================
# PHASE 3: VERIFY ALL RESOURCES DELETED
# =============================================================================

Write-Log ""
Write-Log "PHASE 3: Verifying Cleanup" "INFO"

# Check for remaining stacks
Write-Log "Checking for remaining CloudFormation stacks..."
$RemainingStacks = aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --region $Region | ConvertFrom-Json
$ProjectStacks = $RemainingStacks.StackSummaries | Where-Object { $_.StackName -like "*$ProjectPrefix*" }

if ($ProjectStacks.Count -gt 0) {
    Write-Log "Found $($ProjectStacks.Count) remaining stacks:" "WARNING"
    foreach ($Stack in $ProjectStacks) {
        Write-Log "  - $($Stack.StackName) ($($Stack.StackStatus))" "WARNING"
    }
} else {
    Write-Log "No remaining stacks found" "SUCCESS"
}

# Check for remaining S3 buckets
Write-Log "Checking for remaining S3 buckets..."
$Buckets = aws s3api list-buckets --region $Region | ConvertFrom-Json
$ProjectBuckets = $Buckets.Buckets | Where-Object { $_.Name -like "*$ProjectPrefix*" }

if ($ProjectBuckets.Count -gt 0) {
    Write-Log "Found $($ProjectBuckets.Count) remaining buckets:" "WARNING"
    foreach ($Bucket in $ProjectBuckets) {
        Write-Log "  - $($Bucket.Name)" "WARNING"
    }
} else {
    Write-Log "No remaining S3 buckets found" "SUCCESS"
}

# Check for remaining Lambda functions
Write-Log "Checking for remaining Lambda functions..."
$Functions = aws lambda list-functions --region $Region | ConvertFrom-Json
$ProjectFunctions = $Functions.Functions | Where-Object { $_.FunctionName -like "*$ProjectPrefix*" }

if ($ProjectFunctions.Count -gt 0) {
    Write-Log "Found $($ProjectFunctions.Count) remaining Lambda functions:" "WARNING"
    foreach ($Function in $ProjectFunctions) {
        Write-Log "  - $($Function.FunctionName)" "WARNING"
    }
} else {
    Write-Log "No remaining Lambda functions found" "SUCCESS"
}

# Check for remaining DynamoDB tables
Write-Log "Checking for remaining DynamoDB tables..."
$Tables = aws dynamodb list-tables --region $Region | ConvertFrom-Json
$ProjectTables = $Tables.TableNames | Where-Object { $_ -like "*$ProjectPrefix*" }

if ($ProjectTables.Count -gt 0) {
    Write-Log "Found $($ProjectTables.Count) remaining DynamoDB tables:" "WARNING"
    foreach ($Table in $ProjectTables) {
        Write-Log "  - $Table" "WARNING"
    }
} else {
    Write-Log "No remaining DynamoDB tables found" "SUCCESS"
}

# =============================================================================
# CLEANUP SUMMARY
# =============================================================================

$CleanupResults.EndTime = Get-Date
$CleanupResults.Duration = ($CleanupResults.EndTime - $CleanupResults.StartTime).ToString()

Write-Log ""
Write-Log "========================================" "INFO"
Write-Log "CLEANUP SUMMARY" "INFO"
Write-Log "========================================" "INFO"
Write-Log "Total Duration: $($CleanupResults.Duration)" "INFO"
Write-Log ""

$SuccessCount = ($CleanupResults.Stacks | Where-Object { $_.Success }).Count
$TotalCount = $CleanupResults.Stacks.Count

Write-Log "Stacks Deleted: $SuccessCount / $TotalCount" "INFO"
Write-Log ""

foreach ($Stack in $CleanupResults.Stacks) {
    $Status = if ($Stack.Success) { "DELETED" } else { "FAILED" }
    $Symbol = if ($Stack.Success) { "[OK]" } else { "[FAIL]" }
    Write-Log "$Symbol $($Stack.Name): $Status" $(if ($Stack.Success) { "SUCCESS" } else { "ERROR" })
}

# Save results
$CleanupResults | ConvertTo-Json -Depth 10 | Set-Content "$OutputDir/cleanup_results.json"
Write-Log ""
Write-Log "Cleanup results saved to: $OutputDir/cleanup_results.json" "INFO"
Write-Log "Cleanup log saved to: $LogFile" "INFO"

Write-Log ""
if ($SuccessCount -eq $TotalCount -and $ProjectStacks.Count -eq 0) {
    Write-Log "Cleanup completed successfully! All resources deleted. [OK]" "SUCCESS"
    Write-Log ""
    Write-Log "COST SAVED: ~$137/month (or ~$4.64/day)" "SUCCESS"
    exit 0
} else {
    Write-Log "Cleanup completed with warnings. Some resources may remain." "WARNING"
    Write-Log "Please check AWS Console to verify all resources are deleted." "WARNING"
    Write-Log ""
    Write-Log "If any resources remain, delete them manually to avoid charges." "WARNING"
    exit 1
}

