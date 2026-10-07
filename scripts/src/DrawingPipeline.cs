using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

public static partial class DrawingEngine {
 static void PreserveTemplate(Dictionary<string,object> p,ISheet sheet){
  var sh=Map(p["sheet"]);var props=(double[])sheet.GetProperties2();
  Require(Math.Abs(props[5]*1000-N(sh,"width_mm"))<.1&&Math.Abs(props[6]*1000-N(sh,"height_mm"))<.1,"Select a template with the requested paper size; do not resize its format");
  Require((props[4]!=0)==Convert.ToBoolean(sh["first_angle"]),"Projection must follow the selected template");
 }
 public static Dictionary<string,object> LayoutPreview(string planPath,string output){
  var p=Read(planPath);string native=S(p,"output_drawing");Require(Path.GetDirectoryName(output)==Path.GetDirectoryName(native),"Preview must stay internal");
  string pdf=Path.ChangeExtension(output,"pdf");Require(!File.Exists(pdf),"Existing preview refused");sw=(ISldWorks)System.Runtime.InteropServices.Marshal.GetActiveObject("SldWorks.Application");
  int e=0,w=0;var doc=sw.GetOpenDocumentByName(native) as IModelDoc2;bool owned=doc==null;
  try{if(owned)doc=sw.OpenDoc6(native,3,1,"",ref e,ref w) as IModelDoc2;
   Require(doc!=null&&!doc.GetSaveFlag(),"Saved layout required");sw.ActivateDoc3(doc.GetTitle(),false,0,ref e);
   Require(doc.Extension.SaveAs3(pdf,0,1,null,null,ref e,ref w)&&e==0&&File.Exists(pdf),"Layout preview export failed");
   return D("status","LAYOUT_PREVIEW_ONLY","pdf",pdf,"deliverable",false,"manufacturing_release","NOT_APPROVED");
  }finally{if(owned&&doc!=null)sw.CloseDoc(doc.GetTitle());}
 }
 // Reused migration operations are integrated here; no external skill/driver calls.
 static object NativeInventory(IModelDoc2 doc) {
  var rows=new List<object>();
  for(var v=(IView)((IDrawingDoc)doc).GetFirstView();v!=null;v=(IView)v.GetNextView()) {
   var items=new List<object>();
   foreach(var ao in A(v.GetAnnotations())) {
    var a=(IAnnotation)ao;var specific=a.GetSpecificAnnotation();
    var item=D("annotation_name",a.GetName(),"type",a.GetType(),"dangling",a.IsDangling(),"position",a.GetPosition());
    var dd=specific as IDisplayDimension;var note=specific as INote;var table=specific as ITableAnnotation;
    if(dd!=null){var dim=(IDimension)dd.GetDimension2(0);string name=dim.FullName;if(name.Count(c=>c=='@')>=2)name=name.Substring(0,name.LastIndexOf('@'));item["name"]=name;item["value_si"]=dim.SystemValue;item["prefix"]=dd.GetText(1);item["suffix"]=dd.GetText(2);}
    else if(note!=null)item["text"]=note.GetText();
    else if(table!=null){var cells=new List<object>();for(int r=0;r<table.RowCount;r++){var row=new List<string>();for(int c=0;c<table.ColumnCount;c++)row.Add(table.Text[r,c]);cells.Add(row);}item["rows"]=cells;}
    else item["name"]=a.GetName();
    items.Add(item);
   }
   rows.Add(D("view",v.Name,"source",v.GetReferencedModelName(),"configuration",v.ReferencedConfiguration,"scale",v.ScaleDecimal,"orientation",v.GetOrientationName(),"position",v.Position,"outline",v.GetOutline(),"annotations",items));
  }
  return rows;
 }
 static void SnapshotReopen(Dictionary<string,object> p,Dictionary<string,object> report){
  string output=S(p,"output_drawing");sw.CloseDoc(drawing.GetTitle());int e=0,w=0;
  drawing=(IModelDoc2)sw.OpenDoc6(output,3,1,"",ref e,ref w);Require(drawing!=null&&e==0,"Native reopen failed: "+e);dr=(IDrawingDoc)drawing;
  var snapshot=NativeInventory(drawing);
  Require(Serializer().Serialize(snapshot)==Serializer().Serialize(report["native_baseline"]),"Native annotations/views changed on reopen");
  foreach(var vo in Rows(snapshot))foreach(var ao in Rows(Map(vo)["annotations"]))Require(!Convert.ToBoolean(Map(ao)["dangling"]),"Dangling annotation");
  Require(((string[])dr.GetSheetNames()).Length==1,"Only one sheet permitted");
  report["reopen"]=D("status","PASS","snapshot",snapshot);
  sw.ActivateDoc3(drawing.GetTitle(),false,0,ref e);drawing.ViewZoomtofit2();
 }
 static void AddFacts(Dictionary<string,object> facts){
  var required=new List<object>();var known=new HashSet<string>{"Extrusion","ExtrudeCut","Boss","Cut","BossThin","CutThin","ICE","Imported","BaseBody","Revolution","RevCut","Fillet","Round fillet corner","Chamfer","HoleWzd","Sweep","CutSweep","BoundaryBoss","BoundaryCut","Loft","CutLoft","MirrorPattern","LPattern","CirPattern"};
  foreach(var fo in Rows(facts["features"])){
   var f=Map(fo);if(Convert.ToBoolean(f["suppressed"])||!(known.Contains(S(f,"type"))||f.ContainsKey("has_faces")&&Convert.ToBoolean(f["has_faces"])))continue;
   string id=S(f,"name")+"|"+S(f,"type");var fields=new List<string>();
   foreach(var dimension in Rows(f["dimensions"]))fields.Add("dimension:"+S(Map(dimension),"name"));
   if(S(f,"type")=="HoleWzd")fields.AddRange(new[]{"diameter","location","depth","through_blind","quantity"});
   if(S(f,"type")=="Chamfer")fields.AddRange(new[]{"distance","angle"});
   if(fields.Count==0)fields.Add("geometry_definition");
   required.Add(D("id",id,"name",f["name"],"type",f["type"],"required",fields.Distinct().ToArray(),"evidence","features:"+S(f,"name")));
  }
  facts["draft_features"]=required;facts["schema_version"]=2;
  facts["coverage_limits"]="Feature-derived requirements must be supplemented by the agent's face/edge inventory for sketch locations, blind depths and unnamed geometric features.";
 }
 static Dictionary<string,object> ModelDimensionInventory(Dictionary<string,object> p,HashSet<string> original){
  var options=p.ContainsKey("model_dimensions")?Map(p["model_dimensions"]):D("include_unmarked",true);
  bool unmarked=options.ContainsKey("include_unmarked")&&Convert.ToBoolean(options["include_unmarked"]);
  bool hidden=options.ContainsKey("include_hidden_features")&&Convert.ToBoolean(options["include_hidden_features"]);
  var first=views.Values.First();int activationError=0;
  // Keep the legacy automation-port source -> drawing -> view activation order.
  var sourceDoc=sw.GetOpenDocumentByName(first.GetReferencedModelName()) as IModelDoc2;
  Require(sourceDoc!=null,"Referenced source must be open for model dimension import");
  Require(sw.ActivateDoc3(sourceDoc.GetTitle(),false,1,ref activationError)!=null,"Activate dimension source failed: "+activationError);
  Require(sw.ActivateDoc3(drawing.GetTitle(),false,1,ref activationError)!=null,"Activate dimension drawing failed: "+activationError);
  Require(dr.ActivateView(first.Name),"Activate model view failed");drawing.ClearSelection2(true);
  var inserted=Rows(dr.InsertModelAnnotations3(0,32768+(unmarked?524288:0),true,true,hidden,false));
  Require(drawing.ForceRebuild3(false),"Imported dimension rebuild failed");
  var dimensions=new List<object>();var nativeNames=new HashSet<string>();
  foreach(var v in views.Values)for(var dd=(IDisplayDimension)v.GetFirstDisplayDimension5();dd!=null;dd=(IDisplayDimension)dd.GetNext5()){
   var dim=(IDimension)dd.GetDimension2(0);if(original!=null&&original.Contains(dim.FullName))continue;
   nativeNames.Add(dim.FullName);var a=(IAnnotation)dd.GetAnnotation();
   dimensions.Add(D("name",String.Join("@",dim.FullName.Split('@').Take(2)),"source_name",dim.FullName,"view",v.Name,"value_si",dim.SystemValue,"display_type",dd.Type2,"position",a.GetPosition(),"dangling",a.IsDangling()));
  }
  var keep=OptionalRows(options,"keep").Select(Convert.ToString).ToArray();
  Func<string,bool> matches=k=>nativeNames.Any(n=>n==k||n.StartsWith(k+"@",StringComparison.Ordinal));
  return D("status","MEASURED","include_unmarked",unmarked,"include_hidden_features",hidden,"returned_annotations",inserted.Length,"dimensions",dimensions,"requested",keep,"matched",keep.Where(matches).ToArray(),"missing",keep.Where(k=>!matches(k)).ToArray());
 }
 static void ImportAnnotations(Dictionary<string,object> p,Dictionary<string,object> report){
  if(p.ContainsKey("model_dimensions")){
   var options=Map(p["model_dimensions"]);var keep=new HashSet<string>(OptionalRows(options,"keep").Select(Convert.ToString));
   var original=new HashSet<string>();foreach(var v in views.Values)for(var dd=(IDisplayDimension)v.GetFirstDisplayDimension5();dd!=null;dd=(IDisplayDimension)dd.GetNext5())original.Add(((IDimension)dd.GetDimension2(0)).FullName);
   var inventory=ModelDimensionInventory(p,original);report["model_dimension_import"]=inventory;
   inventory["status"]=Rows(inventory["missing"]).Length==0?"PASS":"MISSING_REQUIRED";
   Require(Rows(inventory["missing"]).Length==0,"Requested model dimensions were not imported: "+String.Join(",",Rows(inventory["missing"]).Select(Convert.ToString))+"; inspect Visibility.model_dimension_inventory before selecting keep");
   var found=new HashSet<string>();var remove=new List<IAnnotation>();
   foreach(var v in views.Values)for(var dd=(IDisplayDimension)v.GetFirstDisplayDimension5();dd!=null;dd=(IDisplayDimension)dd.GetNext5()){
    var dim=(IDimension)dd.GetDimension2(0);if(original.Contains(dim.FullName))continue;
    string key=keep.FirstOrDefault(k=>dim.FullName==k||dim.FullName.StartsWith(k+"@",StringComparison.Ordinal));
   if(key==null||!found.Add(key))remove.Add((IAnnotation)dd.GetAnnotation());else {
    var annotation=(IAnnotation)dd.GetAnnotation();TemplateFont(annotation);Bind("model:"+key,annotation,v.Name);
    if(bindings!=null)Map(bindings["model:"+key])["dimension_name"]=String.Join("@",dim.FullName.Split('@').Take(2));
    foreach(var placement in OptionalRows(options,"positions")){var q=Map(placement);if(S(q,"name")==key){var xy=Vec(q["position_mm"]);Require(annotation.SetPosition2(xy[0]/1000,xy[1]/1000,0),"Imported dimension position failed");}}
   }
   }
   Require(found.SetEquals(keep),"Requested model dimensions were not imported: "+String.Join(",",keep.Except(found)));
   drawing.ClearSelection2(true);foreach(var a in remove)Require(a.Select3(true,null),"Redundant dimension selection failed");if(remove.Count>0)Require(drawing.Extension.DeleteSelection2(0),"Dimension deduplication failed");drawing.ClearSelection2(true);
  }
  if(p.ContainsKey("import_pmi")&&Convert.ToBoolean(p["import_pmi"]))foreach(var v in views.Values)v.ImportAnnotations(false,true,true,false,true);
 }
 static IEdge PickEdge(IView view,Dictionary<string,object> edgeFact,IModelDoc2 model){
  if(S(edgeFact,"type")=="circle")return VisibleCircle(D("view",views.First(kv=>kv.Value==view).Key,"edge_id",edgeFact["id"]),new Dictionary<int,Dictionary<string,object>>{{Convert.ToInt32(edgeFact["id"]),edgeFact}},model);
  Require(S(edgeFact,"type")=="line","Only line/circle references supported");int error=0;
  var target=model.Extension.GetObjectByPersistReference3(Convert.FromBase64String(S(edgeFact,"persist_ref")),out error) as IEdge;
  Require(target!=null&&error==0,"Persistent line reference cannot resolve");
  var start=(double[])((IVertex)target.GetStartVertex()).GetPoint();var end=(double[])((IVertex)target.GetEndVertex()).GetPoint();var matches=new List<IEdge>();
  Func<double[],double[],bool> same=(a,b)=>a.Length==b.Length&&a.Zip(b,(x,y)=>Math.Abs(x-y)).Max()<1e-8;
  foreach(var co in A(view.GetVisibleComponents()))foreach(var eo in A(view.GetVisibleEntities2((Component2)co,1))){var edge=eo as IEdge;if(edge==null||!((ICurve)edge.GetCurve()).IsLine())continue;var a=edge.GetStartVertex() as IVertex;var b=edge.GetEndVertex() as IVertex;if(a==null||b==null)continue;var x=(double[])a.GetPoint();var y=(double[])b.GetPoint();if(same(start,x)&&same(end,y)||same(start,y)&&same(end,x))matches.Add(edge);}
  Require(matches.Count==1,"Ambiguous/invisible line reference: "+edgeFact["id"]+"; matches="+matches.Count);return matches[0];
 }
 static void FeatureDimensions(Dictionary<string,object> p,Dictionary<int,Dictionary<string,object>> edges,IModelDoc2 model){
  if(OptionalRows(p,"linear").Length+OptionalRows(p,"radial").Length>0)Require(drawing.ForceRebuild3(false),"Feature view rebuild failed");
  foreach(string key in new[]{"linear","radial"})foreach(var item in OptionalRows(p,key)){
   var q=Map(item);var v=views[S(q,"view")];Require(dr.ActivateView(""),"Return to sheet before resolving source coordinates");drawing.ClearSelection2(true);
   int id=Convert.ToInt32(q[key=="linear"?"a_edge":"edge_id"]);var firstEdge=PickEdge(v,edges[id],model);var secondEdge=key=="linear"?PickEdge(v,edges[Convert.ToInt32(q["b_edge"])],model):null;
   Require(dr.ActivateView(v.Name),"Activate feature view");var select=(ISelectData)((ISelectionMgr)drawing.SelectionManager).CreateSelectData();select.View=(View)v;
   Require(((IEntity)firstEdge).Select4(false,(SelectData)select),"Feature edge selection");
   if(key=="linear")Require(((IEntity)secondEdge).Select4(true,(SelectData)select),"Second feature edge selection");
   var xy=Vec(q["position_mm"]);IDisplayDimension dd;
   if(key=="radial")dd=(IDisplayDimension)drawing.AddRadialDimension2(xy[0]/1000,xy[1]/1000,0);
   else if(S(q,"direction")=="angular")dd=(IDisplayDimension)drawing.AddDimension2(xy[0]/1000,xy[1]/1000,0);
   else dd=(IDisplayDimension)(S(q,"direction")=="horizontal"?drawing.AddHorizontalDimension2(xy[0]/1000,xy[1]/1000,0):drawing.AddVerticalDimension2(xy[0]/1000,xy[1]/1000,0));
   Require(dd!=null,"Feature dimension creation failed");double actual=((IDimension)dd.GetDimension2(0)).SystemValue;
   actual*=key=="linear"&&S(q,"direction")=="angular"?180/Math.PI:1000;
   Require(Math.Abs(actual-N(q,key=="linear"&&S(q,"direction")=="angular"?"expected_deg":"expected_mm"))<1e-5,"Feature dimension mismatch: "+actual);TemplateFont((IAnnotation)dd.GetAnnotation());Bind(S(q,"id"),(IAnnotation)dd.GetAnnotation(),S(q,"view"));drawing.ClearSelection2(true);
  }
 }
 static void Arrange(Dictionary<string,object> p){
  if(!p.ContainsKey("auto_arrange")||!Convert.ToBoolean(p["auto_arrange"]))return;
  drawing.ClearSelection2(true);int selected=0;
  foreach(var v in views.Values)foreach(var item in A(v.GetAnnotations())){var a=(IAnnotation)item;if(a.GetSpecificAnnotation() is IDisplayDimension){Require(a.Select3(true,null),"Arrange selection");selected++;}}
  if(selected>0)Require(drawing.Extension.AlignDimensions(0,.008),"Native auto-arrange failed");drawing.ClearSelection2(true);
 }
 public static Dictionary<string,object> ExportDwg(string planPath){
  var p=Read(planPath);var report=D("status","FAILED","method","DWG_INDEPENDENT_READBACK","settings_restored",false);bool ownsNative=false;var originalSettings=new Dictionary<int,int>();var toggles=new Dictionary<int,bool>();double? originalScaleFactor=null;
  sw=(ISldWorks)System.Runtime.InteropServices.Marshal.GetActiveObject("SldWorks.Application");
  try {
   string native=S(p,"output_drawing"),dwg=S(p,"output_dwg"),pdf=S(p,"output_pdf");int e=0,w=0;
   Require(!File.Exists(dwg)&&!File.Exists(pdf),"Existing deliverables refused");drawing=sw.GetOpenDocumentByName(native) as IModelDoc2;ownsNative=drawing==null;if(ownsNative)drawing=sw.OpenDoc6(native,3,1,"",ref e,ref w) as IModelDoc2;Require(drawing!=null&&!drawing.GetSaveFlag(),"Saved native drawing required");
   dr=(IDrawingDoc)drawing;Require(((string[])dr.GetSheetNames()).Length==1,"Single sheet required");sw.ActivateDoc3(drawing.GetTitle(),false,0,ref e);
   foreach(var setting in new[]{swUserPreferenceIntegerValue_e.swDxfVersion,swUserPreferenceIntegerValue_e.swDxfOutputNoScale,swUserPreferenceIntegerValue_e.swDxfMultiSheetOption,swUserPreferenceIntegerValue_e.swDxfOutputFonts,swUserPreferenceIntegerValue_e.swDxfOutputLineStyles})originalSettings[(int)setting]=sw.GetUserPreferenceIntegerValue((int)setting);
   foreach(var setting in new[]{swUserPreferenceToggle_e.swDxfMapping,swUserPreferenceToggle_e.swDxfExportAllSheetsToPaperSpace,swUserPreferenceToggle_e.swDxfAllSheetsToPaperSpace})toggles[(int)setting]=sw.GetUserPreferenceToggle((int)setting);
   originalScaleFactor=sw.GetUserPreferenceDoubleValue((int)swUserPreferenceDoubleValue_e.swDxfOutputScaleFactor);report["previous_dxf_scale_factor"]=originalScaleFactor;report["native_sheet_properties"]=((ISheet)dr.GetCurrentSheet()).GetProperties2();sw.SetUserPreferenceDoubleValue((int)swUserPreferenceDoubleValue_e.swDxfOutputScaleFactor,1.0);sw.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swDxfAllSheetsToPaperSpace,false);
   sw.SetUserPreferenceIntegerValue((int)swUserPreferenceIntegerValue_e.swDxfVersion,8);sw.SetUserPreferenceIntegerValue((int)swUserPreferenceIntegerValue_e.swDxfOutputNoScale,0);sw.SetUserPreferenceIntegerValue((int)swUserPreferenceIntegerValue_e.swDxfMultiSheetOption,0);sw.SetUserPreferenceIntegerValue((int)swUserPreferenceIntegerValue_e.swDxfOutputFonts,1);sw.SetUserPreferenceIntegerValue((int)swUserPreferenceIntegerValue_e.swDxfOutputLineStyles,0);sw.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swDxfMapping,false);sw.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swDxfExportAllSheetsToPaperSpace,false);
   report["export_native_snapshot"]=NativeInventory(drawing);report["export_active_path"]=((IModelDoc2)sw.ActiveDoc).GetPathName();
   Directory.CreateDirectory(Path.GetDirectoryName(dwg));Require(drawing.Extension.SaveAs3(dwg,0,1,null,null,ref e,ref w)&&e==0&&File.Exists(dwg),"DWG export failed: "+e);report["dwg_sha256"]=Hash(dwg);report["dwg_warning"]=w;report["native_sha256"]=Hash(native);
   foreach(string extension in new[]{".err",".log"}){string extra=Path.ChangeExtension(dwg,extension);if(File.Exists(extra)){string diagnostic=Path.Combine(Path.GetDirectoryName(native),"dwg_export"+extension);Require(!File.Exists(diagnostic),"Existing diagnostic refused");File.Move(extra,diagnostic);report["dwg_diagnostic"+extension]=diagnostic;}}
   report["dwg"]=dwg;report["status"]="DWG_EXPORTED";
  }catch(Exception ex){report["error"]=ex.ToString();}
  finally{
   try{foreach(var kv in originalSettings)sw.SetUserPreferenceIntegerValue(kv.Key,kv.Value);foreach(var kv in toggles)sw.SetUserPreferenceToggle(kv.Key,kv.Value);if(originalScaleFactor.HasValue)sw.SetUserPreferenceDoubleValue((int)swUserPreferenceDoubleValue_e.swDxfOutputScaleFactor,originalScaleFactor.Value);report["settings_restored"]=true;}catch(Exception ex){report["restore_error"]=ex.Message;report["status"]="FAILED";}
   try{if(ownsNative&&drawing!=null){sw.CloseDoc(drawing.GetTitle());report["export_native_closed"]=true;}}catch(Exception ex){report["cleanup_error"]=ex.Message;report["status"]="FAILED";}ReleaseSessionReferences();
  }
  return report;
 }
}
