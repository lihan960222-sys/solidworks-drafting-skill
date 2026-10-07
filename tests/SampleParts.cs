using System;using System.IO;using System.Runtime.InteropServices;using SolidWorks.Interop.sldworks;
public static class SampleParts {
 public static string Create(string template,string output,string family){
  if(File.Exists(output))throw new Exception("Existing sample refused");
  var sw=(ISldWorks)Marshal.GetActiveObject("SldWorks.Application");var doc=(IModelDoc2)sw.NewDocument(template,0,0,0);if(doc==null)throw new Exception("Part template unavailable");
  try {
   var plane=(IFeature)doc.FirstFeature();while(plane!=null&&plane.GetTypeName2()!="RefPlane")plane=(IFeature)plane.GetNextFeature();if(plane==null)throw new Exception("No reference plane");
   plane.Select2(false,0);doc.SketchManager.InsertSketch(true);
   if(family=="shaft")doc.SketchManager.CreateCircleByRadius(0,0,0,.015);
   else if(family=="bracket"){doc.SketchManager.CreateLine(0,0,0,.06,0,0);doc.SketchManager.CreateLine(.06,0,0,.06,.012,0);doc.SketchManager.CreateLine(.06,.012,0,.012,.012,0);doc.SketchManager.CreateLine(.012,.012,0,.012,.05,0);doc.SketchManager.CreateLine(.012,.05,0,0,.05,0);doc.SketchManager.CreateLine(0,.05,0,0,0,0);}
   else doc.SketchManager.CreateCornerRectangle(-.04,-.025,0,.04,.025,0);
   doc.SketchManager.InsertSketch(true);
   var boss=(IFeature)doc.FeatureManager.FeatureExtrusion3(true,false,false,0,0,family=="shaft"?.07:.02,0,false,false,false,false,0,0,false,false,false,false,true,true,true,0,0,false);if(boss==null)throw new Exception("Sample extrusion failed");boss.Name="SampleBody";
   if(family=="plate"){
    doc.ClearSelection2(true);plane.Select2(false,0);doc.SketchManager.InsertSketch(true);
    foreach(double x in new[]{-.025,0,.025})foreach(double y in new[]{-.012,.012})doc.SketchManager.CreateCircleByRadius(x,y,0,.003);
    doc.SketchManager.InsertSketch(true);var cut=(IFeature)doc.FeatureManager.FeatureCut4(true,false,true,1,0,.02,0,false,false,false,false,0,0,false,false,false,false,false,true,true,false,false,false,0,0,false,false);if(cut==null)throw new Exception("Sample holes failed");cut.Name="SampleHoles";
   }
   doc.ForceRebuild3(false);int e=0,w=0;Directory.CreateDirectory(Path.GetDirectoryName(output));if(!doc.Extension.SaveAs3(output,0,1,null,null,ref e,ref w)||e!=0)throw new Exception("Sample save failed "+e);return output;
  }finally{sw.CloseDoc(doc.GetTitle());}
 }
}
