# Chirp — Implementation Plan

**Date:** 2026-03-13
**Design doc:** [chirp-landscape-exploration.md](2026-03-13-chirp-landscape-exploration.md)
**Status:** Ready to execute

---

## What We're Building

Two deliverables that enable Rook to create intelligent GH components on the fly:

1. **Chirp Adapter Service** (Python) — the format → LLM call → parse → validate → cache → trace cycle, exposed as an HTTP endpoint
2. **chirp_create Tool** (Rook MCP tool) — token-efficient creation of intelligent script components on the GH canvas

## Architecture Decision: Python Service, Not C# DLL

GH C# Script components have no clean mechanism for referencing external .dlls at runtime. Rather than fight this, the adapter runs as a **Python HTTP service** that script components call via `HttpClient.PostAsync()`. This is cleaner because:

- Python has direct access to Anthropic/OpenAI SDKs (no HTTP wrapper for LLM calls)
- DSPy is Python — we can use it as the adapter backend, getting format/parse/validate for free
- Rook's MCP server is Python — natural integration path
- LLM call latency (100ms-seconds) dwarfs the local HTTP round-trip (~1ms)

The script component body becomes ~10 lines of C# that POST to the adapter and unpack the response.

---

## Phase 1: Chirp Adapter Service

**Goal:** A Python service that takes a signature + inputs + schema, calls an LLM, and returns validated typed outputs. Testable with curl.

### Task 1.1: Project scaffold

- [ ] Initialize Python project in Chirp repo root
  - `pyproject.toml` with dependencies: `dspy`, `fastapi`, `uvicorn`, `pydantic`
  - `src/chirp/` package directory
  - `tests/` directory
- [ ] Verify: `pip install -e .` succeeds

### Task 1.2: Core adapter module

- [ ] Create `src/chirp/adapter.py`
  - `ChirpAdapter` class
  - `call(signature: str, inputs: dict, schema: dict) -> dict` method
  - Internally builds a DSPy `Signature` from the string + schema
  - Creates a `dspy.Predict(signature)` module
  - Calls it with the inputs
  - Returns validated outputs as a dict matching the schema
- [ ] Configure DSPy LM via LiteLLM model string (e.g. `dspy.LM("anthropic/claude-sonnet-4-20250514")` — swappable to any LiteLLM-supported provider via `CHIRP_MODEL` env var)
- [ ] Verify: unit test that calls `adapter.call()` with a simple signature and gets typed output back

### Task 1.3: Type coercion layer

- [ ] Create `src/chirp/types.py`
  - Map schema type strings to Python/Pydantic types: `"int"`, `"float"`, `"string"`, `"bool"`, `"list[int]"`, etc.
  - GH-specific types (`"Surface"`, `"Mesh"`, `"Curve"`, `"Point3d"`) → string representations (serialized as descriptive text for LLM, returned as string for script to reconstruct)
  - Build Pydantic model from schema dict at runtime
- [ ] Verify: type coercion test — LLM returns `"42"` for an int field, adapter returns Python `int(42)`

### Task 1.4: HTTP server

- [ ] Create `src/chirp/server.py`
  - FastAPI app with single endpoint: `POST /chirp/call`
  - Request body: `{ "signature": str, "inputs": dict, "schema": dict }`
  - Response body: `{ "outputs": dict, "reasoning": str | null, "usage": { "input_tokens": int, "output_tokens": int } }`
  - Error response: `{ "error": str, "details": str }`
- [ ] Create `src/chirp/__main__.py` — `uvicorn` entry point, configurable port (default 9900)
- [ ] Verify: `python -m chirp` starts server, `curl -X POST http://localhost:9900/chirp/call -d '...'` returns valid response

### Task 1.5: Caching

- [ ] Add input-hash → output cache to `ChirpAdapter`
  - Hash: `sha256(signature + json.dumps(inputs, sort_keys=True) + json.dumps(schema, sort_keys=True))`
  - Cache store: in-memory dict (sufficient for prototype; upgrade to disk/redis later)
  - Cache-Control header or `"cache": true/false` in request body
- [ ] Verify: second identical request returns cached result with `"cached": true` in response

### Task 1.6: Trace logging

- [ ] Add trace logging to `ChirpAdapter`
  - Each call logs: timestamp, signature, inputs, schema, LLM prompt (from DSPy), LLM response, parsed outputs, latency_ms, tokens_used, cache_hit
  - Log to `traces/` directory as JSONL (one line per call)
  - Configurable via env var `CHIRP_TRACE_DIR`
- [ ] Verify: after a call, trace file exists with correct structure

---

## Phase 2: Script Component Integration

**Goal:** A working C# script component in Grasshopper that calls the Chirp adapter and produces typed outputs. Manual test.

### Task 2.1: Script component template

- [ ] Create `templates/chirp_script_template.cs` — the C# code that goes inside a GH script component
  - Uses `System.Net.Http.HttpClient` to POST to `http://localhost:9900/chirp/call`
  - Serializes inputs from component pins to JSON
  - Deserializes response JSON to typed outputs
  - Sets outputs via script component output variables (A, B, C, etc.)
  - Error handling: if adapter returns error, set component runtime message via `AddRuntimeMessage`
  - Synchronous (blocking) call — async via `GH_TaskCapableComponent` comes later
- [ ] Verify: template compiles in GH script component editor (manual test)

### Task 2.2: First manual test — "Intent to Parameters"

- [ ] Create the test component manually in Grasshopper:
  - Script component with inputs: `Surface` (Surface), `Intent` (string)
  - Outputs: `UCount` (int), `VCount` (int), `Grading` (double)
  - Script body: the template code calling Chirp adapter with signature "Given a surface description and design intent, determine subdivision parameters"
- [ ] Wire it: Surface input → Chirp component → downstream SubSrf or similar
- [ ] Verify: type "dense near edges" as intent → get reasonable int/int/double outputs → geometry downstream updates

### Task 2.3: Error handling and edge cases

- [ ] Test: adapter service not running → component shows warning message, doesn't crash
- [ ] Test: LLM returns unparseable output → adapter retries or returns error → component shows error
- [ ] Test: empty/null inputs → graceful handling
- [ ] Test: rapid re-solve (slider upstream) → cache prevents redundant LLM calls

---

## Phase 3: chirp_create Tool

**Goal:** A Rook MCP tool that creates intelligent script components on the canvas in ~100 tokens.

### Task 3.1: Tool definition

- [ ] Create `src/chirp/rook_tool.py`
  - `chirp_create(pins_in, pins_out, signature, schema, deterministic_code=None)` function
  - Generates the full C# script body from template + parameters
  - Returns a `gh_edit`-compatible batch mutation that:
    1. Creates a C# Script component
    2. Sets input/output pins
    3. Sets the script code via `/gh/script` endpoint
  - Alternatively: calls Rook's HTTP API directly to create the component
- [ ] Define MCP tool schema for Rook integration
- [ ] Verify: calling the function returns valid gh_edit JSON

### Task 3.2: Pin configuration

- [ ] Implement dynamic pin setup
  - Parse pin definitions: `"Surface:Surface"`, `"Intent:string"`, `"UCount:int"`
  - Map to GH script component I/O (script components use generic A/B/C output names — need to set via type hints or rename)
  - Handle GH type mapping: `string` → `System.String`, `int` → `System.Int32`, `Surface` → `Rhino.Geometry.Surface`, etc.
- [ ] Verify: created component has correct pin names and types

### Task 3.3: Integration test with Rook

- [ ] Register `chirp_create` as a Rook MCP tool (or call via HTTP)
- [ ] Test: Rook agent calls `chirp_create` → component appears on canvas → component works
- [ ] Test: Rook chains two chirp components → pipeline works end-to-end
- [ ] Verify: the full loop — natural language → Rook → chirp_create → working intelligent component on canvas

---

## Phase 4: Hardening & First Real Use

**Goal:** Use Chirp on a real design task at Safdie to validate the concept.

### Task 4.1: Pick a real workflow

- [ ] Identify a current Safdie project workflow where intent-to-parameters would save time
- [ ] Design 2-3 intelligent components for that workflow
- [ ] Build them via chirp_create
- [ ] Measure: does it actually help? What breaks?

### Task 4.2: Reliability improvements (based on Phase 4.1 findings)

- [ ] Items TBD based on real usage feedback
- [ ] Likely: prompt tuning, schema refinement, caching improvements, error messages

### Task 4.3: Rook knowledge integration

- [ ] Register Chirp components in Rook's knowledge graph
- [ ] Chirp traces feed into Rook's learning pipeline (A-MEM, MABWiser)
- [ ] Few-shot demo injection from successful traces

---

## Success Criteria

**Phase 1 done when:** `curl` to the adapter service returns correct typed outputs for 3 different signatures.

**Phase 2 done when:** A GH script component on canvas calls the adapter and produces correct typed outputs that downstream deterministic components consume.

**Phase 3 done when:** Rook creates an intelligent component on the canvas from a ~100 token tool call, and it works.

**Phase 4 done when:** A real Safdie design workflow uses Chirp components and the designer finds it useful.

---

## Technical Notes

### Port allocation
- Rook native: 9878 (probes 9878-9887)
- RookRoads: 9878-9899 (overlaps with Rook; probes until free)
- Chirp adapter: 9900 (first port outside both Rook and RookRoads ranges; configurable via `CHIRP_PORT` env var)
- Could also run on Rook's port as a sub-route if integrated into Rook's server

### Dependencies
- Python 3.10+ (matches Rook's MCP server)
- DSPy (for Signature/Adapter/Predict pattern — brings LiteLLM as provider abstraction)
- LiteLLM (via DSPy — enables any provider: Anthropic, OpenAI, Ollama, etc. with a single model string)
- FastAPI + uvicorn (HTTP server)
- Pydantic (type validation — also used by DSPy)

### Rook endpoints used
- `POST /gh/edit` — batch component creation
- `POST /gh/script` — set script component source code
- `POST /gh/create-component` — create component by GUID
- `GET /gh/query` — canvas introspection (for future context-aware components)

### Environment variables
- `CHIRP_PORT` — adapter service port (default 9900)
- `CHIRP_TRACE_DIR` — trace log directory (default `./traces`)
- `ANTHROPIC_API_KEY` — for LLM calls
- `CHIRP_MODEL` — LiteLLM model string (default `anthropic/claude-sonnet-4-20250514`; supports `openai/gpt-4o`, `ollama/llama3`, any LiteLLM provider)
- `CHIRP_CACHE` — enable/disable caching (default `true`)
