"""chirp_create — token-efficient creation of intelligent GH script components.

This is the CodeSpeak parallel: compress the boilerplate of creating an
LLM-embedded script component into a ~100 token tool call. Rook calls
chirp_create with pin definitions, a signature, and a schema, and gets
back either a gh_edit batch or a direct Rook HTTP call.
"""

from __future__ import annotations

import json

# GH C# type mappings: chirp type string → C# type
CSHARP_TYPE_MAP: dict[str, str] = {
    "int": "int",
    "float": "double",
    "double": "double",
    "string": "string",
    "bool": "bool",
    "Point3d": "Point3d",
    "Vector3d": "Vector3d",
    "Plane": "Plane",
    "Line": "Line",
    "Curve": "Curve",
    "Surface": "Surface",
    "Brep": "Brep",
    "Mesh": "Mesh",
    "Box": "Box",
    "Circle": "Circle",
    "Arc": "Arc",
    "Polyline": "Polyline",
}

# Chirp adapter type strings (for the schema dict sent to the adapter)
ADAPTER_TYPE_MAP: dict[str, str] = {
    "int": "int",
    "float": "float",
    "double": "float",
    "string": "string",
    "bool": "bool",
    # GH geometry types → string (descriptive text for LLM)
    "Point3d": "string",
    "Vector3d": "string",
    "Plane": "string",
    "Line": "string",
    "Curve": "string",
    "Surface": "string",
    "Brep": "string",
    "Mesh": "string",
    "Box": "string",
    "Circle": "string",
    "Arc": "string",
    "Polyline": "string",
}

# How to read each C# type from JsonElement
JSON_READ_MAP: dict[str, str] = {
    "int": "GetInt32()",
    "float": "GetDouble()",
    "double": "GetDouble()",
    "string": 'GetString()',
    "bool": "GetBoolean()",
}


def parse_pin(pin_def: str) -> tuple[str, str]:
    """Parse a pin definition like 'UCount:int' into (name, type)."""
    parts = pin_def.split(":")
    if len(parts) != 2:
        raise ValueError(f"Pin must be 'Name:Type', got: {pin_def!r}")
    return parts[0].strip(), parts[1].strip()


def chirp_create(
    pins_in: list[str],
    pins_out: list[str],
    signature: str,
    deterministic_code: str | None = None,
) -> dict:
    """Generate a Chirp-enabled C# script component.

    Args:
        pins_in: Input pin definitions, e.g. ["SurfaceDesc:string", "Intent:string"]
        pins_out: Output pin definitions, e.g. ["UCount:int", "VCount:int", "Grading:float"]
        signature: DSPy signature string, e.g. "surface_description, intent -> u_count, v_count, grading"
        deterministic_code: Optional C# code to run after LLM outputs are assigned.
                           Has access to all input/output fields.

    Returns:
        dict with:
            script: The complete C# source code for the script component
            pins_in: List of {name, type} dicts for input pin configuration
            pins_out: List of {name, type} dicts for output pin configuration
    """
    in_pins = [parse_pin(p) for p in pins_in]
    out_pins = [parse_pin(p) for p in pins_out]

    # Validate input types
    for name, type_str in in_pins:
        if type_str not in CSHARP_TYPE_MAP:
            raise ValueError(f"Unknown input type: {type_str!r} for pin {name!r}")

    # Build schema from output pins
    schema = {}
    for name, type_str in out_pins:
        adapter_type = ADAPTER_TYPE_MAP.get(type_str)
        if adapter_type is None:
            raise ValueError(f"Unknown output type: {type_str!r}")
        schema[_to_snake(name)] = adapter_type

    # Generate the script
    script = _generate_script(in_pins, out_pins, signature, schema, deterministic_code)

    return {
        "script": script,
        "pins_in": [{"name": n, "type": t} for n, t in in_pins],
        "pins_out": [{"name": n, "type": t} for n, t in out_pins],
    }


def _to_snake(name: str) -> str:
    """Convert PascalCase or camelCase to snake_case."""
    result = []
    for i, c in enumerate(name):
        if c.isupper() and i > 0:
            result.append("_")
        result.append(c.lower())
    return "".join(result)


def _generate_script(
    in_pins: list[tuple[str, str]],
    out_pins: list[tuple[str, str]],
    signature: str,
    schema: dict[str, str],
    deterministic_code: str | None,
) -> str:
    """Generate the full C# script body."""
    lines: list[str] = []

    def w(line: str = "") -> None:
        lines.append(line)

    # Usings
    w("using System;")
    w("using System.Collections.Generic;")
    w("using System.Net.Http;")
    w("using System.Text;")
    w("using System.Text.Json;")
    w("using Rhino.Geometry;")
    w()
    w("public class Script_Instance")
    w("{")

    # Input fields
    w("    // === INPUTS ===")
    for name, type_str in in_pins:
        cs_type = CSHARP_TYPE_MAP.get(type_str, "string")
        w(f"    public {cs_type} {name} = {_csharp_default(cs_type)};")
    w()

    # Output fields — geometry types become string (LLM returns text descriptions)
    w("    // === OUTPUTS ===")
    for name, type_str in out_pins:
        if _is_geometry_type(type_str):
            cs_type = "string"
        else:
            cs_type = CSHARP_TYPE_MAP.get(type_str, "string")
        w(f"    public {cs_type} {name} = {_csharp_default(cs_type)};")
    w()

    # HttpClient
    w("    private static readonly HttpClient _client = new HttpClient()")
    w("    {")
    w("        Timeout = TimeSpan.FromSeconds(30)")
    w("    };")
    w()

    # RunScript
    w("    public void RunScript()")
    w("    {")
    w("        try")
    w("        {")

    # Build inputs dict
    w("            var inputs = new Dictionary<string, object>")
    w("            {")
    for i, (name, type_str) in enumerate(in_pins):
        comma = "," if i < len(in_pins) - 1 else ""
        if ADAPTER_TYPE_MAP.get(type_str) == "string" and type_str != "string":
            w(f'                {{ "{_to_snake(name)}", {name}?.ToString() ?? "" }}{comma}')
        else:
            w(f'                {{ "{_to_snake(name)}", {name} }}{comma}')
    w("            };")
    w()

    # Schema
    schema_json = json.dumps(schema).replace('"', '\\"')
    w(f'            var schema = JsonSerializer.Deserialize<Dictionary<string, string>>(')
    w(f'                "{schema_json}");')
    w()

    # Request
    w("            var request = new Dictionary<string, object>")
    w("            {")
    escaped_sig = signature.replace('"', '\\"')
    w(f'                {{ "signature", "{escaped_sig}" }},')
    w('                { "inputs", inputs },')
    w('                { "schema", schema }')
    w("            };")
    w()

    # HTTP call
    w('            var json = JsonSerializer.Serialize(request);')
    w('            var content = new StringContent(json, Encoding.UTF8, "application/json");')
    w()
    w('            var response = _client.PostAsync("http://localhost:9900/chirp/call", content).Result;')
    w('            var body = response.Content.ReadAsStringAsync().Result;')
    w()
    w("            if (!response.IsSuccessStatusCode)")
    w('                throw new Exception($"Chirp error ({response.StatusCode}): {body}");')
    w()

    # Parse outputs
    w("            using var doc = JsonDocument.Parse(body);")
    w('            var outputs = doc.RootElement.GetProperty("outputs");')
    w()
    for name, type_str in out_pins:
        snake = _to_snake(name)
        reader = JSON_READ_MAP.get(type_str, "GetString()")
        w(f'            {name} = outputs.GetProperty("{snake}").{reader};')

    # Deterministic post-processing
    if deterministic_code:
        w()
        w("            // === Deterministic post-processing ===")
        w(f"            {deterministic_code}")

    # Error handling
    w("        }")
    w("        catch (HttpRequestException)")
    w("        {")
    w("            // Adapter not running — leave defaults")
    w("        }")
    w("        catch (Exception ex)")
    w("        {")
    w('            throw new Exception($"Chirp: {ex.Message}");')
    w("        }")
    w("    }")
    w("}")

    return "\n".join(lines) + "\n"


def _is_geometry_type(type_str: str) -> bool:
    """True if this is a GH geometry type (LLM returns string, not actual geometry)."""
    return ADAPTER_TYPE_MAP.get(type_str) == "string" and type_str != "string"


def _csharp_default(cs_type: str) -> str:
    """Return the C# default value literal for a type."""
    defaults = {
        "int": "0",
        "double": "0.0",
        "string": '""',
        "bool": "false",
        "Point3d": "Point3d.Origin",
        "Vector3d": "Vector3d.Zero",
        "Plane": "Plane.WorldXY",
    }
    return defaults.get(cs_type, "null")
