param([Parameter(Mandatory=$true)][string]$Plan,[Parameter(Mandatory=$true)][string]$Report,[string]$ViewerInterop='')
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $Report){throw 'Existing viewer report refused'}
$p=Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
if(-not $ViewerInterop){
 $class=(Get-ItemProperty 'Registry::HKEY_CLASSES_ROOT\EModelView.EModelViewControl\CLSID').'(default)'
 $server=(Get-ItemProperty ("Registry::HKEY_CLASSES_ROOT\CLSID\"+$class+'\InprocServer32')).'(default)'
 $ViewerInterop=Join-Path (Split-Path -Parent $server.Trim('"')) 'eDrawings.Interop.EModelViewControl.dll'
}
Add-Type -Path $ViewerInterop
$code=@'
using System;
using System.IO;
using System.Threading;
using System.Drawing;
using System.Drawing.Printing;
using System.Windows.Forms;
using System.Collections.Generic;
using eDrawings.Interop.EModelViewControl;
public class DwgViewerHost:AxHost {
 public DwgViewerHost():base("{91CAA896-8C40-484C-84E6-9348C69A82A0}"){}
 public IEModelViewControl Viewer {get{return (IEModelViewControl)GetOcx();}}
}
public static class DwgPdf {
 public static Dictionary<string,object> Run(string dwg,string pdf,double width,double height) {
  if(File.Exists(pdf))throw new Exception("Existing PDF refused");
  var result=new Dictionary<string,object>();
  var form=new Form();var host=new DwgViewerHost();{
   form.ShowInTaskbar=false;form.StartPosition=FormStartPosition.Manual;form.Location=new Point(-30000,-30000);form.Size=new Size(1024,768);host.Dock=DockStyle.Fill;form.Controls.Add(host);form.Show();host.CreateControl();
   var viewer=host.Viewer;var events=(_IEModelViewControlEvents_Event)viewer;bool loaded=false,printed=false;string failure=null;
   events.OnFinishedLoadingDocument+=delegate(string name){loaded=true;};
   events.OnFailedLoadingDocument+=delegate(string name,int code,string message){failure=code+" "+message;};
   events.OnFinishedPrintingDocument+=delegate(string name){printed=true;};
   events.OnFailedPrintingDocument+=delegate(string name){failure="Print failed "+name;};
   try{
    viewer.OpenDoc(dwg,false,false,true,"");var deadline=DateTime.UtcNow.AddSeconds(45);
    while(!loaded&&failure==null&&DateTime.UtcNow<deadline){Application.DoEvents();Thread.Sleep(50);}
    if(!loaded||failure!=null)throw new Exception("DWG load failed/timeout: "+failure);
    if(!String.Equals(Path.GetFullPath(viewer.FileName),Path.GetFullPath(dwg),StringComparison.OrdinalIgnoreCase)||viewer.SheetCount!=1)throw new Exception("Wrong DWG or multiple sheets");
    result["loaded_file"]=viewer.FileName;result["sheet_count"]=viewer.SheetCount;
    bool landscape=width>height;double small=Math.Min(width,height),large=Math.Max(width,height);
    int paper=small==210? (int)PaperKind.A4 : small==297? (int)PaperKind.A3 : (int)PaperKind.Custom;
    viewer.SetPageSetupOptions(landscape?EMVPrintOrientation.eLandscape:EMVPrintOrientation.ePortrait,paper,(int)Math.Round(large/25.4*1000),(int)Math.Round(small/25.4*1000),1,7,"Microsoft Print to PDF",0,0,0,0);
    viewer.Print5(false,"CAD-DWG-Draft",false,false,false,EMVPrintType.eOneToOne,1,0,0,false,1,1,pdf);
    deadline=DateTime.UtcNow.AddSeconds(45);long last=-1;int stable=0;
    while(stable<10&&failure==null&&DateTime.UtcNow<deadline){Application.DoEvents();Thread.Sleep(100);long size=File.Exists(pdf)?new FileInfo(pdf).Length:0;stable=printed&&size>0&&size==last?stable+1:0;last=size;}
    if(failure!=null||stable<10)throw new Exception("PDF print failed/timeout: "+failure);
    result["status"]="PDF_PRINTED_REVIEW_REQUIRED";result["print_mode"]="ONE_TO_ONE";result["pdf_bytes"]=new FileInfo(pdf).Length;
   }finally{viewer.CloseActiveDoc("");result["owned_viewer_document_closed"]=true;}
  }
  return result;
 }
}
'@
Add-Type -TypeDefinition $code -ReferencedAssemblies $ViewerInterop,'System.Windows.Forms.dll','System.Drawing.dll'
$result=@{status='FAILED';method='EDRAWINGS_DWG_DIRECT'}
try {
 $before=(Get-FileHash -LiteralPath $p.output_dwg -Algorithm SHA256).Hash.ToLowerInvariant()
 $print=[DwgPdf]::Run($p.output_dwg,$p.output_pdf,$p.sheet.width_mm,$p.sheet.height_mm)
 if((Get-FileHash -LiteralPath $p.output_dwg -Algorithm SHA256).Hash.ToLowerInvariant() -ne $before){throw 'DWG changed during readback'}
 $result=@{status=$print.status;method='EDRAWINGS_DWG_DIRECT';viewer=$print;pdf_source_dwg_sha256=$before;pdf_sha256=(Get-FileHash -LiteralPath $p.output_pdf -Algorithm SHA256).Hash.ToLowerInvariant()}
}catch{$result.error=$_.Exception.ToString()}
[IO.File]::WriteAllText($Report,($result|ConvertTo-Json -Depth 20),[Text.UTF8Encoding]::new($false))
if($result.status -eq 'FAILED'){throw $result.error}

# The isolated process owns the remaining ActiveX window. Avoid faulty host disposal after CloseActiveDoc.
[Environment]::Exit(0)
