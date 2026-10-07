param([Parameter(Mandatory=$true)][string]$Plan,[Parameter(Mandatory=$true)][string]$Output,[ValidateSet('Imported','Missing')][string]$Expected='Imported',[string]$Python='python',[Parameter(Mandatory=$true)][string]$InteropPath)
$ErrorActionPreference='Stop'
$taskScripts=Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts'
# Test the import module without promoting a deliberately incomplete drawing.
try { & (Join-Path $taskScripts 'run.ps1') -Mode Prepare -Plan $Plan -Output $Output -Python $Python -InteropPath $InteropPath -TimeoutSeconds 240 } catch { if(-not(Test-Path -LiteralPath $Output)){throw} }
$taskReport=Get-Content -LiteralPath $Output -Raw -Encoding UTF8 | ConvertFrom-Json
$taskPlan=Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
if($taskReport.error -match 'identity failure'){throw 'Native failure mislabeled as worker identity failure'}
if(-not $taskReport.model_dimension_import){throw 'Actual dimension import report missing'}
if($Expected -eq 'Missing') {
 if($taskReport.model_dimension_import.status -ne 'MISSING_REQUIRED' -or $taskReport.model_dimension_import.missing.Count -eq 0 -or $taskReport.native_worker_exit_code -ne 1){throw 'Missing required import did not fail explicitly'}
 if(Test-Path -LiteralPath $taskPlan.output_drawing){throw 'Incomplete import saved as completed native drawing'}
 Write-Output 'MISSING_REQUIRED_GUARD_PASS';exit 0
}
if($taskReport.model_dimension_import.status -ne 'PASS' -or $taskReport.reopen.status -ne 'PASS' -or $taskReport.native_worker_exit_code -ne 0 -or -not $taskReport.source_hash_unchanged){throw 'Native import/reopen/source integrity regression'}
if($taskReport.status -eq 'FAILED' -and $taskReport.error -ne 'OUTPUT_FAILED: Incomplete geometry definitions'){throw ('Unexpected downstream failure: '+$taskReport.error)}
$taskCheck=@'
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from verify_outputs import check_native_plan
p=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8-sig'))
r=json.loads(Path(sys.argv[3]).read_text(encoding='utf-8-sig'))
f=json.loads(Path(p['facts']).read_text(encoding='utf-8-sig'))
assert p.get('model_dimensions',{}).get('keep'), 'Empty import regression'
c=check_native_plan(r['reopen']['snapshot'],p,f,r['native_bindings'])
assert not c['layout_flags'], c['layout_flags']
print('SELECTED_IMPORT_REOPEN_PASS retained='+str(len(p['model_dimensions']['keep'])))
'@
& $Python -X utf8 -c $taskCheck $taskScripts $Plan $Output
if($LASTEXITCODE -ne 0){throw 'Native dimension identity/value/position check failed'}
