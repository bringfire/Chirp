# Chirp frozen results and deterministic fallback

**Date:** 2026-09-23 · **Status:** implemented; live Grasshopper gate PASSED 2026-09-24 · **Rook side:** skill text only

**Gate result (Rhino 8.35, standalone, fake adapter on 9977, no key):** live solve wrote the snapshot
into the Frozen pin's persistent data; with the adapter stopped the *first* re-solve replayed it
(`[frozen replay: adapter not running…]`, runtime warning); after save → close → reopen from disk the
replay came from the file; `Freeze=true` replayed as `[frozen]` with no warning. A component built
before the `GH_String` fix, reopened from the same file, came back with an empty `GH_ObjectWrapper`
and fell to `[deterministic fallback…]`, confirming both the serialisation finding and the fallback.
Three findings folded in: `unchecked` for the FNV hash (RhinoCode compiles with overflow checks),
`RefreshPin` (ClearData + CollectData) after every write, and `GH_String` storage.

## Problem

A Chirp component is a Grasshopper script that calls the adapter on every solve. Without a
configured model every component turns red on every solve, after ~12 s of LiteLLM auth retries.
A `.gh` file with Chirp components therefore only works on the machine that authored it, with a
key, and every re-solve costs a model call. The Rook installer no longer collects a key, so the
first-run experience is exactly this failure.

## Goal

Every Chirp component keeps its last successful model result *inside the Grasshopper file*, replays
it when the model is unavailable or when the user asks for it, and otherwise degrades to typed
deterministic defaults. Reasoning always says which path ran. Nothing here needs a key, Rook, or the
adapter for a frozen file to solve.

## Design

### Two new universal input pins (auto-added like `Correction`)

| Pin | Type | Meaning |
|---|---|---|
| `Freeze` | bool, optional | `true`: replay the frozen result and never call the model. Default `false`. |
| `Frozen` | string, optional | The frozen snapshot. Written by the component itself after each successful model call, into the pin's **persistent data**, so it is saved in the `.gh` and travels with the file. May also be wired from a Panel to supply a snapshot by hand. |

Both are reserved names, rejected in `pins_in` like `Correction`.

### Snapshot format (`Frozen` value)

The raw `/chirp/call` response body wrapped with capture metadata:

```json
{"v": 1, "captured": "2026-09-23T23:10:00Z", "inputs": "<fnv1a hex of the request inputs JSON>", "body": { ...verbatim adapter response... }}
```

Replay parses `body` with the same generated readers as a live response, so replay and live share one
code path. `inputs` lets replay warn when the inputs changed since capture.

### Solve algorithm (generated C#)

1. Build the request as today.
2. If `Freeze == true` and a snapshot is present → **replay**. Reasoning = `[frozen] ` + captured reasoning.
3. Else call the adapter.
   - Success → assign outputs, Reasoning; write a new snapshot into `Frozen`'s persistent data.
   - Adapter unreachable, or HTTP 503 `model_unavailable`, or any other failure →
     - snapshot present → **replay**, Reasoning prefixed `[frozen replay: <reason>]`; runtime **warning** if the input hash differs from capture.
     - no snapshot → **deterministic defaults** per output pin (`_csharp_default`), Reasoning = `[deterministic fallback: <reason>]`; runtime **warning**.
4. `deterministic_code` (author post-processing) runs after outputs are assigned on every path, so an author-supplied default rule applies to replay and fallback too.
5. `deterministic_only` components are unchanged (no pins added, no adapter contact).

The component never throws for a missing model. Compile and contract errors still throw.

### Adapter: fail fast and say why

- `ChirpAdapter` resolves the credential env var for a model's provider prefix at LM creation
  (anthropic → `ANTHROPIC_API_KEY`, openai cloud → `OPENAI_API_KEY`, openrouter → `OPENROUTER_API_KEY`,
  gemini → `GEMINI_API_KEY`; local/OpenAI-compatible endpoints from `CHIRP_PROVIDERS` need none).
  A model whose credential is absent is marked unavailable; `call()` raises `ModelUnavailable`
  immediately instead of retrying for 12 s.
- `/chirp/call` maps `ModelUnavailable` to **503** `{"error": "model_unavailable", "details": ...}`.
- `/health` gains `model_ready: bool` and `model_reason: str|null` for the default model.

### Persistence mechanism (gate: live Grasshopper test before merge)

`Component.Params.Input[frozenIndex]` cast to `Param_GenericObject` / `Param_String`;
`PersistentData.Clear()` + `Append(...)` inside `RunScript`. This is what "Internalise data" does, is
serialised into the `.gh`, and is collected on the next solve when the pin has no sources. No
`ExpireSolution` is called, so no solve loop. Gate: create a probe component in a live Grasshopper,
solve twice, save, reopen, confirm the value round-trips and the document is marked dirty.
Fallback if the gate fails: keep the snapshot in the script source as a constant rewritten through
Rook's `gh_set_script` (explicit "freeze" action instead of automatic capture).

### Out of scope here

- A RookChat settings surface for Chirp credentials, and a Prime-backed provider (subscription
  users). Both build on this: a frozen file already solves without either.
- Rook changes beyond the Chirp skill text (Rook adds pins from the adapter's `pins_in`, so the new
  pins need no Rook code).

## Tests

- `test_rook_tool.py`: new pins present and reserved; replay branch and fallback defaults emitted;
  deterministic_code emitted on all paths; deterministic_only unchanged; still no `System.Text.Json`.
- `test_adapter.py`: credential resolution per prefix; missing credential → `ModelUnavailable` without
  calling the LM; `CHIRP_PROVIDERS` endpoint without key is allowed.
- `test_server.py`: 503 mapping; health `model_ready`.
- Live (Rook install): no key → component solves with `[deterministic fallback…]`; with key → solves,
  snapshot written; save/reopen on a keyless run → `[frozen replay…]` with the captured outputs.
