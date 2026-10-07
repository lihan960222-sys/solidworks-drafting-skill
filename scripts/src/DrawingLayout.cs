using System;
using System.IO;
using System.Linq;
using System.Diagnostics;
using System.Collections.Generic;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

public static partial class DrawingEngine {
 public static string LayoutPython="python", LayoutPlanner="";
 public static string LayoutProgressPath="";
 static void LayoutProgress(Dictionary<string,object> report,string phase){if(String.IsNullOrEmpty(LayoutProgressPath))return;File.WriteAllText(LayoutProgressPath,Serializer().Serialize(D("phase",phase,"created_document_title",report.ContainsKey("created_document_title")?report["created_document_title"]:"","plan",report["plan"],"time_utc",DateTime.UtcNow.ToString("o"))));}
 static bool measureEnvelopes=false;
 static string BindingKey(Dictionary<string,object> binding){return S(binding,"annotation_name")+(binding.ContainsKey("dimension_name")?"\u001f"+S(binding,"dimension_name"):"");}
 static Dictionary<string,List<IAnnotation>> AnnotationIndex(IView view){var index=new Dictionary<string,List<IAnnotation>>();foreach(var obj in A(view.GetAnnotations())){var a=(IAnnotation)obj;string key=a.GetName();if(!index.ContainsKey(key))index[key]=new List<IAnnotation>();index[key].Add(a);var dd=a.GetSpecificAnnotation() as IDisplayDimension;if(dd!=null){key+="\u001f"+String.Join("@",((IDimension)dd.GetDimension2(0)).FullName.Split('@').Take(2));if(!index.ContainsKey(key))index[key]=new List<IAnnotation>();index[key].Add(a);}}return index;}
 static string ResolveScaleText(string text){foreach(var kv in views)text=text.Replace("{scale:"+kv.Key+"}",kv.Value.ScaleDecimal.ToString("G",System.Globalization.CultureInfo.InvariantCulture));Require(!text.Contains("{scale:"),"Unknown view in scale note");return text;}
 static void UpdateScaleNotes(Dictionary<string,object> p){foreach(var noteSpec in Rows(p["notes"])){var spec=Map(noteSpec);if(!S(spec,"text").Contains("{scale:"))continue;var binding=Map(bindings[S(spec,"id")]);for(var v=(IView)dr.GetFirstView();v!=null;v=(IView)v.GetNextView())foreach(var obj in A(v.GetAnnotations())){var a=(IAnnotation)obj;if(MatchesBinding(a,binding)&&a.GetSpecificAnnotation() is INote)Require(((INote)a.GetSpecificAnnotation()).SetText(ResolveScaleText(S(spec,"text"))),"Scale note update failed");}}}
 static void RescaleBlocks(Dictionary<string,double> scales,Dictionary<string,object> positions,double factor,string frontView){
  foreach(var kv in views){var view=kv.Value;var centre=Vec(view.Position);view.ScaleDecimal=scales[kv.Key]*factor;var index=AnnotationIndex(view);
   foreach(var entry in Rows(positions[kv.Key])){var item=Map(entry);var binding=Map(item["binding"]);var before=Vec(item["position"]);var target=new[]{centre[0]+(before[0]-centre[0])*factor,centre[1]+(before[1]-centre[1])*factor,before[2]};
    var matches=index[BindingKey(binding)];Require(matches.Count==1,"Scaled annotation identity is not unique");var match=matches[0];Require(match.SetPosition2(target[0],target[1],target[2]),"Scaled annotation placement failed");TemplateFont(match);
   }
  }
  Require(((ISheet)dr.GetCurrentSheet()).SetScale(scales[frontView]*factor,1,false,false),"Scaled sheet ratio update failed");
  Require(drawing.ForceRebuild3(false),"Scaled block rebuild failed");
 }
 static void Extend(double[] b,double x,double y){Require(Finite(x)&&Finite(y),"Nonfinite annotation display coordinate");b[0]=Math.Min(b[0],x*1000);b[1]=Math.Min(b[1],y*1000);b[2]=Math.Max(b[2],x*1000);b[3]=Math.Max(b[3],y*1000);}
 static double[] DisplayArcBounds(double[] q){
  Require(q.Length==17,"Unsupported arc display data");var b=new[]{double.PositiveInfinity,double.PositiveInfinity,double.NegativeInfinity,double.NegativeInfinity};
  double[] c={q[10],q[11],q[12]},u={q[4]-q[10],q[5]-q[11],q[6]-q[12]},end={q[7]-q[10],q[8]-q[11],q[9]-q[12]},n={q[13],q[14],q[15]};
  double r=Math.Sqrt(u.Sum(x=>x*x)),nr=Math.Sqrt(n.Sum(x=>x*x));Require(r>0&&nr>0,"Invalid display arc radius/normal");for(int i=0;i<3;i++){u[i]/=r;n[i]/=nr;}
  double[] v={n[1]*u[2]-n[2]*u[1],n[2]*u[0]-n[0]*u[2],n[0]*u[1]-n[1]*u[0]};
  double sweep=Math.Atan2(end.Zip(v,(x,y)=>x*y).Sum(),end.Zip(u,(x,y)=>x*y).Sum());bool ccw=q[16]!=0;double turn=2*Math.PI;
  if(ccw&&sweep<=1e-12)sweep+=turn;else if(!ccw&&sweep>=-1e-12)sweep-=turn;
  var angles=new List<double>{0,sweep};for(int axis=0;axis<2;axis++){double a=Math.Atan2(v[axis],u[axis]);foreach(double candidate in new[]{a,a+Math.PI}){double signed=(candidate%turn+turn)%turn;if(!ccw&&signed>0)signed-=turn;if(ccw?signed<=sweep+1e-10:signed>=sweep-1e-10)angles.Add(signed);}}
  foreach(double a in angles)Extend(b,c[0]+r*(u[0]*Math.Cos(a)+v[0]*Math.Sin(a)),c[1]+r*(u[1]*Math.Cos(a)+v[1]*Math.Sin(a)));return b;
 }
 static double[] AnnotationEnvelope(IAnnotation a){
  var b=new[]{double.PositiveInfinity,double.PositiveInfinity,double.NegativeInfinity,double.NegativeInfinity};
  var data=a.GetDisplayData() as IDisplayData;Require(data!=null,"Annotation display data unavailable: "+a.GetName());
  // Display primitives use absolute sheet coordinates (metres), not annotation offsets.
  for(int i=0;i<data.GetLineCount();i++){var q=Vec(data.GetLineAtIndex2(i));Require(q.Length==10,"Unsupported line display data");Extend(b,q[4],q[5]);Extend(b,q[7],q[8]);}
  for(int i=0;i<data.GetArcCount();i++){var arc=DisplayArcBounds(Vec(data.GetArcAtIndex2(i)));Extend(b,arc[0]/1000,arc[1]/1000);Extend(b,arc[2]/1000,arc[3]/1000);}
  for(int i=0;i<data.GetArrowHeadCount();i++){var q=Vec(data.GetArrowHeadAtIndex(i));Require(q.Length==9,"Unsupported arrow display data");double r=Math.Abs(q[6])+Math.Abs(q[7]);Extend(b,q[0]-r,q[1]-r);Extend(b,q[0]+r,q[1]+r);}
  for(int i=0;i<data.GetTriangleCount();i++){var q=Vec(data.GetTriangleAtIndex(i));Require(q.Length>=9,"Unsupported triangle display data");for(int j=q.Length-9;j<q.Length;j+=3)Extend(b,q[j],q[j+1]);}
  for(int i=0;i<data.GetPolyLineCount();i++){var q=Vec(data.GetPolylineAtIndex2(i));Require(q.Length>=7&&q.Length==7+3*(int)q[6],"Unsupported polyline display data");for(int j=7;j<q.Length;j+=3)Extend(b,q[j],q[j+1]);}
  for(int i=0;i<data.GetPolygonCount();i++){var q=Vec(data.GetPolygonAtIndex(i));Require(q.Length>=5&&q.Length==5+3*(int)q[4],"Unsupported polygon display data");for(int j=5;j<q.Length;j+=3)Extend(b,q[j],q[j+1]);}
  Require(data.GetEllipseCount()==0&&data.GetParabolaCount()==0,"Unsupported curved annotation display primitive");
  for(int i=0;i<data.GetTextCount();i++){
   var pt=Vec(data.GetTextPositionAtIndex(i));double h=data.GetTextHeightAtIndex(i),w=data.GetTextInBoxWidthAtIndex(i),bh=data.GetTextInBoxHeightAtIndex(i);Require(pt.Length>=2&&h>0,"Invalid annotation text display data");
   if(w<=0)w=h*Math.Max(1,data.GetTextAtIndex(i).Length);if(bh<=0)bh=h;
   // Conservative font/descender allowance; ref positions are swTextPosition_e.
   int reference=data.GetTextRefPositionAtIndex(i);double left=0,bottom=0;
   if(reference==2){left=-w/2;bottom=-bh/2;}else if(reference==3){left=-w;bottom=-bh;}else if(reference==4)left=-w;else if(reference==0)bottom=-bh;else if(reference==5){left=-w/2;bottom=-bh;}
   double angle=data.GetTextAngleAtIndex(i),cs=Math.Cos(angle),sn=Math.Sin(angle);
   foreach(double x in new[]{left-h*.15,left+w+h*.15})foreach(double y in new[]{bottom-h*.25,bottom+bh+h*.25})Extend(b,pt[0]+x*cs-y*sn,pt[1]+x*sn+y*cs);
  }
  // Empty decorative annotations do not enlarge the geometry box.
  return Finite(b[0])?b:null;
 }
 static double[] ViewEnvelope(IView view,double padding){
  var box=Vec(view.GetOutline()).Select(x=>x*1000).ToArray();Require(box.Length==4,"View outline unavailable");
  foreach(var obj in A(view.GetAnnotations())){var b=AnnotationEnvelope((IAnnotation)obj);if(b!=null){box[0]=Math.Min(box[0],b[0]);box[1]=Math.Min(box[1],b[1]);box[2]=Math.Max(box[2],b[2]);box[3]=Math.Max(box[3],b[3]);}}
  return new[]{box[0]-padding,box[1]-padding,box[2]+padding,box[3]+padding};
 }
 static void LineHierarchy(Dictionary<string,object> p){
  if(p.ContainsKey("line_hierarchy")&&!Convert.ToBoolean(p["line_hierarchy"]))return;
  foreach(var pair in new[]{new[]{(int)swUserPreferenceIntegerValue_e.swLineFontVisibleEdgesThickness,(int)swLineWeights_e.swLW_THICK},new[]{(int)swUserPreferenceIntegerValue_e.swLineFontDimensionsThickness,(int)swLineWeights_e.swLW_THIN}})
   Require(drawing.Extension.SetUserPreferenceInteger(pair[0],0,pair[1]),"Document line hierarchy failed: "+pair[0]);
  foreach(var view in views.Values)foreach(var obj in A(view.GetAnnotations())){var a=(IAnnotation)obj;if(a.GetSpecificAnnotation() is IDisplayDimension||a.GetSpecificAnnotation() is INote){a.Color=0;a.Width=(int)swLineWeights_e.swLW_THIN;}}
 }
 static object LineHierarchySnapshot(IModelDoc2 doc){return D("visible_edges",doc.Extension.GetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swLineFontVisibleEdgesThickness,0),"dimension_lines",doc.Extension.GetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swLineFontDimensionsThickness,0),"extension_lines",doc.Extension.GetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swDimensionsExtensionLineStyleThickness,0));}
 static void EnvelopeLayout(Dictionary<string,object> p,string planPath,Dictionary<string,object> report){
  if(!p.ContainsKey("layout"))return;
  var options=Map(p["layout"]);double pad=N(options,"padding_mm");string frontView=S(Map(options["orthographic_views"]),"front");var blocks=new Dictionary<string,object>();
  var originalScales=views.ToDictionary(kv=>kv.Key,kv=>kv.Value.ScaleDecimal);var originalPositions=new Dictionary<string,object>();
  foreach(var kv in views){var pos=new List<object>();foreach(var obj in A(kv.Value.GetAnnotations())){var a=(IAnnotation)obj;var dd=a.GetSpecificAnnotation() as IDisplayDimension;if(dd==null&&!(a.GetSpecificAnnotation() is INote))continue;
   var binding=D("annotation_name",a.GetName());if(dd!=null)binding["dimension_name"]=String.Join("@",((IDimension)dd.GetDimension2(0)).FullName.Split('@').Take(2));
   var data=(IDisplayData)a.GetDisplayData();var heights=Enumerable.Range(0,data.GetTextCount()).Select(i=>data.GetTextHeightAtIndex(i)).ToArray();pos.Add(D("binding",binding,"position",a.GetPosition(),"text_heights",heights));
  }originalPositions[kv.Key]=pos;}
  var attempts=new List<object>();report["layout_attempts"]=attempts;Dictionary<string,object> solved=null,request=null,bestSolved=null,bestRequest=null;double factor=1,bestFactor=1,bestScore=double.PositiveInfinity;double targetFill=options.ContainsKey("target_fill")?N(options,"target_fill"):.55;var fillRange=options.ContainsKey("fill_range")?Vec(options["fill_range"]):new[]{.45,.65};
  var factors=options.ContainsKey("scale_factors")?Vec(options["scale_factors"]):new[]{1.0,.95,.9,.85,.8,.75,.625,.5,.375,.25,.2,.125};
  foreach(double trial in factors){factor=trial;LayoutProgress(report,"measure_scale_factor:"+factor);if(factor!=1)RescaleBlocks(originalScales,originalPositions,factor,frontView);
  UpdateScaleNotes(p);
  blocks.Clear();
  foreach(var kv in views)blocks[kv.Key]=D("position_mm",Vec(kv.Value.Position).Take(2).Select(x=>x*1000).ToArray(),"bounds_mm",ViewEnvelope(kv.Value,pad));
  var trialTables=new List<IAnnotation>();var seen=new HashSet<string>();
  for(var v=(IView)dr.GetFirstView();v!=null;v=(IView)v.GetNextView())foreach(var obj in A(v.GetAnnotations())){var a=(IAnnotation)obj;if(a.GetSpecificAnnotation() is ITableAnnotation&&bindings.Values.Any(b=>S(Map(b),"annotation_name")==a.GetName())&&seen.Add(a.GetName()))trialTables.Add(a);}
  Require(trialTables.Count==Rows(p["tables"]).Length,"Measured table identity mismatch");
  var tableSizes=new List<object>();foreach(var a in trialTables){var b=AnnotationEnvelope(a);Require(b!=null,"Table envelope unavailable");tableSizes.Add(new[]{b[2]-b[0],b[3]-b[1]});}
  var trialReserved=OptionalRows(options,"reserved_boxes_mm").ToList();
  // Sheet notes remain fixed obstacles; title/stamp obstacles come from the template plan.
  for(var v=(IView)dr.GetFirstView();v!=null;v=(IView)v.GetNextView())if(String.IsNullOrEmpty(v.GetReferencedModelName()))foreach(var obj in A(v.GetAnnotations())){var a=(IAnnotation)obj;if(a.GetSpecificAnnotation() is INote&&bindings.Values.Any(b=>S(Map(b),"annotation_name")==a.GetName())){var b=AnnotationEnvelope(a);if(b!=null)trialReserved.Add(b);}}
  request=D("blocks",new Dictionary<string,object>(blocks),"first_angle",Map(p["sheet"])["first_angle"],"usable_bounds_mm",options["usable_bounds_mm"],"reserved_boxes_mm",trialReserved,"table_sizes_mm",tableSizes,"gap_mm",options["gap_mm"],"orthographic_views",options["orthographic_views"]);
  Require(File.Exists(LayoutPlanner)&&!LayoutPlanner.Contains('"')&&!LayoutPython.Contains('"'),"Layout planner path unavailable");
  var start=new ProcessStartInfo(LayoutPython,"-X utf8 \""+LayoutPlanner+"\""){UseShellExecute=false,CreateNoWindow=true,RedirectStandardInput=true,RedirectStandardOutput=true,RedirectStandardError=true};
  string json,error;int code;using(var process=Process.Start(start)){process.StandardInput.Write(Serializer().Serialize(request));process.StandardInput.Close();json=process.StandardOutput.ReadToEnd();error=process.StandardError.ReadToEnd();process.WaitForExit();code=process.ExitCode;}
  report["layout_measurement"]=request;attempts.Add(D("scale_factor",factor,"measurement",request,"status",code==0?"FIT":"NO_FIT","error",error));
  if(code==0){var candidate=Map(Serializer().DeserializeObject(json));double fill=N(candidate,"occupied_fraction"),score=Math.Abs(fill-targetFill);if(fill<fillRange[0]||fill>fillRange[1])score+=1;if(score<bestScore){bestScore=score;bestSolved=candidate;bestRequest=request;bestFactor=factor;}if(fill<=targetFill)break;}
  }
  solved=bestSolved;request=bestRequest;if(solved!=null&&factor!=bestFactor){RescaleBlocks(originalScales,originalPositions,bestFactor,frontView);}factor=bestFactor;if(solved!=null)UpdateScaleNotes(p);Require(solved!=null,"Measured annotated blocks do not fit at any allowed scale; fixed text/arrow sizes retained");
  var tableAnnotations=new List<IAnnotation>();var seenTables=new HashSet<string>();for(var v=(IView)dr.GetFirstView();v!=null;v=(IView)v.GetNextView())foreach(var obj in A(v.GetAnnotations())){var a=(IAnnotation)obj;if(a.GetSpecificAnnotation() is ITableAnnotation&&bindings.Values.Any(b=>S(Map(b),"annotation_name")==a.GetName())&&seenTables.Add(a.GetName()))tableAnnotations.Add(a);}
  var reserved=Rows(request["reserved_boxes_mm"]).ToList();var positions=Map(solved["positions_mm"]);
  foreach(var kv in views){var v=kv.Value;var before=Vec(v.Position);var target=Vec(positions[kv.Key]);double dx=target[0]/1000-before[0],dy=target[1]/1000-before[1];
   var annotations=A(v.GetAnnotations()).Select(x=>(IAnnotation)x).ToArray();var old=annotations.Select(a=>Vec(a.GetPosition())).ToArray();
   Require(v.SetViewPosition(new[]{target[0]/1000,target[1]/1000},false),"Move view block failed: "+kv.Key);
   for(int i=0;i<annotations.Length;i++){var now=Vec(annotations[i].GetPosition());if(old[i].Length>=3&&now.Length>=2&&(Math.Abs(now[0]-old[i][0]-dx)>1e-7||Math.Abs(now[1]-old[i][1]-dy)>1e-7))Require(annotations[i].SetPosition2(old[i][0]+dx,old[i][1]+dy,old[i][2]),"Attached annotation did not translate with view: "+annotations[i].GetName());}
  }
  var tablePos=Rows(solved["table_positions_mm"]);for(int i=0;i<tableAnnotations.Count;i++){
   var a=tableAnnotations[i];var b=AnnotationEnvelope(a);var old=Vec(a.GetPosition());var target=Vec(tablePos[i]);Require(a.SetPosition2(old[0]+(target[0]-b[0])/1000,old[1]+(target[1]-b[3])/1000,old[2]),"Move upper-right table failed");
  }
  Require(drawing.ForceRebuild3(false),"Envelope layout rebuild failed");
  var measured=new Dictionary<string,object>();foreach(var kv in views){var target=Vec(positions[kv.Key]);var actual=Vec(kv.Value.Position);Require(Math.Abs(actual[0]*1000-target[0])<.01&&Math.Abs(actual[1]*1000-target[1])<.01,"View alignment constrained requested block move");measured[kv.Key]=ViewEnvelope(kv.Value,pad);}
  var actualTables=new List<object>();foreach(var a in tableAnnotations)actualTables.Add(AnnotationEnvelope(a));
  var usable=Vec(options["usable_bounds_mm"]);var all=measured.Values.Select(Vec).Concat(actualTables.Select(Vec)).ToArray();
  foreach(var b in all){Require(b[0]>=usable[0]-.1&&b[1]>=usable[1]-.1&&b[2]<=usable[2]+.1&&b[3]<=usable[3]+.1,"Actual annotation envelope exceeds usable frame");foreach(var r in reserved.Select(Vec))Require(!RectOverlap(b,r),"Actual annotation envelope overlaps reserved notes/stamp");}
  for(int i=0;i<all.Length;i++)for(int j=i+1;j<all.Length;j++){Require(!RectOverlap(all[i],all[j]),"Actual annotation envelopes overlap after moving blocks");double clearance=Math.Max(Math.Max(all[i][0]-all[j][2],all[j][0]-all[i][2]),Math.Max(all[i][1]-all[j][3],all[j][1]-all[i][3]));Require(clearance>=N(options,"gap_mm")-.1,"Actual block/table clearance below plan standard");}
  foreach(var kv in views){var index=AnnotationIndex(kv.Value);foreach(var obj in Rows(originalPositions[kv.Key])){var item=Map(obj);var binding=Map(item["binding"]);var matches=index[BindingKey(binding)];Require(matches.Count==1,"Final annotation identity is not unique");var a=matches[0];var data=(IDisplayData)a.GetDisplayData();var heights=Vec(item["text_heights"]);Require(heights.Length==data.GetTextCount(),"Scaled annotation text changed");for(int i=0;i<heights.Length;i++)Require(Math.Abs(heights[i]-data.GetTextHeightAtIndex(i))<1e-8,"Annotation font height changed when scaling view");}}
  solved["fill_target"]=targetFill;solved["fill_range"]=fillRange;solved["spacing_mm"]=options["gap_mm"];solved["padding_mm"]=pad;solved["balance_review_required"]=true;solved["scale_changed"]=factor!=1;solved["scale_factor"]=factor;solved["view_scales"]=views.ToDictionary(kv=>kv.Key,kv=>(object)kv.Value.ScaleDecimal);solved["fixed_text_height_verified"]=true;
  solved["actual_bounds_mm"]=measured;solved["actual_table_bounds_mm"]=actualTables;solved["measurement"]=request;solved["plan_sha256"]=Hash(planPath);solved["line_hierarchy"]=LineHierarchySnapshot(drawing);report["envelope_layout"]=solved;
  var property=drawing.Extension.get_CustomPropertyManager("");Require(property.Add3("_DraftingLayout",30,Serializer().Serialize(solved),2)==0,"Save measured layout failed");
 }
 static bool RectOverlap(double[] a,double[] b){return Math.Min(a[2],b[2])>Math.Max(a[0],b[0])+.05&&Math.Min(a[3],b[3])>Math.Max(a[1],b[1])+.05;}
 static object ReadLayout(string planPath){string raw="",resolved="";bool wasResolved=false,linked=false;drawing.Extension.get_CustomPropertyManager("").Get6("_DraftingLayout",false,out raw,out resolved,out wasResolved,out linked);Require(!String.IsNullOrEmpty(raw),"Saved measured layout missing");var layout=Map(Serializer().DeserializeObject(raw));Require(S(layout,"plan_sha256")==Hash(planPath),"Saved layout plan identity changed");return layout;}
}
