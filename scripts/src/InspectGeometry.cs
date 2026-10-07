using System;
using System.IO;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
public static class InspectGeometry {
 static Dictionary<string,object> D(params object[] a){var r=new Dictionary<string,object>();for(int i=0;i<a.Length;i+=2)r[(string)a[i]]=a[i+1];return r;}
 static object[] A(object o){return o as object[]??new object[0];}
 static List<object> features;
 static HashSet<string> seen;
 static void Walk(IFeature f,bool sub){int n=0;while(f!=null&&n++<10000){if(seen.Add(f.Name+"|"+f.GetTypeName2())){
  var dims=new List<object>();var dd=(IDisplayDimension)f.GetFirstDisplayDimension();int k=0;
  while(dd!=null&&k++<300){var dm=(IDimension)dd.GetDimension2(0);dims.Add(D("name",dm.FullName,"value_si",dm.SystemValue,"display_type",dd.Type2));dd=(IDisplayDimension)f.GetNextDisplayDimension(dd);}
  object definition=null;
  if(f.GetTypeName2()=="HoleWzd"){var hd=f.GetDefinition() as IWizardHoleFeatureData2;if(hd!=null)definition=D("type",hd.Type,"standard",hd.Standard,"standard2",hd.Standard2,"size",hd.FastenerSize,"fastener_type",hd.FastenerType,"diameter_si",hd.Diameter,"tap_drill_diameter_si",hd.TapDrillDiameter,"depth_si",hd.Depth,"thread_depth_si",hd.ThreadDepth,"end_condition",hd.EndCondition,"thread_end_condition",hd.ThreadEndCondition,"thread_class",hd.ThreadClass);}
  if(f.GetTypeName2()=="Chamfer"){var cd=f.GetDefinition() as IChamferFeatureData2;if(cd!=null)definition=D("distance_si",cd.GetEdgeChamferDistance(0),"angle_rad",cd.EdgeChamferAngle,"type",cd.Type);}
  features.Add(D("name",f.Name,"type",f.GetTypeName2(),"has_faces",A(f.GetFaces()).Length>0,"suppressed",f.IsSuppressed(),"error",f.GetErrorCode(),"dimensions",dims,"definition",definition));
  Walk((IFeature)f.GetFirstSubFeature(),true);
 }f=(IFeature)(sub?f.GetNextSubFeature():f.GetNextFeature());}}
 public static object Run(string path,string cfg,string id){
  var sw=(ISldWorks)Marshal.GetActiveObject("SldWorks.Application");int e=0,w=0;bool wasOpen=sw.GetOpenDocumentByName(path)!=null;
  var d=(IModelDoc2)sw.OpenDoc6(path,1,3,cfg,ref e,ref w);if(d==null)throw new Exception("Open part "+e);
  try{
   if(d.ConfigurationManager.ActiveConfiguration.Name!=cfg&&!d.ShowConfiguration2(cfg))throw new Exception("Configuration "+cfg);
   var bodies=new List<object>();var faces=new List<object>();var edges=new List<object>();
   double[] min={double.PositiveInfinity,double.PositiveInfinity,double.PositiveInfinity},max={double.NegativeInfinity,double.NegativeInfinity,double.NegativeInfinity};
   int bi=0,fi=0,ei=0;
   foreach(object o in A(((IPartDoc)d).GetBodies2(0,false))){var b=(IBody2)o;bi++;double[] bb=new double[6];
    for(int ax=0;ax<3;ax++){double x=0,y=0,z=0;double[] v={0,0,0};v[ax]=1;b.GetExtremePoint(v[0],v[1],v[2],out x,out y,out z);max[ax]=Math.Max(max[ax],new[]{x,y,z}[ax]);bb[ax+3]=new[]{x,y,z}[ax];b.GetExtremePoint(-v[0],-v[1],-v[2],out x,out y,out z);min[ax]=Math.Min(min[ax],new[]{x,y,z}[ax]);bb[ax]=new[]{x,y,z}[ax];}
    bodies.Add(D("id",bi,"name",b.Name,"bounds_si",bb,"check_code",b.Check2()));
    foreach(object fo in A(b.GetFaces())){var f=(IFace2)fo;var s=(ISurface)f.GetSurface();fi++;
     string type=s.IsPlane()?"plane":s.IsCylinder()?"cylinder":s.IsCone()?"cone":s.IsSphere()?"sphere":s.IsTorus()?"torus":"freeform";
     object par=s.IsPlane()?s.PlaneParams:s.IsCylinder()?s.CylinderParams:s.IsCone()?s.ConeParams:s.IsSphere()?s.SphereParams:s.IsTorus()?s.TorusParams:null;
     var circles=new List<object>();foreach(object eo in A(f.GetEdges())){var ed=(IEdge)eo;var c=(ICurve)ed.GetCurve();if(c.IsCircle())circles.Add(c.CircleParams);}
     faces.Add(D("id",fi,"body",bi,"type",type,"parameters_si",par,"bounds_si",f.GetBox(),"area_m2",f.GetArea(),"sense",f.FaceInSurfaceSense(),"circles_si",circles));
    }
    foreach(object eo in A(b.GetEdges())){var ed=(IEdge)eo;var c=(ICurve)ed.GetCurve();ei++;var vs=ed.GetStartVertex() as IVertex;var ve=ed.GetEndVertex() as IVertex;
     double t0=0,t1=0;bool closed=false,periodic=false;c.GetEndParams(out t0,out t1,out closed,out periodic);
     object start=vs==null?null:vs.GetPoint(),end=ve==null?null:ve.GetPoint();object tess=null;
     try{if(start!=null&&end!=null)tess=c.GetTessPts(.00001,.002,start,end);}catch{}
     edges.Add(D("id",ei,"body",bi,"type",c.IsLine()?"line":c.IsCircle()?"circle":"curve","parameters_si",c.IsLine()?c.LineParams:c.IsCircle()?c.CircleParams:null,"start_si",start,"end_si",end,"persist_ref",Convert.ToBase64String((byte[])d.Extension.GetPersistReference3(ed)),"tessellation_si",tess,"parameter_start",t0,"parameter_end",t1,"closed",closed));
    }
   }
   features=new List<object>();seen=new HashSet<string>();Walk((IFeature)d.FirstFeature(),false);
   return D("id",id,"path",path,"configuration",cfg,"bounds_si",new[]{min[0],min[1],min[2],max[0],max[1],max[2]},"bodies",bodies,"faces",faces,"edges",edges,"features",features,"open_error",e,"open_warning",w);
  }finally{if(!wasOpen)sw.CloseDoc(d.GetTitle());}
 }
}
