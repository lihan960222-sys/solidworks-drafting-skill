using System;
public static partial class DrawingEngine {
 public static void CheckEnvelopeGeometry(){
  var q=new double[]{0,0,-1,-1, .01,0,0, 0,.01,0, 0,0,0, 0,0,1,1};
  var b=DisplayArcBounds(q);
  Require(Math.Abs(b[0])<1e-6&&Math.Abs(b[1])<1e-6&&Math.Abs(b[2]-10)<1e-6&&Math.Abs(b[3]-10)<1e-6,"Quarter arc envelope was expanded to full circle");
  q[16]=0;b=DisplayArcBounds(q);
  Require(Math.Abs(b[0]+10)<1e-6&&Math.Abs(b[1]+10)<1e-6&&Math.Abs(b[2]-10)<1e-6&&Math.Abs(b[3]-10)<1e-6,"Clockwise major arc extrema missing");
  q[7]=.01;q[8]=0;q[16]=1;b=DisplayArcBounds(q);
  Require(Math.Abs(b[0]+10)<1e-6&&Math.Abs(b[1]+10)<1e-6,"Full circle extrema missing");
 }
}
