"""chirp_create — token-efficient creation of intelligent GH script components.

This is the CodeSpeak parallel: compress the boilerplate of creating an
LLM-embedded script component into a ~100 token tool call. Rook calls
chirp_create with pin definitions, a signature, and a schema, and gets
back either a gh_edit batch or a direct Rook HTTP call.
"""

from __future__ import annotations

import json
import os

# ── Category definitions ─────────────────────────────────────────────────
# Each category defines the DSPy module and prompt strategy used at runtime.
# The adapter reads the category to select the right reasoning approach.

CATEGORIES: dict[str, dict] = {
    "planner": {
        "module": "ChainOfThought",
        "description": "Translates a design brief into structured parameters",
        "prompt_prefix": "You are a design planner. Given a brief, determine appropriate parameters.",
    },
    "interpreter": {
        "module": "ChainOfThought",
        "description": "Reads upstream reasoning through a domain-specific lens",
        "prompt_prefix": "You are a domain specialist interpreting a design reasoning chain. "
                         "If a correction is provided, prioritize it over upstream assumptions "
                         "and explain the reconciliation.",
    },
    "critic": {
        "module": "ChainOfThought",
        "description": "Checks consistency across multiple reasoning streams",
        "prompt_prefix": "You are a design critic evaluating coherence across disciplines. "
                         "Identify contradictions, score overall coherence, and flag conflicts.",
    },
    "narrator": {
        "module": "ChainOfThought",
        "description": "Synthesizes multiple reasoning streams into a design narrative",
        "prompt_prefix": "You are a design narrator. Synthesize the reasoning streams into "
                         "a coherent, presentation-ready design statement.",
    },
    "classifier": {
        "module": "Predict",
        "description": "Classifies data into categories with confidence",
        "prompt_prefix": "Classify the input into the most appropriate category.",
    },
    "gate": {
        "module": "Predict",
        "description": "Activates or deactivates rules based on reasoning",
        "prompt_prefix": "Based on the design reasoning, determine which rules should be active.",
    },
    "editor": {
        "module": "ChainOfThought",
        "description": "Reconciles upstream reasoning with human corrections",
        "prompt_prefix": "You are a design editor. Reconcile the upstream reasoning with "
                         "the human's correction. The correction takes priority. "
                         "Explain what changed and why.",
    },
}

VALID_CATEGORIES = set(CATEGORIES.keys())

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
    category: str,
    name: str | None = None,
    deterministic_code: str | None = None,
    port: int | None = None,
) -> dict:
    """Generate a Chirp-enabled C# script component.

    Args:
        pins_in: Input pin definitions, e.g. ["SurfaceDesc:string", "Intent:string"]
        pins_out: Output pin definitions, e.g. ["UCount:int", "VCount:int", "Grading:float"]
        signature: DSPy signature string, e.g. "surface_description, intent -> u_count, v_count, grading"
        category: Component category — one of: planner, interpreter, critic,
                  narrator, classifier, gate, editor. Determines DSPy module,
                  prompt strategy, and visual treatment.
        name: Optional display name / NickName for the component.
        deterministic_code: Optional C# code to run after LLM outputs are assigned.
                           Has access to all input/output fields.
        port: Chirp adapter port (default: CHIRP_PORT env var or 9900)

    Returns:
        dict with:
            script: The complete C# source code for the script component
            pins_in: List of {name, type} dicts for input pin configuration
            pins_out: List of {name, type} dicts for output pin configuration
            category: The validated category string
            category_info: Category metadata (module, description, prompt_prefix)
    """
    # ── Validate category ────────────────────────────────────────────
    category = category.lower().strip()
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category: {category!r}. "
            f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )
    category_info = CATEGORIES[category]

    if port is None:
        port = int(os.environ.get(
            "_CHIRP_BOUND_PORT", os.environ.get("CHIRP_PORT", "9900")
        ))

    in_pins = [parse_pin(p) for p in pins_in]
    out_pins = [parse_pin(p) for p in pins_out]

    # Validate input types
    for pin_name, type_str in in_pins:
        if type_str not in CSHARP_TYPE_MAP:
            raise ValueError(f"Unknown input type: {type_str!r} for pin {pin_name!r}")

    # Reject reserved output pin names
    for pin_name, _ in out_pins:
        if pin_name.lower() == "reasoning":
            raise ValueError(
                f"Output pin name {pin_name!r} is reserved (auto-added for LLM chain-of-thought). "
                f"Use a different name like 'Rationale' or 'Explanation'."
            )

    # Reject reserved input pin names
    for pin_name, _ in in_pins:
        if pin_name.lower() == "correction":
            raise ValueError(
                f"Input pin name {pin_name!r} is reserved (auto-added for human corrections). "
                f"Use a different name like 'Override' or 'Adjustment'."
            )

    # ── Auto-add Correction input pin ────────────────────────────────
    # Correction is always the last input — human override, optional.
    all_in_pins = list(in_pins) + [("Correction", "string")]

    # Build schema from output pins
    schema = {}
    for pin_name, type_str in out_pins:
        adapter_type = ADAPTER_TYPE_MAP.get(type_str)
        if adapter_type is None:
            raise ValueError(f"Unknown output type: {type_str!r}")
        schema[_to_snake(pin_name)] = adapter_type

    # Generate the script — includes Correction in inputs, Reasoning in outputs
    script = _generate_script(all_in_pins, out_pins, signature, schema, deterministic_code, port, category)

    # Build final pin lists for GH component configuration
    all_out_pins_list = [{"name": n, "type": t} for n, t in out_pins]
    all_out_pins_list.append({"name": "Reasoning", "type": "string"})

    all_in_pins_list = [{"name": n, "type": t} for n, t in in_pins]
    all_in_pins_list.append({"name": "Correction", "type": "string"})

    return {
        "script": script,
        "pins_in": all_in_pins_list,
        "pins_out": all_out_pins_list,
        "category": category,
        "category_info": category_info,
        "name": name or f"Chirp {category.title()}",
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
    port: int,
    category: str = "planner",
) -> str:
    """Generate a GH_ScriptInstance C# script for the RhinoCode C# Script component."""
    lines: list[str] = []

    def w(line: str = "") -> None:
        lines.append(line)

    # Standard RhinoCode usings
    w("using System;")
    w("using System.Collections.Generic;")
    w("using System.Net.Http;")
    w("using System.Text;")
    w("using System.Text.Json;")
    w("using Rhino;")
    w("using Rhino.Geometry;")
    w("using Grasshopper;")
    w("using Grasshopper.Kernel;")
    w()
    w("public class Script_Instance : GH_ScriptInstance")
    w("{")

    # HttpClient as static field
    w("    private static readonly HttpClient _client = new HttpClient()")
    w("    {")
    w("        Timeout = TimeSpan.FromSeconds(30)")
    w("    };")
    w()

    # RunScript with typed parameters
    # Inputs: object params (cast inside). Outputs: ref object params.
    # Correction is always the last input — human override, optional.
    # Reasoning is always the last output — exposes the LLM's chain of thought.
    in_params = ", ".join(f"object {name}" for name, _ in in_pins)
    out_param_list = [f"ref object {name}" for name, _ in out_pins]
    out_param_list.append("ref object Reasoning")
    out_params = ", ".join(out_param_list)
    all_params = ", ".join(filter(None, [in_params, out_params]))
    w(f"    private void RunScript({all_params})")
    w("    {")
    w("        try")
    w("        {")

    # Build inputs dict — cast from object to expected type
    # Correction is included in in_pins but handled specially below
    domain_pins = [(n, t) for n, t in in_pins if n != "Correction"]
    w("            var inputs = new Dictionary<string, object>")
    w("            {")
    for i, (name, type_str) in enumerate(domain_pins):
        comma = "," if i < len(domain_pins) - 1 else ""
        if ADAPTER_TYPE_MAP.get(type_str) == "string" and type_str != "string":
            w(f'                {{ "{_to_snake(name)}", {name}?.ToString() ?? "" }}{comma}')
        else:
            w(f'                {{ "{_to_snake(name)}", {name} ?? (object)"" }}{comma}')
    w("            };")
    w()

    # Correction — only include when non-empty (per-node human override)
    w('            var correctionText = Correction?.ToString() ?? "";')
    w('            if (!string.IsNullOrWhiteSpace(correctionText))')
    w('                inputs["correction"] = correctionText;')
    w()

    # Schema — use verbatim string to avoid escaping issues
    schema_json = json.dumps(schema)
    w(f'            var schema = JsonSerializer.Deserialize<Dictionary<string, string>>(')
    w(f'                @"{schema_json.replace(chr(34), chr(34)+chr(34))}");')
    w()

    # Request — includes category for adapter module/prompt selection
    w("            var request = new Dictionary<string, object>")
    w("            {")
    escaped_sig = signature.replace('"', '""')
    w(f'                {{ "signature", @"{escaped_sig}" }},')
    w('                { "inputs", inputs },')
    w('                { "schema", schema },')
    escaped_cat = category.replace('"', '""')
    w(f'                {{ "category", @"{escaped_cat}" }}')
    w("            };")
    w()

    # HTTP call
    w('            var json = JsonSerializer.Serialize(request);')
    w('            var content = new StringContent(json, Encoding.UTF8, "application/json");')
    w()
    w(f'            var response = _client.PostAsync("http://localhost:{port}/chirp/call", content).Result;')
    w('            var body = response.Content.ReadAsStringAsync().Result;')
    w()
    w("            if (!response.IsSuccessStatusCode)")
    w('                throw new Exception($"Chirp error ({response.StatusCode}): {body}");')
    w()

    # Parse outputs and assign to ref params
    w("            using var doc = JsonDocument.Parse(body);")
    w('            var result = doc.RootElement.GetProperty("outputs");')
    w()
    for name, type_str in out_pins:
        snake = _to_snake(name)
        reader = JSON_READ_MAP.get(type_str, "GetString()")
        # Cast to object for ref assignment
        w(f'            {name} = (object)result.GetProperty("{snake}").{reader};')

    # Reasoning — expose the LLM's chain of thought
    w()
    w('            if (doc.RootElement.TryGetProperty("reasoning", out var reasoningEl)')
    w('                && reasoningEl.ValueKind == JsonValueKind.String)')
    w('                Reasoning = (object)reasoningEl.GetString();')

    # Deterministic post-processing
    if deterministic_code:
        w()
        w("            // === Deterministic post-processing ===")
        w(f"            {deterministic_code}")

    # Error handling
    w("        }")
    w("        catch (HttpRequestException)")
    w("        {")
    w(f'            Print("Chirp: adapter not running on localhost:{port}");')
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
