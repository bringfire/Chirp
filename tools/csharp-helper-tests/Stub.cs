// Stand-in for RhinoCode's Grasshopper1ScriptInstance so a generated component
// compiles outside Rhino. Only the members the generated script touches exist;
// the helper tests never construct an instance.
using Grasshopper.Kernel;

public abstract class GH_ScriptInstance
{
    public IGH_Component Component;
    public int Iteration;

    protected void Print(string text) { }

    protected void AddRuntimeMessage(GH_RuntimeMessageLevel level, string text) { }
}
