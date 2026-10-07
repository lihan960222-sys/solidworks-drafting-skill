param([string]$Request,[string]$Response,[string]$InteropPath)
$ErrorActionPreference='Stop'
$result=@{status='FAILED'}
try {
 $requestData=Get-Content -LiteralPath $Request -Raw -Encoding UTF8 | ConvertFrom-Json
 $interop=Join-Path $InteropPath 'SolidWorks.Interop.sldworks.dll';$constants=Join-Path $InteropPath 'SolidWorks.Interop.swconst.dll'
 Add-Type -Path $interop;Add-Type -Path $constants
 Add-Type -ReferencedAssemblies @($interop,$constants,'System.Web.Extensions.dll','System.Drawing.dll','System.Core.dll') -Path @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'src') -Filter '*.cs' | ForEach-Object {$_.FullName})
 switch($requestData.mode){
  'Inspect' {$result=[DrawingEngine]::Inspect($requestData.source,$requestData.configuration)}
  'Visibility' {$result=[DrawingEngine]::Visibility($requestData.plan)}
  'Verify' {$result=[DrawingEngine]::VerifySaved($requestData.plan)}
  'Prepare' {$result=[DrawingEngine]::Execute($requestData.plan)}
  'Preview' {$result=[DrawingEngine]::LayoutPreview($requestData.plan,$Response.Replace('.worker.json','.layout.json'))}
  'Export' {
   $result=[DrawingEngine]::VerifySaved($requestData.plan)
   if($result.status -ne 'FAILED'){
    $export=[DrawingEngine]::ExportDwg($requestData.plan);$result['export']=$export
    if($export.status -eq 'FAILED'){$result['status']='FAILED';$result['error']=$export.error}
   }
  }
  'Execute' {
   $result=[DrawingEngine]::Execute($requestData.plan)
   if($result.status -ne 'FAILED') {
    $export=[DrawingEngine]::ExportDwg($requestData.plan);$result['export']=$export
    if($export.status -eq 'FAILED'){$result['status']='FAILED';$result['error']=$export.error}
   }
  }
 }
}catch{$result=@{status='FAILED';error=$_.Exception.ToString()}}
finally { if('DrawingEngine' -as [type]){[DrawingEngine]::ReleaseSessionReferences()};[GC]::Collect();[GC]::WaitForPendingFinalizers() }
$result['request_id']=$requestData.request_id
[IO.File]::WriteAllText($Response,($result|ConvertTo-Json -Depth 100),[Text.UTF8Encoding]::new($false))
if($result.status -eq 'FAILED'){exit 1}
