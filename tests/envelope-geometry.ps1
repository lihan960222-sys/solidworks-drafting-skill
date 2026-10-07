param([Parameter(Mandatory=$true)][string]$InteropPath)
$ErrorActionPreference='Stop'
$interop=Join-Path $InteropPath 'SolidWorks.Interop.sldworks.dll'
$constants=Join-Path $InteropPath 'SolidWorks.Interop.swconst.dll'
Add-Type -Path $interop;Add-Type -Path $constants
$files=@(Get-ChildItem (Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts\src') -Filter '*.cs' | ForEach-Object {$_.FullName})+@(Join-Path $PSScriptRoot 'EnvelopeGeometryChecks.cs')
Add-Type -ReferencedAssemblies @($interop,$constants,'System.Web.Extensions.dll','System.Drawing.dll','System.Core.dll') -Path $files
[DrawingEngine]::CheckEnvelopeGeometry()
'ENVELOPE_GEOMETRY_PASS'
