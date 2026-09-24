"""chirp_create — token-efficient creation of intelligent GH script components.

This is the CodeSpeak parallel: compress the boilerplate of creating an
LLM-embedded script component into a ~100 token tool call. Rook calls
chirp_create with pin definitions, a signature, and a schema, and gets
back either a gh_edit batch or a direct Rook HTTP call.
"""

from __future__ import annotations

import json
import os

from chirp.timeout_policy import GENERATED_CLIENT_TIMEOUT_SECONDS

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


# Universal pins added to every LLM-backed component (see docs/plans/2026-09-23-*).
RESERVED_FROZEN_PINS = frozenset({"freeze", "frozen"})


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
    deterministic_only: bool = False,
    port: int | None = None,
    model: str | None = None,
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
        deterministic_only: Generate a component that runs deterministic_code
                           without calling the Chirp LLM endpoint.
        port: Chirp adapter port (default: CHIRP_PORT env var or 9900)
        model: LiteLLM model string for this component. When set, the generated
               C# script sends the model in every /chirp/call request, overriding
               the adapter's default. E.g. "openai/mercury-2",
               "anthropic/claude-haiku-4-5-20251001".

    Returns:
        dict with:
            script: The complete C# source code for the script component
            pins_in: List of {name, type} dicts for input pin configuration
            pins_out: List of {name, type} dicts for output pin configuration
            category: The validated category string
            category_info: Category metadata (module, description, prompt_prefix)
            model: The model string if set, else None
    """
    # ── Validate category ────────────────────────────────────────────
    category = category.lower().strip()
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category: {category!r}. "
            f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )
    category_info = CATEGORIES[category]
    if deterministic_only and not deterministic_code:
        raise ValueError("deterministic_only requires deterministic_code")

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
        if pin_name.lower() in RESERVED_FROZEN_PINS:
            raise ValueError(
                f"Input pin name {pin_name!r} is reserved (auto-added for frozen results). "
                f"Use a different name like 'Locked' or 'Snapshot'."
            )

    # ── Auto-add universal input pins ────────────────────────────────
    # Correction is always after the domain inputs — human override, optional.
    # LLM components also get Freeze (replay on demand) and Frozen (the snapshot
    # that travels with the .gh file); deterministic-only components never call
    # the model, so they carry neither.
    all_in_pins = list(in_pins) + [("Correction", "string")]
    if not deterministic_only:
        all_in_pins += [("Freeze", "bool"), ("Frozen", "string")]

    # Build schema from output pins
    schema = {}
    for pin_name, type_str in out_pins:
        adapter_type = ADAPTER_TYPE_MAP.get(type_str)
        if adapter_type is None:
            raise ValueError(f"Unknown output type: {type_str!r}")
        schema[_to_snake(pin_name)] = adapter_type

    # Generate the script — includes Correction in inputs, Reasoning in outputs
    script = _generate_script(
        all_in_pins,
        out_pins,
        signature,
        schema,
        deterministic_code,
        port,
        category,
        model,
        deterministic_only=deterministic_only,
    )

    # Build final pin lists for GH component configuration
    all_out_pins_list = [{"name": n, "type": t} for n, t in out_pins]
    all_out_pins_list.append({"name": "Reasoning", "type": "string"})

    all_in_pins_list = [{"name": n, "type": t} for n, t in in_pins]
    all_in_pins_list.append({"name": "Correction", "type": "string"})
    if not deterministic_only:
        all_in_pins_list.append({
            "name": "Freeze",
            "type": "bool",
            "optional": True,
            "description": "True: replay the frozen result and never call the model.",
        })
        all_in_pins_list.append({
            "name": "Frozen",
            "type": "string",
            "optional": True,
            "description": (
                "Frozen result captured after the last successful model call; stored as "
                "persistent data so it travels with the .gh file. Wire a Panel to supply one."
            ),
        })

    return {
        "script": script,
        "pins_in": all_in_pins_list,
        "pins_out": all_out_pins_list,
        "category": category,
        "category_info": category_info,
        "name": name or f"Chirp {category.title()}",
        "model": model,
        "deterministic_only": deterministic_only,
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
    model: str | None = None,
    deterministic_only: bool = False,
) -> str:
    """Generate a GH_ScriptInstance C# script for the RhinoCode C# Script component."""
    lines: list[str] = []

    def w(line: str = "") -> None:
        lines.append(line)

    in_params = ", ".join(f"object {name}" for name, _ in in_pins)
    out_param_list = [f"ref object {name}" for name, _ in out_pins]
    out_param_list.append("ref object Reasoning")
    out_params = ", ".join(out_param_list)
    all_params = ", ".join(filter(None, [in_params, out_params]))

    if deterministic_only:
        w("using System;")
        w("using System.Collections.Generic;")
        w("using Rhino;")
        w("using Rhino.Geometry;")
        w("using Grasshopper;")
        w("using Grasshopper.Kernel;")
        w()
        w("public class Script_Instance : GH_ScriptInstance")
        w("{")
        w(f"    private void RunScript({all_params})")
        w("    {")
        w("        try")
        w("        {")
        w("            // === Deterministic execution ===")
        w('            Reasoning = (object)"deterministic";')
        w(f"            {deterministic_code}")
        w("            return;")
        w("        }")
        w("        catch (Exception ex)")
        w("        {")
        w('            throw new Exception($"Chirp: {ex.Message}");')
        w("        }")
        w("    }")
        w("}")
        return "\n".join(lines) + "\n"

    # Standard RhinoCode usings
    w("using System;")
    w("using System.Collections.Generic;")
    w("using System.Globalization;")
    w("using System.Net;")
    w("using System.Net.Http;")
    w("using System.Text;")
    w("using System.Threading.Tasks;")
    w("using Rhino;")
    w("using Rhino.Geometry;")
    w("using Grasshopper;")
    w("using Grasshopper.Kernel;")
    w("using Grasshopper.Kernel.Parameters;")
    w("using Grasshopper.Kernel.Types;")
    w()
    w("public class Script_Instance : GH_ScriptInstance")
    w("{")
    frozen_index = [n for n, _ in in_pins].index("Frozen")
    w(f"    private const int FrozenPinIndex = {frozen_index};")
    w()

    # HttpClient as static field
    w("    private static readonly HttpClient _client = new HttpClient()")
    w("    {")
    w(f"        Timeout = TimeSpan.FromSeconds({GENERATED_CLIENT_TIMEOUT_SECONDS})")
    w("    };")
    w()

    # RunScript with typed parameters.
    # Inputs: object params (cast inside). Outputs: ref object params.
    # Correction is always the last input; Reasoning is always the last output.
    w(f"    private void RunScript({all_params})")
    w("    {")
    w("        try")
    w("        {")

    # Build inputs dict — cast from object to expected type
    # Correction is included in in_pins but handled specially below
    domain_pins = [(n, t) for n, t in in_pins if n != "Correction" and n.lower() not in RESERVED_FROZEN_PINS]
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

    # Schema — generated as a dictionary to avoid System.Text.Json dependency.
    w("            var schema = new Dictionary<string, string>")
    w("            {")
    schema_items = list(schema.items())
    for i, (field, type_name) in enumerate(schema_items):
        comma = "," if i < len(schema_items) - 1 else ""
        w(f'                {{ @"{field.replace(chr(34), chr(34)+chr(34))}", @"{type_name.replace(chr(34), chr(34)+chr(34))}" }}{comma}')
    w("            };")
    w()

    # Request — includes category for adapter module/prompt selection
    escaped_sig = signature.replace('"', '""')
    escaped_cat = category.replace('"', '""')
    if model:
        escaped_model = model.replace('"', '""')
        model_arg = f'@"{escaped_model}"'
    else:
        model_arg = "null"
    w(f'            var json = BuildRequestJson(@"{escaped_sig}", @"{escaped_cat}", {model_arg}, inputs, schema);')
    w()

    # === Model call with frozen replay and deterministic fallback ===
    # Order: Freeze on -> replay the item's frozen entry, or typed defaults when
    # none exists (Freeze never calls the model); else call the adapter; on an
    # adapter failure -> replay the entry if present, else typed defaults.
    # Frozen entries are kept per list item (Grasshopper runs RunScript once per
    # iteration), in one aggregate store so list matching is unaffected.
    # Inference and transport timeouts stay hard errors (Rook classifies them);
    # only "adapter unreachable" and adapter error responses fall back.
    url = f"http://localhost:{port}/chirp/call"
    unreachable = f"adapter not running on localhost:{port}"
    w("            // === Model call with frozen replay and deterministic fallback ===")
    w("            var freeze = ReadFlag(Freeze);")
    w("            var inputsHash = HashText(json);")
    w("            var store = ReadFrozenStore(Frozen);")
    w('            var slot = "i" + Iteration;')
    w("            bool entryMatches;")
    w("            var entry = FindEntry(store, slot, inputsHash, out entryMatches);")
    w("            string body = null;")
    w('            string mode = "live";')
    w('            string note = "";')
    w("            if (freeze)")
    w("            {")
    w("                if (entry != null)")
    w("                {")
    w('                    body = ExtractObject(entry, "body");')
    w('                    mode = "frozen";')
    w("                }")
    w("                else")
    w("                {")
    w('                    mode = "defaults";')
    w('                    note = "Freeze is on and no frozen result exists for this item";')
    w("                }")
    w("            }")
    w("            else")
    w("            {")
    w("                try")
    w("                {")
    w('                    var content = new StringContent(json, Encoding.UTF8, "application/json");')
    w('                    var response = _client.PostAsync("' + url + '", content).GetAwaiter().GetResult();')
    w("                    var text = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();")
    w("                    if (response.StatusCode == HttpStatusCode.GatewayTimeout)")
    w('                        throw new Exception($"chirp_inference_timeout: {text}");')
    w("                    if (response.IsSuccessStatusCode)")
    w("                        body = text;")
    w("                    else")
    w("                        note = DescribeAdapterError((int)response.StatusCode, text);")
    w("                }")
    w("                catch (HttpRequestException)")
    w("                {")
    w('                    note = "' + unreachable + '";')
    w("                }")
    w("                if (body == null)")
    w("                {")
    w("                    if (entry != null)")
    w("                    {")
    w('                        body = ExtractObject(entry, "body");')
    w('                        mode = "frozen-fallback";')
    w("                    }")
    w("                    else")
    w("                    {")
    w('                        mode = "defaults";')
    w("                    }")
    w("                }")
    w("            }")
    w()

    # Parse outputs and assign to ref params. These helpers intentionally avoid
    # System.Text.Json because Rhino.Inside C# script components may not resolve it.
    # Live and replayed bodies share this path; defaults are the typed zero values.
    w('            var reasoningText = "";')
    w("            if (body != null)")
    w("            {")
    w('                var result = ExtractObject(body, "outputs");')
    for name, type_str in out_pins:
        snake = _to_snake(name)
        reader = _csharp_json_reader(type_str)
        # Cast to object for ref assignment
        w(f'                {name} = (object){reader}(result, "{snake}");')
    w('                reasoningText = ReadString(body, "reasoning");')
    w("            }")
    w("            else")
    w("            {")
    w("                // === Deterministic defaults ===")
    for name, type_str in out_pins:
        w(f"                {name} = (object){_default_literal(type_str)};")
    w("            }")
    w()

    # Reasoning — expose the LLM's chain of thought, prefixed by the path taken.
    w('            if (mode == "live")')
    w("            {")
    w("                Reasoning = (object)reasoningText;")
    w("                TryWriteFrozen(store, slot, BuildEntry(inputsHash, body));")
    w("            }")
    w('            else if (mode == "frozen")')
    w("            {")
    w('                Reasoning = (object)("[frozen] " + reasoningText);')
    w("            }")
    w('            else if (mode == "frozen-fallback")')
    w("            {")
    w("                var changed = !entryMatches;")
    w('                var detail = note + (changed ? "; inputs changed since capture" : "");')
    w('                Reasoning = (object)("[frozen replay: " + detail + "] " + reasoningText);')
    w('                Warn("Chirp replayed its frozen result (" + detail + ")");')
    w("            }")
    w("            else")
    w("            {")
    w('                Reasoning = (object)("[deterministic fallback: " + note + "]");')
    w('                Warn("Chirp used deterministic defaults (" + note + ")");')
    w("            }")

    # Deterministic post-processing runs after outputs on every path (live,
    # frozen, fallback), so an author-supplied rule also shapes the fallback.
    if deterministic_code:
        w()
        w("            // === Deterministic post-processing ===")
        w(f"            {deterministic_code}")

    # Error handling — timeouts stay hard errors for Rook's classification; an
    # unreachable adapter is handled above by the fallback, so it never lands here.
    w("        }")
    w("        catch (TaskCanceledException)")
    w("        {")
    w(f'            throw new Exception("chirp_transport_timeout: Chirp transport exceeded its {GENERATED_CLIENT_TIMEOUT_SECONDS}-second safety ceiling.");')
    w("        }")
    w("        catch (Exception ex)")
    w("        {")
    w('            throw new Exception($"Chirp: {ex.Message}");')
    w("        }")
    w("    }")
    _write_frozen_helpers(w)
    _write_json_helpers(w)
    w("}")

    return "\n".join(lines) + "\n"


def _csharp_json_reader(type_str: str) -> str:
    """Return the generated C# helper used to coerce a JSON property."""
    if type_str == "int":
        return "ReadInt"
    if type_str in {"float", "double"}:
        return "ReadDouble"
    if type_str == "bool":
        return "ReadBool"
    return "ReadString"


def _default_literal(type_str: str) -> str:
    """C# literal used for an output pin when no model result is available."""
    if type_str == "int":
        return "0"
    if type_str in {"float", "double"}:
        return "0.0"
    if type_str == "bool":
        return "false"
    return '""'


def _write_frozen_helpers(w) -> None:
    """Emit the frozen-result helpers.

    The Frozen pin holds ONE aggregate store (a single GH_String, so Grasshopper's
    longest-list matching is unaffected) with one entry per list item:
    ``{"v":2,"count":N,"items":{"i0":{"captured","inputs","body"}, ...}}``.
    Entries are looked up by inputs hash first, then by iteration index.
    """
    w()
    w("    private static bool ReadFlag(object value)")
    w("    {")
    w("        if (value is bool flag) return flag;")
    w("        bool parsed;")
    w("        return value != null && bool.TryParse(value.ToString(), out parsed) && parsed;")
    w("    }")
    w()
    w("    private static bool HasBody(string entry)")
    w("    {")
    w("        if (string.IsNullOrWhiteSpace(entry)) return false;")
    w('        var body = ExtractRawProperty(entry, "body");')
    w("        return !string.IsNullOrWhiteSpace(body) && body.TrimStart().StartsWith(\"{\");")
    w("    }")
    w()
    w("    private static string HashText(string text)")
    w("    {")
    w("        // FNV-1a 32-bit over UTF-8: stable across solves and machines.")
    w("        // RhinoCode compiles scripts with overflow checking on; the multiply must wrap.")
    w("        uint hash = 2166136261;")
    w("        unchecked")
    w("        {")
    w('            foreach (var b in Encoding.UTF8.GetBytes(text ?? ""))')
    w("            {")
    w("                hash ^= b;")
    w("                hash *= 16777619;")
    w("            }")
    w("        }")
    w('        return hash.ToString("x8");')
    w("    }")
    w()
    w("    private IGH_Param FrozenParam()")
    w("    {")
    w("        if (Component == null || FrozenPinIndex >= Component.Params.Input.Count) return null;")
    w("        return Component.Params.Input[FrozenPinIndex];")
    w("    }")
    w()
    w("    private string ReadFrozenStore(object frozenInput)")
    w("    {")
    w("        // A wired source is the user's store. Unwired: read the pin's persistent")
    w("        // data directly, so later iterations of this solve see entries written by")
    w("        // earlier ones (the collected input value is a snapshot from solve start).")
    w("        try")
    w("        {")
    w("            var param = FrozenParam();")
    w("            if (param != null && param.SourceCount == 0)")
    w("            {")
    w("                var goo = param as GH_PersistentParam<IGH_Goo>;")
    w("                if (goo != null)")
    w("                {")
    w("                    foreach (var item in goo.PersistentData.AllData(true))")
    w("                    {")
    w("                        if (item == null) continue;")
    w("                        var text = item.ToString();")
    w("                        if (!string.IsNullOrWhiteSpace(text)) return text;")
    w("                    }")
    w('                    return "";')
    w("                }")
    w("            }")
    w("        }")
    w("        catch (Exception) { }")
    w('        return frozenInput?.ToString() ?? "";')
    w("    }")
    w()
    w("    private static string FindEntry(string store, string slot, string inputsHash, out bool matches)")
    w("    {")
    w("        matches = false;")
    w("        if (string.IsNullOrWhiteSpace(store)) return null;")
    w('        var items = ExtractRawProperty(store, "items");')
    w("        if (string.IsNullOrWhiteSpace(items))")
    w("        {")
    w("            // Legacy single snapshot: one entry, treated as item 0.")
    w('            if (slot == "i0" && HasBody(store))')
    w("            {")
    w('                matches = ReadString(store, "inputs") == inputsHash;')
    w("                return store;")
    w("            }")
    w("            return null;")
    w("        }")
    w('        var count = ReadInt(store, "count");')
    w("        for (var k = 0; k < count; k++)")
    w("        {")
    w('            var candidate = ExtractRawProperty(items, "i" + k);')
    w('            if (HasBody(candidate) && ReadString(candidate, "inputs") == inputsHash)')
    w("            {")
    w("                matches = true;")
    w("                return candidate;")
    w("            }")
    w("        }")
    w("        var positional = ExtractRawProperty(items, slot);")
    w("        return HasBody(positional) ? positional : null;")
    w("    }")
    w()
    w("    private static string BuildEntry(string inputsHash, string body)")
    w("    {")
    w("        var sb = new StringBuilder();")
    w('        sb.Append("{");')
    w('        AppendStringProperty(sb, "captured", DateTime.UtcNow.ToString("o"));')
    w('        sb.Append(",");')
    w('        AppendStringProperty(sb, "inputs", inputsHash);')
    w('        sb.Append(",\\"body\\":");')
    w("        sb.Append(body);")
    w('        sb.Append("}");')
    w("        return sb.ToString();")
    w("    }")
    w()
    w("    private static string BuildStore(string store, int index, string entry)")
    w("    {")
    w('        var current = store ?? "";')
    w('        var items = ExtractRawProperty(current, "items");')
    w('        var count = ReadInt(current, "count");')
    w("        if (string.IsNullOrWhiteSpace(items) && HasBody(current))")
    w("        {")
    w('            items = "{\\"i0\\":" + current + "}"; // legacy single snapshot')
    w("            count = 1;")
    w("        }")
    w("        var total = Math.Max(count, index + 1);")
    w("        var sb = new StringBuilder();")
    w('        sb.Append("{\\"v\\":2,\\"count\\":").Append(total).Append(",\\"items\\":{");')
    w("        var first = true;")
    w("        for (var k = 0; k < total; k++)")
    w("        {")
    w('            var raw = k == index ? entry : ExtractRawProperty(items, "i" + k);')
    w("            if (!HasBody(raw)) continue;")
    w('            if (!first) sb.Append(",");')
    w("            first = false;")
    w('            sb.Append("\\"i").Append(k).Append("\\":").Append(raw);')
    w("        }")
    w('        sb.Append("}}");')
    w("        return sb.ToString();")
    w("    }")
    w()
    w("    private static string DescribeAdapterError(int status, string text)")
    w("    {")
    w('        var code = ReadString(text ?? "", "error");')
    w('        var details = ReadString(text ?? "", "details");')
    w("        if (!string.IsNullOrWhiteSpace(code))")
    w('            return code + (string.IsNullOrWhiteSpace(details) ? "" : ": " + details);')
    w('        return "adapter error " + status;')
    w("    }")
    w()
    w("    private void Warn(string message)")
    w("    {")
    w("        // Rhino 8 script instances expose AddRuntimeMessage directly (like Print).")
    w("        try { AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, message); }")
    w("        catch (Exception) { Print(message); }")
    w("    }")
    w()
    w("    private bool IsLastIteration()")
    w("    {")
    w("        var max = 1;")
    w("        try")
    w("        {")
    w("            foreach (var p in Component.Params.Input)")
    w("                if (p.VolatileDataCount > max) max = p.VolatileDataCount;")
    w("        }")
    w("        catch (Exception) { }")
    w("        return Iteration + 1 >= max;")
    w("    }")
    w()
    w("    private void TryWriteFrozen(string store, string slot, string entry)")
    w("    {")
    w("        // Store the updated aggregate as the Frozen pin's persistent data (what")
    w("        // 'Internalise data' does), so it is saved in the .gh and travels with it.")
    w("        try")
    w("        {")
    w("            var param = FrozenParam();")
    w("            if (param == null || string.IsNullOrEmpty(entry)) return;")
    w("            if (param.SourceCount > 0) return; // a wired store belongs to the user")
    w('            var existing = ExtractRawProperty(ExtractRawProperty(store ?? "", "items"), slot);')
    w('            if (string.IsNullOrWhiteSpace(existing) && slot == "i0" && HasBody(store ?? "")) existing = store;')
    w("            if (HasBody(existing)")
    w('                && ExtractRawProperty(existing, "body") == ExtractRawProperty(entry, "body")')
    w('                && ReadString(existing, "inputs") == ReadString(entry, "inputs"))')
    w("                return; // unchanged result: do not dirty the document for a new timestamp")
    w("            var updated = BuildStore(store, Iteration, entry);")
    w("            // Store a GH_String, never a GH_ObjectWrapper: the wrapper does not write")
    w("            // its payload into the .gh file, so the store would reopen empty.")
    w("            var goo = param as GH_PersistentParam<IGH_Goo>;")
    w("            if (goo != null)")
    w("            {")
    w("                goo.PersistentData.Clear();")
    w("                goo.PersistentData.Append(new GH_String(updated));")
    w("            }")
    w("            else")
    w("            {")
    w('                var property = param.GetType().GetProperty("PersistentData");')
    w("                var data = property == null ? null : property.GetValue(param);")
    w("                if (data == null)")
    w("                {")
    w('                    Print("Chirp: this input cannot hold persistent data; frozen result not stored.");')
    w("                    return;")
    w("                }")
    w('                var clear = data.GetType().GetMethod("Clear", Type.EmptyTypes);')
    w("                if (clear != null) clear.Invoke(data, null);")
    w("                object payload = new GH_String(updated);")
    w('                var append = data.GetType().GetMethod("Append", new[] { payload.GetType() });')
    w("                if (append == null)")
    w('                    append = data.GetType().GetMethod("Append", new[] { typeof(IGH_Goo) });')
    w("                if (append == null)")
    w("                {")
    w('                    Print("Chirp: persistent data has no Append for the frozen result.");')
    w("                    return;")
    w("                }")
    w("                append.Invoke(data, new[] { payload });")
    w("            }")
    w("            if (IsLastIteration()) RefreshPin(param);")
    w("        }")
    w("        catch (Exception ex)")
    w("        {")
    w('            Print("Chirp: could not store the frozen result: " + ex.Message);')
    w("        }")
    w("    }")
    w()
    w("    private static void RefreshPin(IGH_Param param)")
    w("    {")
    w("        // Grasshopper only re-collects a source-less input's persistent data when the")
    w("        // parameter itself is reset; a component re-solve alone keeps the stale volatile")
    w("        // value. Reset and re-collect after the last iteration so the canvas shows the")
    w("        // new store. Nothing is expired, so no extra solve is triggered.")
    w("        param.ClearData();")
    w("        param.CollectData();")
    w("    }")


def _write_json_helpers(w) -> None:
    """Emit small JSON request/response helpers for host-compatible GH scripts."""
    w()
    w("    private static string BuildRequestJson(")
    w("        string signature,")
    w("        string category,")
    w("        string model,")
    w("        Dictionary<string, object> inputs,")
    w("        Dictionary<string, string> schema)")
    w("    {")
    w("        var sb = new StringBuilder();")
    w('        sb.Append("{");')
    w('        AppendStringProperty(sb, "signature", signature);')
    w('        sb.Append(",");')
    w('        sb.Append("\\"inputs\\":");')
    w("        AppendObject(sb, inputs);")
    w('        sb.Append(",");')
    w('        sb.Append("\\"schema\\":");')
    w("        AppendStringObject(sb, schema);")
    w('        sb.Append(",");')
    w('        AppendStringProperty(sb, "category", category);')
    w("        if (!string.IsNullOrWhiteSpace(model))")
    w("        {")
    w('            sb.Append(",");')
    w('            AppendStringProperty(sb, "model", model);')
    w("        }")
    w('        sb.Append("}");')
    w("        return sb.ToString();")
    w("    }")
    w()
    w("    private static void AppendObject(StringBuilder sb, Dictionary<string, object> values)")
    w("    {")
    w('        sb.Append("{");')
    w("        var first = true;")
    w("        foreach (var pair in values)")
    w("        {")
    w("            if (!first) sb.Append(\",\");")
    w("            first = false;")
    w("            AppendQuoted(sb, pair.Key);")
    w('            sb.Append(":");')
    w("            AppendJsonValue(sb, pair.Value);")
    w("        }")
    w('        sb.Append("}");')
    w("    }")
    w()
    w("    private static void AppendStringObject(StringBuilder sb, Dictionary<string, string> values)")
    w("    {")
    w('        sb.Append("{");')
    w("        var first = true;")
    w("        foreach (var pair in values)")
    w("        {")
    w("            if (!first) sb.Append(\",\");")
    w("            first = false;")
    w("            AppendQuoted(sb, pair.Key);")
    w('            sb.Append(":");')
    w("            AppendQuoted(sb, pair.Value);")
    w("        }")
    w('        sb.Append("}");')
    w("    }")
    w()
    w("    private static void AppendStringProperty(StringBuilder sb, string key, string value)")
    w("    {")
    w("        AppendQuoted(sb, key);")
    w('        sb.Append(":");')
    w("        AppendQuoted(sb, value);")
    w("    }")
    w()
    w("    private static void AppendJsonValue(StringBuilder sb, object value)")
    w("    {")
    w("        if (value == null)")
    w("        {")
    w('            sb.Append("\\"\\"");')
    w("            return;")
    w("        }")
    w()
    w("        if (value is bool boolValue)")
    w("        {")
    w('            sb.Append(boolValue ? "true" : "false");')
    w("            return;")
    w("        }")
    w()
    w("        if (value is IFormattable formattable && !(value is string))")
    w("        {")
    w("            sb.Append(formattable.ToString(null, CultureInfo.InvariantCulture));")
    w("            return;")
    w("        }")
    w()
    w("        AppendQuoted(sb, value.ToString() ?? string.Empty);")
    w("    }")
    w()
    w("    private static void AppendQuoted(StringBuilder sb, string value)")
    w("    {")
    w('        sb.Append("\\"");')
    w("        foreach (var ch in value ?? string.Empty)")
    w("        {")
    w("            switch (ch)")
    w("            {")
    w('                case \'\\\\\': sb.Append("\\\\\\\\"); break;')
    w('                case \'"\' : sb.Append("\\\\\\\""); break;')
    w('                case \'\\n\': sb.Append("\\\\n"); break;')
    w('                case \'\\r\': sb.Append("\\\\r"); break;')
    w('                case \'\\t\': sb.Append("\\\\t"); break;')
    w("                default: sb.Append(ch); break;")
    w("            }")
    w("        }")
    w('        sb.Append("\\"");')
    w("    }")
    w()
    w("    private static string ExtractObject(string json, string property)")
    w("    {")
    w("        var raw = ExtractRawProperty(json, property);")
    w("        if (string.IsNullOrWhiteSpace(raw) || raw[0] != '{')")
    w('            throw new Exception($"Chirp response missing object property {property}");')
    w("        return raw;")
    w("    }")
    w()
    w("    private static string ExtractRawProperty(string json, string property)")
    w("    {")
    w("        var marker = \"\\\"\" + property + \"\\\"\";")
    w("        var key = json.IndexOf(marker, StringComparison.Ordinal);")
    w("        if (key < 0)")
    w("            return string.Empty;")
    w("        var colon = json.IndexOf(':', key + marker.Length);")
    w("        if (colon < 0)")
    w("            return string.Empty;")
    w("        var start = SkipWhitespace(json, colon + 1);")
    w("        if (start >= json.Length)")
    w("            return string.Empty;")
    w("        if (json[start] == '\"')")
    w("            return json.Substring(start, ScanStringEnd(json, start) - start + 1);")
    w("        if (json[start] == '{')")
    w("            return json.Substring(start, ScanObjectEnd(json, start) - start + 1);")
    w("        var end = start;")
    w("        while (end < json.Length && json[end] != ',' && json[end] != '}')")
    w("            end++;")
    w("        return json.Substring(start, end - start).Trim();")
    w("    }")
    w()
    w("    private static int SkipWhitespace(string text, int index)")
    w("    {")
    w("        while (index < text.Length && char.IsWhiteSpace(text[index])) index++;")
    w("        return index;")
    w("    }")
    w()
    w("    private static int ScanStringEnd(string text, int start)")
    w("    {")
    w("        var escaped = false;")
    w("        for (var i = start + 1; i < text.Length; i++)")
    w("        {")
    w("            if (escaped)")
    w("            {")
    w("                escaped = false;")
    w("                continue;")
    w("            }")
    w("            if (text[i] == '\\\\')")
    w("            {")
    w("                escaped = true;")
    w("                continue;")
    w("            }")
    w("            if (text[i] == '\"') return i;")
    w("        }")
    w("        throw new Exception(\"Chirp response contained an unterminated string.\");")
    w("    }")
    w()
    w("    private static int ScanObjectEnd(string text, int start)")
    w("    {")
    w("        var depth = 0;")
    w("        var inString = false;")
    w("        var escaped = false;")
    w("        for (var i = start; i < text.Length; i++)")
    w("        {")
    w("            var ch = text[i];")
    w("            if (inString)")
    w("            {")
    w("                if (escaped)")
    w("                {")
    w("                    escaped = false;")
    w("                }")
    w("                else if (ch == '\\\\')")
    w("                {")
    w("                    escaped = true;")
    w("                }")
    w("                else if (ch == '\"')")
    w("                {")
    w("                    inString = false;")
    w("                }")
    w("                continue;")
    w("            }")
    w("            if (ch == '\"')")
    w("            {")
    w("                inString = true;")
    w("            }")
    w("            else if (ch == '{')")
    w("            {")
    w("                depth++;")
    w("            }")
    w("            else if (ch == '}')")
    w("            {")
    w("                depth--;")
    w("                if (depth == 0) return i;")
    w("            }")
    w("        }")
    w("        throw new Exception(\"Chirp response contained an unterminated object.\");")
    w("    }")
    w()
    w("    private static string ReadString(string json, string property)")
    w("    {")
    w("        var raw = ExtractRawProperty(json, property);")
    w("        if (string.IsNullOrWhiteSpace(raw)) return string.Empty;")
    w("        raw = raw.Trim();")
    w("        if (raw.Length >= 2 && raw[0] == '\"' && raw[raw.Length - 1] == '\"')")
    w("            return UnescapeJsonString(raw.Substring(1, raw.Length - 2));")
    w("        return raw;")
    w("    }")
    w()
    w("    private static int ReadInt(string json, string property)")
    w("    {")
    w("        var raw = ExtractRawProperty(json, property);")
    w("        if (int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out var value))")
    w("            return value;")
    w("        return 0;")
    w("    }")
    w()
    w("    private static double ReadDouble(string json, string property)")
    w("    {")
    w("        var raw = ExtractRawProperty(json, property);")
    w("        if (double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var value))")
    w("            return value;")
    w("        return 0.0;")
    w("    }")
    w()
    w("    private static bool ReadBool(string json, string property)")
    w("    {")
    w("        var raw = ExtractRawProperty(json, property);")
    w("        if (bool.TryParse(raw, out var value))")
    w("            return value;")
    w("        return false;")
    w("    }")
    w()
    w("    private static string UnescapeJsonString(string value)")
    w("    {")
    w("        return value")
    w('            .Replace("\\\\n", "\\n")')
    w('            .Replace("\\\\r", "\\r")')
    w('            .Replace("\\\\t", "\\t")')
    w('            .Replace("\\\\\\\"", "\\"")')
    w('            .Replace("\\\\\\\\", "\\\\");')
    w("    }")


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
