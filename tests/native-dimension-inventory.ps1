param([Parameter(Mandatory=$true)][string]$Plan,[Parameter(Mandatory=$true)][string]$Output,[string]$Python='python',[Parameter(Mandatory=$true)][string]$InteropPath)
$ErrorActionPreference='Stop'
$taskRunner=Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\run.ps1'
& $taskRunner -Mode Visibility -Plan $Plan -Output $Output -Python $Python -InteropPath $InteropPath -TimeoutSeconds 240
if($LASTEXITCODE -ne 0){throw 'Visibility worker failed'}
$taskResult=Get-Content -LiteralPath $Output -Raw -Encoding UTF8 | ConvertFrom-Json
if(-not $taskResult.model_dimension_inventory -or $taskResult.model_dimension_inventory.dimensions.Count -eq 0){throw 'MISSING_NATIVE_DIMENSION_INVENTORY: model parameters alone cannot predict importability'}
if(-not $taskResult.source_hash_unchanged){throw 'Source integrity failure'}
if($taskResult.model_dimension_inventory.requested.Count -ne ($taskResult.model_dimension_inventory.matched.Count+$taskResult.model_dimension_inventory.missing.Count)){throw 'Requested dimension accounting differs'}
Write-Output ('DIMENSION_INVENTORY_PASS available='+$taskResult.model_dimension_inventory.dimensions.Count+' matched='+$taskResult.model_dimension_inventory.matched.Count+' missing='+$taskResult.model_dimension_inventory.missing.Count)
