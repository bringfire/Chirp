"""Regenerate a component with awkward pin names and run the compiled C# helper tests.

Requires Rhino 8 (RhinoCommon/Grasshopper assemblies) and the .NET SDK. The
generated script is rebased onto the local stub so it compiles outside Rhino;
RhinoCode does the same rebase at runtime (onto Grasshopper1ScriptInstance).

    python tools/csharp-helper-tests/run.py
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))

from chirp.rook_tool import chirp_create  # noqa: E402

result = chirp_create(
    pins_in=["Brief:string"],
    # Output names chosen to collide with store keys and entry keys when snake_cased.
    pins_out=["I1:int", "Body:string", "Count:int", "Span:float"],
    signature="brief -> i1, body, count, span",
    category="planner",
    port=9977,
)
script = result["script"]
io.open(os.path.join(HERE, "Script.cs"), "w", encoding="utf-8").write(script)
print("generated Script.cs:", len(script), "chars; outputs", [p["name"] for p in result["pins_out"]])

proc = subprocess.run(["dotnet", "run", "--project", os.path.join(HERE, "HelperTests.csproj"), "-v", "q", "--nologo"], cwd=HERE)
sys.exit(proc.returncode)
