# Phase 2 Manual Test Plan

## Prerequisites
1. Chirp adapter running: `python -m chirp` (from repo root with venv activated)
2. Verify: `curl http://localhost:9900/health` returns `{"status":"ok"}`
3. Rhino + Grasshopper open

## Test 2.2: Intent to Parameters

1. Add a C# Script component to the canvas
2. Set inputs: `SurfaceDesc` (string), `Intent` (string)
3. Set outputs: `UCount` (int), `VCount` (int), `Grading` (double)
4. Paste the code from `templates/example_intent_to_params.cs`
5. Wire a Panel to `SurfaceDesc` with: "Rectangular planar surface, 20m x 10m"
6. Wire a Panel to `Intent` with: "dense near edges, sparse in center"
7. Expected: UCount/VCount get reasonable ints, Grading gets a float
8. Wire outputs to a SubSrf or similar downstream component

## Test 2.3: Error Handling

### Adapter not running
1. Stop the Chirp server
2. Trigger the component (change an input)
3. Expected: outputs reset to 0/0.0, component does not crash

### Empty inputs
1. Clear the Intent panel (empty string)
2. Expected: component returns early, no HTTP call

### Rapid re-solve (cache test)
1. Connect a slider to Intent via a Panel
2. Set same text, trigger multiple times quickly
3. Expected: first call hits LLM (~1-2s), subsequent identical calls return instantly (cached)

### Bad schema
1. Modify the script to send an invalid schema type (e.g. "foo")
2. Expected: Chirp returns 500 with error details, component shows error message
