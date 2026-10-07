using System;
using System.IO;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static partial class DrawingEngine {
 static ISldWorks sw; static IModelDoc2 drawing; static IDrawingDoc dr;
 static Dictionary<string,IView> views; static Dictionary<string,object> bindings;
 public static void ReleaseSessionReferences(){views=null;bindings=null;dr=null;drawing=null;sw=null;measureEnvelopes=false;}
 static Dictionary<string,object> D(params object[] a){var r=new Dictionary<string,object>();for(int i=0;i<a.Length;i+=2)r[(string)a[i]]=a[i+1];return r;}
 static object[] A(object o){return o as object[]??new object[0];}
 static Dictionary<string,object> Map(object o){return (Dictionary<string,object>)o;}
 static object[] Rows(object o){var a=o as object[];if(a!=null)return a;var b=o as IEnumerable;if(b==null||o is string)return new object[0];var rows=new List<object>();foreach(var item in b)rows.Add(item);return rows.ToArray();}
 static object[] OptionalRows(Dictionary<string,object> o,string key){return o.ContainsKey(key)?Rows(o[key]):new object[0];}
 static string S(Dictionary<string,object> m,string k){return Convert.ToString(m[k]);}
 static double N(Dictionary<string,object> m,string k){return Convert.ToDouble(m[k]);}
 static double[] Vec(object o){var a=Rows(o);var r=new double[a.Length];for(int i=0;i<a.Length;i++)r[i]=Convert.ToDouble(a[i]);return r;}
 static JavaScriptSerializer Serializer(){var s=new JavaScriptSerializer();s.MaxJsonLength=int.MaxValue;s.RecursionLimit=200;return s;}
 static Dictionary<string,object> Read(string p){return Map(Serializer().DeserializeObject(File.ReadAllText(p)));}
 public static string Hash(string p){using(var h=SHA256.Create())using(var f=new FileStream(p,FileMode.Open,FileAccess.Read,FileShare.ReadWrite))return BitConverter.ToString(h.ComputeHash(f)).Replace("-","").ToLowerInvariant();}
 static string SharedReadHash(string p){using(var h=SHA256.Create())using(var f=new FileStream(p,FileMode.Open,FileAccess.Read,FileShare.ReadWrite))return BitConverter.ToString(h.ComputeHash(f)).Replace("-","").ToLowerInvariant();}
 static void Require(bool ok,string message){if(!ok)throw new Exception(message);}
 static void Position(object o,double width,double height){var p=Vec(o);Require(p.Length==2&&Finite(p[0])&&Finite(p[1])&&p[0]>0&&p[0]<width&&p[1]>0&&p[1]<height,"Invalid/out-of-sheet position");}
 static bool Finite(double n){return !double.IsNaN(n)&&!double.IsInfinity(n);}
 static void Positive(double n){Require(Finite(n)&&n>0,"Invalid positive size/scale");}
 static void Text(Dictionary<string,object> m,string k){Require(!string.IsNullOrWhiteSpace(S(m,k)),"Missing text: "+k);}
 static IModelDoc2 Source(string path,string cfg,out bool wasOpen,out string oldCfg){
  wasOpen=sw.GetOpenDocumentByName(path)!=null;int e=0,w=0;
  var model=wasOpen?(IModelDoc2)sw.GetOpenDocumentByName(path):(IModelDoc2)sw.OpenDoc6(path,1,3,cfg,ref e,ref w);
  Require(model!=null,"Open source failed: "+e);Require(model.GetType()==1,"Only part documents supported");
  Require(string.Equals(Path.GetFullPath(model.GetPathName()),Path.GetFullPath(path),StringComparison.OrdinalIgnoreCase),"Unexpected source identity");
  oldCfg=model.ConfigurationManager.ActiveConfiguration.Name;
  Require(!model.GetSaveFlag(),"Source has unsaved changes: save it manually before inspection/execution");
  if(!string.IsNullOrEmpty(cfg)&&oldCfg!=cfg)Require(model.ShowConfiguration2(cfg),"Unknown configuration");
  return model;
 }
 static void Restore(IModelDoc2 model,bool wasOpen,string oldCfg){
  if(model==null)return;
  if(wasOpen){if(model.ConfigurationManager.ActiveConfiguration.Name!=oldCfg)model.ShowConfiguration2(oldCfg);}
  else sw.CloseDoc(model.GetTitle());
 }
 public static Dictionary<string,object> Inspect(string path,string cfg){
  sw=(ISldWorks)Marshal.GetActiveObject("SldWorks.Application");
  if(string.IsNullOrEmpty(path)){var active=(IModelDoc2)sw.ActiveDoc;Require(active!=null&&active.GetType()==1,"Active document must be a saved part, or supply Source explicitly");path=active.GetPathName();}
  Require(Path.IsPathRooted(path)&&File.Exists(path),"Saved absolute source path required");
  bool wasOpen=false;string oldCfg="";IModelDoc2 model=null;string before=Hash(path);
  try{
   model=Source(path,cfg,out wasOpen,out oldCfg);cfg=model.ConfigurationManager.ActiveConfiguration.Name;
   var facts=Map(InspectGeometry.Run(path,cfg,"source"));
   facts["schema_version"]=2;facts["document_type"]="part";facts["sha256"]=before;
   facts["solidworks_revision"]=sw.RevisionNumber();facts["model_views"]=model.GetModelViewNames();
   facts["material_name"]=model.MaterialUserName;
   var bb=(double[])facts["bounds_si"];var mm=new double[6];for(int i=0;i<6;i++)mm[i]=bb[i]*1000;facts["bounds_mm"]=mm;
   Require(Finite(mm[0]),"No solid bodies found");facts["status"]="INSPECTED";
   AddFacts(facts);Require(Hash(path)==before,"Source file changed during inspection");return facts;
  }finally{Restore(model,wasOpen,oldCfg);}
 }
 static Dictionary<int,Dictionary<string,object>> Edges(Dictionary<string,object> facts){var r=new Dictionary<int,Dictionary<string,object>>();foreach(var eo in Rows(facts["edges"])){var e=Map(eo);r.Add(Convert.ToInt32(e["id"]),e);}return r;}
 static void Validate(Dictionary<string,object> p,Dictionary<string,object> f){
  Require(Convert.ToInt32(p["version"])==2&&Convert.ToInt32(f["schema_version"])==2&&S(f,"document_type")=="part","Unsupported schema");
  Require(File.Exists(S(p,"template"))&&S(p,"template").EndsWith(".drwdot",StringComparison.OrdinalIgnoreCase),"Template missing");
  Require(Path.IsPathRooted(S(p,"output_drawing"))&&S(p,"output_drawing").EndsWith(".slddrw",StringComparison.OrdinalIgnoreCase)&&!File.Exists(S(p,"output_drawing")),"Output drawing must be a new absolute SLDDRW path");
  if(p.ContainsKey("output_pdf"))Require(Path.IsPathRooted(S(p,"output_pdf"))&&S(p,"output_pdf").EndsWith(".pdf",StringComparison.OrdinalIgnoreCase)&&!File.Exists(S(p,"output_pdf")),"PDF path must be new and absolute");
  var sh=Map(p["sheet"]);double w=N(sh,"width_mm"),h=N(sh,"height_mm");Positive(w);Positive(h);Require(sh["first_angle"] is bool,"Projection convention missing");
  var known=new HashSet<string>();foreach(var v in Rows(f["model_views"]))known.Add(Convert.ToString(v));var ids=new HashSet<string>();
  Require(Rows(p["views"]).Length>0,"No model views");
  foreach(var o in Rows(p["views"])){var v=Map(o);Text(v,"id");Require(ids.Add(S(v,"id")),"Duplicate view ID");Require(known.Contains(S(v,"model_view")),"Unknown model view");Position(v["position_mm"],w,h);Positive(N(v,"scale"));Text(v,"reason");}
  foreach(var o in Rows(p["sections"])){var s=Map(o);Require(ids.Contains(S(s,"parent")),"Unknown section parent");Text(s,"id");Require(ids.Add(S(s,"id")),"Duplicate section ID");Text(s,"label");Position(s["position_mm"],w,h);Positive(N(s,"scale"));Text(s,"reason");var ends=Rows(s["line_model_mm"]);Require(ends.Length==2,"Need two section endpoints");var a=Vec(ends[0]);var b=Vec(ends[1]);Require(a.Length==3&&b.Length==3,"Need 3D endpoints");double len=0;for(int i=0;i<3;i++){Require(Finite(a[i])&&Finite(b[i]),"Nonfinite endpoint");len+=(a[i]-b[i])*(a[i]-b[i]);}Require(len>1e-6,"Degenerate section");}
  foreach(var o in Rows(p["dimensions"])){var d=Map(o);Require(ids.Contains(S(d,"view")),"Unknown dimension view");Require(S(d,"direction")=="horizontal"||S(d,"direction")=="vertical","Unsupported dimension direction");Position(d["position_mm"],w,h);Positive(N(d,"expected_mm"));Text(d,"evidence");}
  var edges=Edges(f);
  foreach(var o in Rows(p["labels"])){var t=Map(o);Require(ids.Contains(S(t,"view")),"Unknown label view");int id=Convert.ToInt32(t["edge_id"]);Require(edges.ContainsKey(id)&&S(edges[id],"type")=="circle"&&!string.IsNullOrEmpty(S(edges[id],"persist_ref")),"Invalid circular edge reference");Text(t,"text");var offset=Vec(t["offset_mm"]);Require(offset.Length==2&&Finite(offset[0])&&Finite(offset[1]),"Invalid label offset");}
  foreach(var o in OptionalRows(p,"diameters")){var t=Map(o);Require(ids.Contains(S(t,"view")),"Unknown diameter view");int id=Convert.ToInt32(t["edge_id"]);Require(edges.ContainsKey(id)&&S(edges[id],"type")=="circle","Invalid diameter edge");Position(t["position_mm"],w,h);Positive(N(t,"expected_mm"));Text(t,"evidence");Require(Math.Abs(Vec(edges[id]["parameters_si"])[6]*2000-N(t,"expected_mm"))<1e-5,"Diameter differs from source circle");}
  foreach(var o in Rows(p["tables"])){var t=Map(o);Position(t["position_mm"],w,h);Text(t,"evidence");Require(S(t,"role")=="nominal_hole_schedule"||S(t,"role")=="nominal_feature_schedule","Unsupported table role");Positive(N(t,"row_height_mm"));var widths=Vec(t["column_widths_mm"]);var rows=Rows(t["rows"]);Require(widths.Length>0&&rows.Length>0,"Empty table");double total=0;foreach(double x in widths){Positive(x);total+=x;}foreach(var row in rows){Require(Rows(row).Length==widths.Length,"Unequal table cells");foreach(var cell in Rows(row))Require(cell is string,"Table cell must be string");}var pos=Vec(t["position_mm"]);Require(pos[0]+total<w&&pos[1]-rows.Length*N(t,"row_height_mm")>0,"Table exceeds sheet");}
  Require(OptionalRows(p,"details").Length==0&&!p.ContainsKey("dimension_scheme")&&!p.ContainsKey("style")&&!p.ContainsKey("export"),"Unsupported detail/scheme/style/export operation");
  foreach(string key in new[]{"linear","radial"})foreach(var o in OptionalRows(p,key)){var q=Map(o);Text(q,"id");Text(q,"evidence");Require(ids.Contains(S(q,"view")),"Unknown experimental view");Position(q["position_mm"],w,h);bool angular=key=="linear"&&S(q,"direction")=="angular";if(key=="linear")Require(new[]{"horizontal","vertical","angular"}.Contains(S(q,"direction")),"Invalid experimental direction");Positive(N(q,angular?"expected_deg":"expected_mm"));foreach(string field in key=="linear"?new[]{"a_edge","b_edge"}:new[]{"edge_id"}){int eid=Convert.ToInt32(q[field]);Require(edges.ContainsKey(eid)&&!String.IsNullOrEmpty(S(edges[eid],"persist_ref"))&&(key=="linear"?new[]{"line","circle"}.Contains(S(edges[eid],"type")):S(edges[eid],"type")=="circle"),"Invalid experimental edge");}if(key=="linear")Require(Convert.ToInt32(q["a_edge"])!=Convert.ToInt32(q["b_edge"]),"Distinct edges required");}
  foreach(var o in Rows(p["notes"])){var n=Map(o);Position(n["position_mm"],w,h);Text(n,"text");Require(!n.ContainsKey("font_mm"),"Note font overrides unsupported; inherit selected template");}
 }
 static double[] Project(IView v,double[] xyz){var mu=(IMathUtility)sw.GetMathUtility();return (double[])((IMathPoint)((IMathPoint)mu.CreatePoint(xyz)).MultiplyTransform(v.ModelToViewTransform)).ArrayData;}
 static void TemplateFont(IAnnotation a){Require(a.SetTextFormat(0,true,a.GetTextFormat(0)),"Template annotation text format failed");}
 static void Bind(string id,IAnnotation a,string view){if(bindings==null)return;bindings[id]=D("annotation_name",a.GetName(),"view",view,"position",a.GetPosition());}
 static bool MatchesBinding(IAnnotation annotation,Dictionary<string,object> binding){
  if(annotation.GetName()!=S(binding,"annotation_name"))return false;
  if(!binding.ContainsKey("dimension_name"))return true;
  var dd=annotation.GetSpecificAnnotation() as IDisplayDimension;
  return dd!=null&&String.Join("@",((IDimension)dd.GetDimension2(0)).FullName.Split('@').Take(2))==S(binding,"dimension_name");
 }
 static void SaveBindings(Dictionary<string,object> report){
  report["native_bindings"]=bindings;
  var index=new Dictionary<string,List<IAnnotation>>();for(var v=(IView)dr.GetFirstView();v!=null;v=(IView)v.GetNextView()){string scope=String.IsNullOrEmpty(v.GetReferencedModelName())?"":v.Name;foreach(var kv in AnnotationIndex(v)){string key=scope+"\u001e"+kv.Key;if(!index.ContainsKey(key))index[key]=new List<IAnnotation>();index[key].AddRange(kv.Value);}}
  foreach(var entry in bindings){var binding=Map(entry.Value);string key=S(binding,"view")+"\u001e"+BindingKey(binding);var matches=index.ContainsKey(key)?index[key]:new List<IAnnotation>();Require(matches.Count==1,"Native annotation identity is not unique: "+entry.Key+" view="+S(binding,"view")+" annotation="+S(binding,"annotation_name")+" matches="+matches.Count);binding["position"]=matches[0].GetPosition();}
  var property=drawing.Extension.get_CustomPropertyManager("");Require(property.Add3("_DraftingBindings",30,Serializer().Serialize(bindings),2)==0,"Save native annotation identities failed");report["native_bindings"]=bindings;
 }
 static object ReadBindings(){string raw="",resolved="";bool wasResolved=false,linked=false;drawing.Extension.get_CustomPropertyManager("").Get6("_DraftingBindings",false,out raw,out resolved,out wasResolved,out linked);Require(!String.IsNullOrEmpty(raw),"Saved semantic annotation mapping missing");return Serializer().DeserializeObject(raw);}
 static INote Note(string text,double[] pos){drawing.ClearSelection2(true);var n=(INote)drawing.InsertNote(text);Require(n!=null,"InsertNote failed");var a=(IAnnotation)n.GetAnnotation();Require(a.SetPosition2(pos[0]/1000,pos[1]/1000,0),"Note position failed");TemplateFont(a);return n;}
 static IView ModelView(Dictionary<string,object> v,string source,string cfg){var pos=Vec(v["position_mm"]);var result=(IView)dr.CreateDrawViewFromModelView3(source,S(v,"model_view"),pos[0]/1000,pos[1]/1000,0);Require(result!=null,"Model view creation failed");Require(result.SetName2(S(v,"id")),"Stable view name failed");result.ReferencedConfiguration=cfg;result.UseSheetScale=0;result.ScaleDecimal=N(v,"scale");result.SetDisplayMode3(false,2,false,false);result.SetDisplayTangentEdges2(0);return result;}
 static IView Section(Dictionary<string,object> s){
  var parent=views[S(s,"parent")];Require(dr.ActivateView(parent.Name),"Activate section parent failed");drawing.ClearSelection2(true);
  var ends=Rows(s["line_model_mm"]);var mu=(IMathUtility)sw.GetMathUtility();var tf=((ISketch)parent.GetSketch()).ModelToSketchTransform;var pts=new double[2][];
  for(int i=0;i<2;i++){var xyz=Vec(ends[i]);for(int j=0;j<3;j++)xyz[j]/=1000;var sheet=Project(parent,xyz);pts[i]=(double[])((IMathPoint)((IMathPoint)mu.CreatePoint(sheet)).MultiplyTransform(tf)).ArrayData;}
  Require(Math.Abs(pts[0][0]-pts[1][0])+Math.Abs(pts[0][1]-pts[1][1])>1e-9,"Cut line collapses in selected view");
  var seg=(ISketchSegment)drawing.SketchManager.CreateLine(pts[0][0],pts[0][1],0,pts[1][0],pts[1][1],0);Require(seg!=null,"Section line failed");drawing.ClearSelection2(true);Require(seg.Select4(false,null),"Select section line failed");
  var pos=Vec(s["position_mm"]);var sec=(IView)dr.CreateSectionViewAt5(pos[0]/1000,pos[1]/1000,0,S(s,"label"),1,null,0);Require(sec!=null,"Section creation failed");Require(sec.SetName2(S(s,"id")),"Stable section name failed");sec.UseParentScale=false;sec.UseSheetScale=0;sec.ScaleDecimal=N(s,"scale");return sec;
 }
 static Dictionary<string,object> Dimension(Dictionary<string,object> spec){
  var view=views[S(spec,"view")];Require(dr.ActivateView(view.Name),"Activate dimension view failed");drawing.ClearSelection2(true);int axis=S(spec,"direction")=="horizontal"?0:1;
  IVertex low=null,high=null;double[] lp=null,hp=null;
  foreach(var co in A(view.GetVisibleComponents()))foreach(var vo in A(view.GetVisibleEntities2((Component2)co,2))){var vertex=vo as IVertex;if(vertex==null)continue;var pos=Project(view,(double[])vertex.GetPoint());if(low==null||pos[axis]<lp[axis]-1e-9||(Math.Abs(pos[axis]-lp[axis])<1e-9&&pos[1-axis]<lp[1-axis])){low=vertex;lp=pos;}if(high==null||pos[axis]>hp[axis]+1e-9||(Math.Abs(pos[axis]-hp[axis])<1e-9&&pos[1-axis]<hp[1-axis])){high=vertex;hp=pos;}}
  Require(low!=null&&high!=null&&Math.Abs(lp[axis]-hp[axis])>1e-9,"No usable overall vertices");
  var sd=(ISelectData)((ISelectionMgr)drawing.SelectionManager).CreateSelectData();sd.View=(View)view;Require(((IEntity)low).Select4(false,(SelectData)sd)&&((IEntity)high).Select4(true,(SelectData)sd),"Dimension vertex selection failed");
  var xy=Vec(spec["position_mm"]);var dd=(IDisplayDimension)(axis==0?drawing.AddHorizontalDimension2(xy[0]/1000,xy[1]/1000,0):drawing.AddVerticalDimension2(xy[0]/1000,xy[1]/1000,0));Require(dd!=null,"Associated dimension failed");
  double actual=((IDimension)dd.GetDimension2(0)).SystemValue*1000;Require(Math.Abs(actual-N(spec,"expected_mm"))<1e-5,"Dimension mismatch: "+actual+" expected "+N(spec,"expected_mm"));TemplateFont((IAnnotation)dd.GetAnnotation());Bind(S(spec,"id"),(IAnnotation)dd.GetAnnotation(),S(spec,"view"));drawing.ClearSelection2(true);
  return D("view",S(spec,"view"),"direction",S(spec,"direction"),"expected_mm",N(spec,"expected_mm"),"actual_mm",actual,"status","PASS");
 }
 static IEdge VisibleCircle(Dictionary<string,object> tag,Dictionary<int,Dictionary<string,object>> edges,IModelDoc2 source){
  var v=views[S(tag,"view")];var edgeFact=edges[Convert.ToInt32(tag["edge_id"])];int error=0;var target=source.Extension.GetObjectByPersistReference3(Convert.FromBase64String(S(edgeFact,"persist_ref")),out error) as IEdge;Require(target!=null&&error==0,"Persistent edge reference cannot resolve");
  var targetRef=S(edgeFact,"persist_ref");IEdge visible=null;var targetParams=(double[])((ICurve)target.GetCurve()).CircleParams;var geometricMatches=new List<IEdge>();
  foreach(var co in A(v.GetVisibleComponents()))foreach(var eo in A(v.GetVisibleEntities2((Component2)co,1))){var ed=eo as IEdge;if(ed==null)continue;var data=source.Extension.GetPersistReference3(ed) as byte[];if(data!=null&&Convert.ToBase64String(data)==targetRef)visible=ed;var curve=(ICurve)ed.GetCurve();if(!curve.IsCircle())continue;var cp=(double[])curve.CircleParams;bool same=true;foreach(int i in new[]{0,1,2,6})if(Math.Abs(cp[i]-targetParams[i])>1e-8)same=false;double dot=cp[3]*targetParams[3]+cp[4]*targetParams[4]+cp[5]*targetParams[5];if(Math.Abs(Math.Abs(dot)-1)>1e-7)same=false;if(same)geometricMatches.Add(ed);}
  // Drawing-context edge proxies can have different persistent bytes. Resolve the source
  // object first, then require a unique full 3D circle match (never XY/radius alone).
  if(visible==null){Require(geometricMatches.Count==1,"Ambiguous/missing 3D circle correspondence: "+tag["edge_id"]);visible=geometricMatches[0];}
  Require(visible!=null,"Requested edge is not visible in label view: "+tag["edge_id"]);return visible;
 }
 static Dictionary<string,object> Diameter(Dictionary<string,object> spec,Dictionary<int,Dictionary<string,object>> edges,IModelDoc2 source){
  var v=views[S(spec,"view")];var edge=VisibleCircle(spec,edges,source);Require(dr.ActivateView(v.Name),"Activate diameter view failed");drawing.ClearSelection2(true);var sd=(ISelectData)((ISelectionMgr)drawing.SelectionManager).CreateSelectData();sd.View=(View)v;Require(((IEntity)edge).Select4(false,(SelectData)sd),"Diameter edge selection failed");var pos=Vec(spec["position_mm"]);var dd=(IDisplayDimension)drawing.AddDiameterDimension2(pos[0]/1000,pos[1]/1000,0);Require(dd!=null,"Native diameter creation failed");double actual=((IDimension)dd.GetDimension2(0)).SystemValue*1000;Require(Math.Abs(actual-N(spec,"expected_mm"))<1e-5,"Diameter mismatch: "+actual);TemplateFont((IAnnotation)dd.GetAnnotation());Bind(S(spec,"id"),(IAnnotation)dd.GetAnnotation(),S(spec,"view"));drawing.ClearSelection2(true);return D("view",S(spec,"view"),"direction","diameter","expected_mm",N(spec,"expected_mm"),"actual_mm",actual,"status","PASS");
 }
 static void Label(Dictionary<string,object> tag,Dictionary<int,Dictionary<string,object>> edges,IModelDoc2 source){
  var v=views[S(tag,"view")];var visible=VisibleCircle(tag,edges,source);Require(dr.ActivateView(v.Name),"Activate label view failed");drawing.ClearSelection2(true);
  var sd=(ISelectData)((ISelectionMgr)drawing.SelectionManager).CreateSelectData();sd.View=(View)v;Require(((IEntity)visible).Select4(false,(SelectData)sd),"Label edge selection failed");
  var note=(INote)drawing.InsertNote(S(tag,"text"));Require(note!=null,"Label note failed");var visibleCircle=(double[])((ICurve)visible.GetCurve()).CircleParams;var center=Project(v,new[]{visibleCircle[0],visibleCircle[1],visibleCircle[2]});var offset=Vec(tag["offset_mm"]);var an=(IAnnotation)note.GetAnnotation();Require(an.SetPosition2(center[0]+offset[0]/1000,center[1]+offset[1]/1000,0),"Label position failed");TemplateFont(an);Bind(S(tag,"id"),an,S(tag,"view"));an.SetLeader3(1,0,true,false,false,false);drawing.ClearSelection2(true);
 }
 static void Table(Dictionary<string,object> spec){dr.ActivateView("");drawing.ClearSelection2(true);var rows=Rows(spec["rows"]);var widths=Vec(spec["column_widths_mm"]);var pos=Vec(spec["position_mm"]);var t=(ITableAnnotation)dr.InsertTableAnnotation2(false,pos[0]/1000,pos[1]/1000,1,"",rows.Length,widths.Length);Require(t!=null,"Native general table failed");for(int i=0;i<rows.Length;i++){var cells=Rows(rows[i]);for(int j=0;j<widths.Length;j++)t.Text[i,j]=(string)cells[j];t.SetRowHeight(i,N(spec,"row_height_mm")/1000,0);}for(int j=0;j<widths.Length;j++)t.SetColumnWidth(j,widths[j]/1000,0);var tf=t.GetTextFormat();Require(t.SetTextFormat(true,tf),"Template table text format failed");foreach(var id in Rows(spec["feature_ids"]))Bind("table:"+Convert.ToString(id),(IAnnotation)t.GetAnnotation(),"");}
 static List<object> AnnotationCounts(IModelDoc2 doc){var result=new List<object>();for(var v=(IView)((IDrawingDoc)doc).GetFirstView();v!=null;v=(IView)v.GetNextView()){int n=0,d=0,t=0,dangling=0;foreach(var ao in A(v.GetAnnotations())){var a=(IAnnotation)ao;if(a.GetSpecificAnnotation() is INote)n++;if(a.GetSpecificAnnotation() is IDisplayDimension)d++;if(a.GetSpecificAnnotation() is ITableAnnotation)t++;if(a.IsDangling())dangling++;}result.Add(D("view",v.Name,"notes",n,"dimensions",d,"tables",t,"dangling",dangling));}return result;}
 public static Dictionary<string,object> VerifySaved(string planPath){
  var report=D("status","FAILED","plan",planPath,"visual_review","NOT_CHECKED","manufacturing_release","NOT_APPROVED");
  bool ownsDrawing=false;
  try{
   var p=Read(planPath);measureEnvelopes=p.ContainsKey("layout");var f=Read(S(p,"facts"));string path=S(p,"output_drawing");Require(Path.IsPathRooted(path)&&File.Exists(path),"Saved native drawing required");Require(SharedReadHash(S(f,"path"))==S(f,"sha256"),"Source changed since inspection");string nativeBefore=SharedReadHash(path);
   sw=(ISldWorks)Marshal.GetActiveObject("SldWorks.Application");drawing=sw.GetOpenDocumentByName(path) as IModelDoc2;ownsDrawing=drawing==null;Require(ownsDrawing,"Preexisting drawing preserved: close it or audit an owned copy before reopening");int e=0,w=0;if(ownsDrawing)drawing=sw.OpenDoc6(path,3,1,"",ref e,ref w) as IModelDoc2;Require(drawing!=null&&!drawing.GetSaveFlag(),"Cannot verify an unsaved/modified drawing");dr=(IDrawingDoc)drawing;report["native_baseline"]=NativeInventory(drawing);report["native_bindings"]=ReadBindings();if(p.ContainsKey("layout"))report["envelope_layout"]=ReadLayout(planPath);
   var sourceDoc=sw.GetOpenDocumentByName(S(f,"path")) as IModelDoc2;Require(sourceDoc==null||!sourceDoc.GetSaveFlag(),"Referenced source has unsaved changes");SnapshotReopen(p,report);Require(SharedReadHash(path)==nativeBefore,"Input native drawing changed");Require(SharedReadHash(S(f,"path"))==S(f,"sha256"),"Source changed during verification");report["source_hash_unchanged"]=true;report["native_hash_unchanged"]=true;report["status"]="NATIVE_REOPEN_VERIFIED";
  }catch(Exception ex){report["error"]=ex.Message;}
  finally{if(ownsDrawing&&drawing!=null)try{sw.CloseDoc(drawing.GetTitle());report["verification_drawing_closed"]=true;}catch(Exception ex){report["cleanup_error"]=ex.Message;report["status"]="FAILED";}ReleaseSessionReferences();}
  return report;
 }
 public static Dictionary<string,object> Visibility(string planPath){
  var report=D("status","FAILED","plan",planPath);IModelDoc2 model=null;bool wasOpen=false;string oldCfg="",source="",before="",created="";
  try {
   var p=Read(planPath);measureEnvelopes=p.ContainsKey("layout");var f=Read(S(p,"facts"));Validate(p,f);source=S(f,"path");before=Hash(source);Require(before==S(f,"sha256"),"Source changed: inspect again");
   sw=(ISldWorks)Marshal.GetActiveObject("SldWorks.Application");model=Source(source,S(f,"configuration"),out wasOpen,out oldCfg);
   var sh=Map(p["sheet"]);drawing=(IModelDoc2)sw.NewDocument(S(p,"template"),12,0,0);Require(drawing!=null,"Create preview drawing failed");created=drawing.GetTitle();dr=(IDrawingDoc)drawing;
   var sheet=(ISheet)dr.GetCurrentSheet();PreserveTemplate(p,sheet);
   int err=0;sw.ActivateDoc3(created,false,0,ref err);dr.EditSheet();views=new Dictionary<string,IView>();
   foreach(var o in Rows(p["views"])){var v=Map(o);views.Add(S(v,"id"),ModelView(v,source,S(f,"configuration")));}
   Require(drawing.ForceRebuild3(false),"Preview rebuild failed");
   var results=new List<object>();
   foreach(var kv in views){
    var circles=new List<double[]>();var lines=new List<object>();
    foreach(var co in A(kv.Value.GetVisibleComponents()))foreach(var eo in A(kv.Value.GetVisibleEntities2((Component2)co,1))){var e=eo as IEdge;if(e==null)continue;var c=(ICurve)e.GetCurve();if(c.IsCircle())circles.Add((double[])c.CircleParams);if(c.IsLine()){var a=e.GetStartVertex() as IVertex;var b=e.GetEndVertex() as IVertex;if(a!=null&&b!=null)lines.Add(D("start_si",a.GetPoint(),"end_si",b.GetPoint()));}}
    var matches=new List<object>();
    foreach(var eo in Rows(f["edges"])){var e=Map(eo);if(S(e,"type")!="circle")continue;var target=Vec(e["parameters_si"]);int count=0;
     foreach(var cp in circles){bool same=true;foreach(int i in new[]{0,1,2,6})if(Math.Abs(cp[i]-target[i])>1e-8)same=false;double dot=cp[3]*target[3]+cp[4]*target[4]+cp[5]*target[5];if(Math.Abs(Math.Abs(dot)-1)>1e-7)same=false;if(same)count++;}
     if(count>0)matches.Add(D("edge_id",e["id"],"geometric_matches",count));
    }
    results.Add(D("view",kv.Key,"visible_circle_count",circles.Count,"source_circle_matches",matches,"visible_lines",lines));
   }
   report["views"]=results;report["model_dimension_inventory"]=ModelDimensionInventory(p,null);report["source_hash_unchanged"]=Hash(source)==before;Require(Convert.ToBoolean(report["source_hash_unchanged"]),"Source changed during visibility preview");report["status"]="VISIBILITY_MEASURED";
  }catch(Exception ex){report["error"]=ex.Message;}
  finally{if(!String.IsNullOrEmpty(created)&&sw!=null)try{sw.CloseDoc(created);}catch(Exception ex){report["cleanup_error"]=ex.Message;}try{if(sw!=null&&!string.IsNullOrEmpty(source))Restore(sw.GetOpenDocumentByName(source) as IModelDoc2,wasOpen,oldCfg);}catch(Exception ex){report["restore_error"]=ex.Message;report["status"]="FAILED";}ReleaseSessionReferences();}
  return report;
 }
 public static Dictionary<string,object> Execute(string planPath){
  var report=D("status","FAILED","plan",planPath,"visual_review","NOT_CHECKED","manufacturing_release","NOT_APPROVED");IModelDoc2 model=null;bool wasOpen=false,ownsDrawing=false;string oldCfg="",before="",source="";
  try{
   var p=Read(planPath);measureEnvelopes=p.ContainsKey("layout");var f=Read(S(p,"facts"));Validate(p,f);source=S(f,"path");before=Hash(source);Require(before==S(f,"sha256"),"Source changed: inspect again");sw=(ISldWorks)Marshal.GetActiveObject("SldWorks.Application");model=Source(source,S(f,"configuration"),out wasOpen,out oldCfg);
   var sh=Map(p["sheet"]);drawing=(IModelDoc2)sw.NewDocument(S(p,"template"),12,0,0);Require(drawing!=null,"Create drawing failed");ownsDrawing=true;bindings=new Dictionary<string,object>();dr=(IDrawingDoc)drawing;report["created_document_title"]=drawing.GetTitle();LayoutProgress(report,"drawing_created");var sheet=(ISheet)dr.GetCurrentSheet();PreserveTemplate(p,sheet);report["template_preserved"]=true;report["template_format"]=sheet.GetTemplateName();int e=0,w=0;sw.ActivateDoc3(drawing.GetTitle(),false,0,ref e);dr.EditSheet();views=new Dictionary<string,IView>();
   foreach(var o in Rows(p["views"])){var v=Map(o);views.Add(S(v,"id"),ModelView(v,source,S(f,"configuration")));}
   Require(sheet.SetScale(N(Map(Rows(p["views"])[0]),"scale"),1,false,false),"Sheet scale update failed");foreach(var o in Rows(p["sections"])){var s=Map(o);views.Add(S(s,"id"),Section(s));}
   var checks=new List<object>();foreach(var o in Rows(p["dimensions"]))checks.Add(Dimension(Map(o)));report["dimensions"]=checks;
   var edges=Edges(f);foreach(var o in OptionalRows(p,"diameters"))checks.Add(Diameter(Map(o),edges,model));foreach(var o in Rows(p["labels"]))Label(Map(o),edges,model);
   FeatureDimensions(p,edges,model);ImportAnnotations(p,report);foreach(var o in Rows(p["tables"]))Table(Map(o));dr.ActivateView("");foreach(var o in Rows(p["notes"])){var n=Map(o);var note=Note(ResolveScaleText(S(n,"text")),Vec(n["position_mm"]));Bind(S(n,"id"),(IAnnotation)note.GetAnnotation(),"");}drawing.ClearSelection2(true);Require(drawing.ForceRebuild3(false),"Drawing rebuild failed");
   LayoutProgress(report,"annotations_created");Arrange(p);LineHierarchy(p);Require(drawing.ForceRebuild3(false),"Post-arrangement rebuild failed");EnvelopeLayout(p,planPath,report);
   var boxes=new List<object>();var flags=new List<object>();var extents=new Dictionary<string,double[]>();
   foreach(var kv in views){var box=(double[])kv.Value.GetOutline();var mm=new double[4];for(int i=0;i<4;i++)mm[i]=box[i]*1000;extents.Add(kv.Key,mm);boxes.Add(D("view",kv.Key,"outline_mm",mm));if(mm[0]<0||mm[1]<0||mm[2]>N(sh,"width_mm")||mm[3]>N(sh,"height_mm"))flags.Add("Out-of-sheet view: "+kv.Key);}
   var names=new List<string>(extents.Keys);for(int i=0;i<names.Count;i++)for(int j=i+1;j<names.Count;j++){var a=extents[names[i]];var b=extents[names[j]];if(Math.Min(a[2],b[2])>Math.Max(a[0],b[0])&&Math.Min(a[3],b[3])>Math.Max(a[1],b[1]))flags.Add("Possible view overlap: "+names[i]+" / "+names[j]);}
   report["view_bounds"]=boxes;report["layout_flags"]=flags;report["unresolved"]=p["unresolved"];
   LayoutProgress(report,"save_bindings");SaveBindings(report);LayoutProgress(report,"save_native");report["native_baseline"]=NativeInventory(drawing);string output=S(p,"output_drawing");Directory.CreateDirectory(Path.GetDirectoryName(output));bool saved=drawing.Extension.SaveAs(output,0,1,null,ref e,ref w);Require(saved&&e==0&&File.Exists(output),"Native drawing save failed: "+e);report["drawing"]=D("path",output,"status","PASS","warnings",w);
   LayoutProgress(report,"reopen_native");SnapshotReopen(p,report);Require(Hash(source)==before,"Source hash changed");report["source_integrity"]="PASS";report["status"]=flags.Count==0?"NATIVE_VERIFIED_REVIEW_REQUIRED":"NATIVE_VERIFIED_LAYOUT_REVIEW_REQUIRED";
  }catch(Exception ex){report["error"]=ex.Message;}
  finally{try{if(ownsDrawing&&drawing!=null){sw.CloseDoc(drawing.GetTitle());report["generated_drawing_closed"]=true;}if(sw!=null&&!string.IsNullOrEmpty(source))Restore(sw.GetOpenDocumentByName(source) as IModelDoc2,wasOpen,oldCfg);}catch(Exception ex){report["restore_error"]=ex.Message;report["error"]=ex.Message;report["status"]="FAILED";}if(!string.IsNullOrEmpty(before)&&File.Exists(source))report["source_hash_unchanged"]=Hash(source)==before;ReleaseSessionReferences();}
  return report;
 }
}
