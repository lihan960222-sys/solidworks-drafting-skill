param(
 [Parameter(Mandatory=$true)][ValidateSet('Inspect','Visibility','Execute','Prepare','Verify','Export','Preview')][string]$Mode,
 [string]$Source='', [string]$Configuration='', [string]$Plan='',
 [Parameter(Mandatory=$true)][string]$Output,
 [string]$InteropPath='', [string]$Python='python',
 [ValidateRange(1,3600)][int]$TimeoutSeconds=180
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING='utf-8'
foreach($path in @($Output)+@($Source,$Plan | Where-Object {$_})) {if(-not [IO.Path]::IsPathRooted($path) -or $path.Contains('"')){throw 'Absolute, quote-free paths required'}}
if(Test-Path -LiteralPath $Output){throw 'Existing report refused'}
$memory=Get-CimInstance -ClassName Win32_OperatingSystem
if($memory.FreeVirtualMemory -lt 1048576){throw 'MEMORY_PRESSURE: less than 1 GB available virtual memory; no CAD worker started'}
if($Mode -ne 'Inspect') {
 $arguments=@((Join-Path $PSScriptRoot 'validate_plan.py'),$Plan)
 if($Mode -in @('Verify','Export','Preview')) {
  & $Python -X utf8 @arguments --allow-existing
 } else { & $Python @arguments }
 if($LASTEXITCODE -ne 0){throw 'Plan validation failed before CAD mutation'}
}
if(-not $InteropPath){
 $clsid=(Get-ItemProperty -LiteralPath 'Registry::HKEY_CLASSES_ROOT\SldWorks.Application\CLSID').'(default)'
 $server=(Get-ItemProperty -LiteralPath "Registry::HKEY_CLASSES_ROOT\CLSID\$clsid\LocalServer32").'(default)'
 if($server -match '^"([^\"]+\.exe)"'){$exe=$Matches[1]}elseif($server -match '^(.+?\.exe)'){$exe=$Matches[1]}else{throw 'Supply installed interop path'}
 $InteropPath=Join-Path (Split-Path -Parent $exe) 'api\redist'
}
if($InteropPath.EndsWith('.dll',[StringComparison]::OrdinalIgnoreCase)){$InteropPath=Split-Path -Parent $InteropPath}
if(-not (Test-Path -LiteralPath (Join-Path $InteropPath 'SolidWorks.Interop.sldworks.dll'))){throw 'Interop unavailable'}
$mutex=[Threading.Mutex]::new($false,'Local\SolidWorksAutomationPort');$owns=$false
try {
 try{$owns=$mutex.WaitOne(0)}catch [Threading.AbandonedMutexException]{$owns=$true}
 if(-not $owns){throw 'Another CAD worker holds the session lock'}
 $parent=Split-Path -Parent $Output;[IO.Directory]::CreateDirectory($parent)|Out-Null
 $requestId=[guid]::NewGuid().ToString('N');$request=Join-Path $parent ('request-'+$requestId+'.json')
 $workerOutput=$Output+'.'+$requestId+'.worker.json';$log=$Output+'.'+$requestId+'.worker.log'
 @{mode=$Mode;source=$Source;configuration=$Configuration;plan=$Plan;request_id=$requestId} | ConvertTo-Json | Set-Content -LiteralPath $request -Encoding UTF8
 $args=@('-NoProfile','-ExecutionPolicy','Bypass','-Sta','-File',('"'+(Join-Path $PSScriptRoot 'worker.ps1')+'"'),'-Request',('"'+$request+'"'),'-Response',('"'+$workerOutput+'"'),'-InteropPath',('"'+$InteropPath+'"'))
 $worker=Start-Process -FilePath (Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe') -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError ($log+'.err')
 $workerHandle=$worker.Handle
 if(-not $worker.WaitForExit($TimeoutSeconds*1000)){
  $worker.Kill();$worker.WaitForExit();$result=@{status='UNKNOWN';error='Worker timeout: CAD may have changed. Inspect session/files before deciding next action.';worker_log=$log}
 }elseif(Test-Path -LiteralPath $workerOutput){
  $worker.WaitForExit();$worker.Refresh();$result=Get-Content -LiteralPath $workerOutput -Raw -Encoding UTF8 | ConvertFrom-Json
  $result | Add-Member -NotePropertyName native_worker_exit_code -NotePropertyValue $worker.ExitCode -Force
  if($result.request_id -ne $requestId -or $worker.ExitCode -ne 0){$result.status='FAILED';$result | Add-Member -NotePropertyName error -NotePropertyValue ('CAD worker identity/exit failure: '+$result.error) -Force}
 }
 else{$result=@{status='FAILED';error=(Get-Content -LiteralPath ($log+'.err') -Raw);worker_log=$log}}
 if($Mode -in @('Execute','Export') -and $result.status -ne 'FAILED' -and $result.status -ne 'UNKNOWN'){
  $viewerReport=$Output+'.'+$requestId+'.viewer.json';$viewerLog=$Output+'.'+$requestId+'.viewer.log'
  $viewerArgs=@('-NoProfile','-Sta','-ExecutionPolicy','Bypass','-File',('"'+(Join-Path $PSScriptRoot 'dwg_pdf.ps1')+'"'),'-Plan',('"'+$Plan+'"'),'-Report',('"'+$viewerReport+'"'))
  $viewerProcess=Start-Process -FilePath (Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe') -ArgumentList $viewerArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput $viewerLog -RedirectStandardError ($viewerLog+'.err')
  $viewerHandle=$viewerProcess.Handle
  if(-not $viewerProcess.WaitForExit($TimeoutSeconds*1000)){$viewerProcess.Kill();$viewerProcess.WaitForExit();$result.status='UNKNOWN';$result | Add-Member -NotePropertyName error -NotePropertyValue 'DWG viewer timeout; inspect written files before retrying' -Force}
  elseif(Test-Path -LiteralPath $viewerReport){
   $viewerProcess.WaitForExit();$viewerProcess.Refresh()
   $viewerResult=Get-Content -LiteralPath $viewerReport -Raw -Encoding UTF8 | ConvertFrom-Json
   $result.export | Add-Member -NotePropertyName viewer -NotePropertyValue $viewerResult -Force
   $result.export | Add-Member -NotePropertyName viewer_exit_code -NotePropertyValue $viewerProcess.ExitCode -Force
   if($viewerResult.status -eq 'FAILED' -or $viewerProcess.ExitCode -ne 0){$result.status='FAILED';$result | Add-Member -NotePropertyName error -NotePropertyValue ('DWG viewer failed: '+$viewerResult.error+' exit '+$viewerProcess.ExitCode) -Force}
  }else{$result.status='FAILED';$result | Add-Member -NotePropertyName error -NotePropertyValue (Get-Content ($viewerLog+'.err') -Raw) -Force}
  [IO.File]::WriteAllText($workerOutput,($result|ConvertTo-Json -Depth 100),[Text.UTF8Encoding]::new($false))
 }
 if($Mode -in @('Execute','Export','Verify','Prepare') -and $result.status -ne 'FAILED' -and $result.status -ne 'UNKNOWN'){
  [IO.File]::WriteAllText($workerOutput,($result|ConvertTo-Json -Depth 100),[Text.UTF8Encoding]::new($false))
  $verifyArgs=@((Join-Path $PSScriptRoot 'verify_outputs.py'),$Plan,$workerOutput)
  if($Mode -in @('Verify','Prepare')){$verifyArgs+='--native-only'}
  $verified=& $Python -X utf8 @verifyArgs
  if($LASTEXITCODE -eq 0){$result=$verified|ConvertFrom-Json}else{$message=$verified -join ' ';$result | Add-Member -NotePropertyName output_verification_error -NotePropertyValue $message -Force;$result | Add-Member -NotePropertyName error -NotePropertyValue $message -Force;$result.status='FAILED'}
 }
 $json=$result|ConvertTo-Json -Depth 100
 $stream=[IO.File]::Open($Output,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
 try{$bytes=[Text.UTF8Encoding]::new($false).GetBytes($json);$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
 Write-Output "REPORT=$Output";Write-Output "STATUS=$($result.status)"
 if($result.status -in @('FAILED','UNKNOWN')){throw $result.error}
}finally{if($owns){$mutex.ReleaseMutex()};$mutex.Dispose()}
