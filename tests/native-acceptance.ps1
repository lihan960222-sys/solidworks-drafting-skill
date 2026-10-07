param([ValidateSet('Compile','Inspect','ExportRoundTrip')][string]$Case='Compile',[string]$Source,[string]$Plan,[string]$OutputDirectory,[string]$InteropPath)
$ErrorActionPreference='Stop'
$scripts=Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts'
if($Case -eq 'Compile') {
 Add-Type -Path (Join-Path $InteropPath 'SolidWorks.Interop.sldworks.dll')
 Add-Type -Path (Join-Path $InteropPath 'SolidWorks.Interop.swconst.dll')
 Add-Type -ReferencedAssemblies @((Join-Path $InteropPath 'SolidWorks.Interop.sldworks.dll'),(Join-Path $InteropPath 'SolidWorks.Interop.swconst.dll'),'System.Web.Extensions.dll','System.Drawing.dll','System.Core.dll') -Path @(Get-ChildItem -LiteralPath (Join-Path $scripts 'src') -Filter '*.cs' | ForEach-Object {$_.FullName})
 if(-not [DrawingEngine].GetMethod('ExportDwg')) {throw 'Export pipeline missing'}
 Write-Output 'COMPILE_PASS';exit
}
if(-not [IO.Path]::IsPathRooted($OutputDirectory)){throw 'Absolute output directory required'}
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
if($Case -eq 'Inspect'){ & (Join-Path $scripts 'run.ps1') -Mode Inspect -Source $Source -Output (Join-Path $OutputDirectory 'facts.json') -InteropPath $InteropPath }
else { & (Join-Path $scripts 'run.ps1') -Mode Execute -Plan $Plan -Output (Join-Path $OutputDirectory 'execution.json') -InteropPath $InteropPath }
