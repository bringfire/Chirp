# Chirp — Landscape Exploration

**Date:** 2026-03-13
**Status:** Active exploration
**Authors:** Aryan + Claude

---

## Context

Chirp started as a spec-driven code generation pipeline for Grasshopper components, inspired by CodeSpeak. The original brief described a YAML-to-C# compiler with a retry loop.

Then we looked at Rook.

Rook is a 215+ tool MCP bridge giving AI agents full programmatic control over Rhino and Grasshopper — geometry creation, canvas manipulation, a self-improving knowledge graph (919 GH components catalogued), multi-agent orchestration, and a 4-phase design cascade. Rook creates **zero** custom GH_Components; it manipulates existing ones via reflection.

This changes Chirp's scope. We're no longer just generating boilerplate. We're designing an **AI-native component library** — Grasshopper components built from the ground up to be discovered, driven, composed, and potentially generated on-the-fly by Rook and other AI agents.

---

## Foundational Analysis: Why Grasshopper?

Before exploring specific opportunities, we need to answer the question that Opportunity #8 surfaced: **if agents can write scripts like humans speak, why do we need Grasshopper at all?**

The answer is that Grasshopper's fundamentals compensate for exactly the things LLMs are worst at. And LLMs compensate for exactly what Grasshopper is worst at. The complementarity is structural, not incidental.

### What Each Platform Is (Fundamentally)

**Rhino** is a direct-manipulation modeler. You act on geometry imperatively — extrude this, fillet that. The result is a **document** (persistent geometry with layers, materials, attributes) but the _process_ is ephemeral. Once you make a fillet, the "why" and "how" are gone. There's no undo graph, no parametric history, no way to say "actually make that fillet 3mm instead of 5mm" without starting over.

**Grasshopper** is a declarative, reactive dataflow graph. You don't _do_ operations — you _describe relationships_. "This curve is always the offset of that curve by this slider's value." The canvas is a **persistent state machine**: change any input and everything downstream recomputes. The definition IS the design logic, preserved visually. Data trees handle the one-to-many branching (one surface → 100 panels → 400 edges) that would require explicit loops in code.

**LLMs** are natural language reasoners. They understand intent, have world knowledge, can generate code, evaluate trade-offs, and explain decisions. But they operate in a fundamentally **procedural, stateless, one-shot** mode: generate a script, run it, done.

### The Complementarity Table

| LLM Weakness | Grasshopper Strength |
|---|---|
| **No persistent state** — context window is finite, conversation is ephemeral | **Canvas IS persistent state** — the definition lives across solves, sessions, days |
| **Procedural only** — generates sequences of actions, then it's done | **Declarative & reactive** — relationships persist and auto-update |
| **No undo graph** — if step 15/20 was wrong, must replay everything | **Definition is its own history** — every step is visible, modifiable, reversible |
| **No spatial reasoning** — can't "see" geometry natively | **Visual graph** — spatial and logical relationships are explicit on canvas |
| **Hallucination** — may produce plausible but wrong operations | **Deterministic compute** — geometry math doesn't hallucinate |
| **One-shot execution** — no parametric exploration | **Sliders = instant variation** — explore design space continuously |
| **Can't manage branching data** — lists and trees require explicit code | **Data trees are first-class** — hierarchical one-to-many is native |

| Grasshopper Weakness | LLM Strength |
|---|---|
| **Rigid components** — each does exactly one thing, no interpretation | **Flexible intent** — can understand "make it denser near the edges" |
| **No world knowledge** — doesn't know what a diagrid is _for_ | **Rich world knowledge** — materials, structures, climate, precedent |
| **Can't explain itself** — definitions become unreadable at scale | **Natural language** — can narrate what a definition does and why |
| **Manual wiring is tedious** — placing and connecting 50 components by hand | **Automatic composition** — agent can build definitions from intent |
| **Fixed parameter space** — you expose what you expose | **Intent-to-parameters** — can suggest values from natural language |
| **No design judgment** — computes what you tell it, can't say "this looks wrong" | **Evaluation & critique** — can assess design quality against criteria |

### The Synthesis: Grasshopper as the LLM's Working Memory

This table reveals Chirp's deepest opportunity. **Grasshopper is the persistent, declarative, reactive substrate that compensates for the LLM's statelessness.** The canvas becomes:

- The LLM's **working memory** — relationships it has established persist between conversations
- The LLM's **undo graph** — every decision is a visible, modifiable node
- The LLM's **exploration interface** — sliders let the human (or the agent) vary parameters without rebuilding
- The LLM's **accountability layer** — the definition shows _how_ the geometry was made, not just _what_ was made

And from the other direction, the LLM becomes:

- Grasshopper's **intent interpreter** — translating natural language into precise parameters
- Grasshopper's **world knowledge** — informing parametric decisions with domain expertise
- Grasshopper's **narrator** — making complex definitions legible to humans
- Grasshopper's **critic** — evaluating outputs against design criteria the canvas can't express

**Neither tool is complete alone. Together, they're a design reasoning system where the human, the graph, and the intelligence layer each do what they're best at.**

This reframes every opportunity on the map. The question for each is: **does this leverage the complementarity, or does it fight it?**

---

## The Expanded Landscape

### Opportunity Space

Below is the map of opportunities we're exploring. Each is tagged with a status:
- `[exploring]` — actively discussing
- `[promising]` — worth designing further
- `[parked]` — interesting but not now
- `[rejected]` — explored and dismissed (with reason)

---

### 1. Spec-Driven Component Generation (Original Chirp)

**Status:** `[exploring]`

The original vision: YAML spec in, compilable `.cs` file out, with a 3-retry compile loop.

**What we know works:**
- GH_Component structure is extremely regular (constructor, RegisterInputParams, RegisterOutputParams, SolveInstance, Guid, Icon)
- The mcneel/rhino-developer-samples confirm the pattern is consistent across simple, geometry, doc-accessing, and async components
- CodeSpeak demonstrates 5-10x LOC reduction on similar boilerplate-heavy targets

**Open questions:**
- Does generation need to happen offline (build a .gha plugin), or can we hot-compile at runtime?
- Should specs live in the Chirp repo, or inside Rook's knowledge graph?
- How does a generated component get into a user's Grasshopper environment?

---

### 2. AI-Discoverable Components

**Status:** `[exploring]`

Components whose specs, behaviors, and I/O contracts are fully legible to Rook's knowledge graph — so an AI agent knows exactly what a component does, what to wire to it, and when to use it, without trial and error.

**Concept:**
- Each Chirp component ships with machine-readable metadata beyond what GH_Component provides natively
- Rook's `sparse_index.json` (1400 intents → GUIDs) and `tiered_knowledge.json` (919 components with I/O) could be auto-populated from Chirp specs
- The spec IS the documentation — no gap between what the component does and what the agent thinks it does

**What this enables:**
- Rook can compose Chirp components with near-zero hallucination risk
- Knowledge graph stays in sync with component behavior automatically
- New components are immediately usable by agents without manual knowledge authoring

**Open questions:**
- What metadata format? Embed in the `.cs` as attributes? Sidecar YAML? Registered at runtime?
- How does this interact with Rook's existing knowledge evolution (DSPy, A-MEM)?

---

### 3. Agent-Interactive Components — "Visual DSPy for Design"

**Status:** `[exploring]` → **HIGH ENERGY**

Components that actively communicate with AI agents during execution — not just passive compute nodes. This is the one that changes everything.

#### The DSPy Parallel — Structural, Not Superficial

Having reviewed the DSPy source code in depth, the parallel to Grasshopper is deeper than "composable modules in a pipeline." DSPy's core innovation is **not** prompt optimization — it's the **Signature-as-Contract** pattern: a Pydantic-based typed I/O declaration that makes the LLM just another backend behind a structured interface.

DSPy's architecture is a three-stage pipeline:
```
Signature (typed contract) → Adapter.format() → LM call → Adapter.parse() → validated output
```

The LLM is not special in DSPy. It's plugged into a type-safe module system via thin adapters. `Predict` is both a `Module` and a `Parameter` — the minimal glue between a typed signature and an LM provider. `ChainOfThought` just prepends a `reasoning` output field to the signature and delegates to `Predict`. `ReAct` dynamically appends tool-call fields. These are **composition patterns over typed contracts**, not prompt engineering tricks.

The structural mapping to Grasshopper:

| DSPy | Grasshopper / Chirp | Why This Is The Same Thing |
|------|---------------------|---------------------------|
| **Signature** (Pydantic-based typed I/O contract) | **RegisterInputParams / RegisterOutputParams** (typed I/O contract) | Both declare what goes in and what comes out, with types enforced at boundaries |
| **Module** (composable callable, returns `Prediction`) | **GH_Component** (composable node, outputs via `DA.SetData`) | Both are units of computation with discoverable parameters |
| **Predict** (binds signature to LM, handles format/parse) | **SolveInstance** body (binds inputs to computation, handles get/set) | The execution core where typed inputs become typed outputs |
| **Adapter** (format/parse bridge: signature ↔ LLM text) | **Rook HTTP bridge** (format/parse bridge: GH data ↔ LLM text) | Decouples the type contract from the LLM's native format |
| **Pipeline** (modules wired in `forward()`) | **GH definition** (components wired on canvas) | Composition topology — but GH makes it visual |
| **`named_parameters()`** (recursive parameter discovery) | **Canvas introspection** (Rook sees all components + connections) | Both enable optimization by making the full graph discoverable |
| **Trace** (execution log per predictor call) | **Rook session recording** (every solve is traceable) | Both collect the data that enables learning |
| **Teleprompter** (optimizes demos/prompts from traces) | **Rook A-MEM + MABWiser** (evolves knowledge from usage) | Both improve module behavior from execution history — optimization is a *consequence* of the structure, not the point |

**The key insight: Grasshopper already IS a visual DSPy-like framework.** It has typed I/O contracts (RegisterParams), composable modules (components), a pipeline topology (the canvas), and reactive evaluation (the solver). What it lacks is the **Adapter layer** — the bridge that lets a component's SolveInstance call an LLM through a typed contract and get structured results back. That's what Chirp provides.

**This means Grasshopper becomes a visual programming environment for AI-augmented design pipelines.** Some nodes are pure geometry (deterministic). Others have an LLM brain (intelligent). The wires carry typed data between them just like any GH definition — but some of those nodes are _thinking_, and they're thinking through typed contracts, not raw prompt strings.

#### Concept

- A component's `SolveInstance` calls Rook's HTTP API (localhost:9950+) or directly calls an LLM API to request AI reasoning
- The component takes structured inputs (geometry, numbers, text) and produces structured outputs — but the _transformation_ is LLM-driven
- Each component has a **prompt signature** (like DSPy's `Signature`) that defines what the LLM sees and what it must return
- Canvas context is available — a component can ask "what else is connected to me?" and reason about the broader definition

#### Concrete Examples

**"Intent Router" component:**
- Input: text description ("create a diagrid on this surface")
- Input: geometry context (what's upstream)
- Output: structured parameters that downstream deterministic components consume
- The LLM translates intent into precise numeric parameters

**"Design Critic" component:**
- Input: geometry from upstream
- Input: design rules (text or structured)
- Output: pass/fail boolean
- Output: text explanation of what's wrong and suggestions
- Output: annotated geometry (highlighted problem areas)
- Acts as an AI-powered design review gate within the definition

**"Adaptive Subdivider" component:**
- Input: surface + intent ("dense near edges, sparse in center")
- Output: subdivision mesh
- The LLM decides the UV counts and grading strategy, then calls deterministic subdivision code
- Different from a parametric subdivider: the parameters aren't exposed, the _intent_ is

**"Material Recommender" component:**
- Input: geometry + structural loads + climate data
- Output: material specification (text)
- Output: material properties (structured data for downstream analysis)
- Draws on LLM world knowledge about materials, not a fixed database

**"Explain" component (meta-component):**
- Input: any geometry
- Input: the upstream component graph (via canvas introspection)
- Output: human-readable narrative of what the definition is doing and why
- Output: formatted text panel content
- Makes definitions self-documenting

#### Why Rook Makes This Possible (And Why Nobody Else Can Do It)

The infrastructure already exists:
- **Canvas awareness:** Rook's GH knowledge system knows the component graph, connections, values
- **Scene graph:** spatial context for geometry-aware reasoning
- **Knowledge evolution:** Rook's DSPy + A-MEM pipeline can optimize component prompts over time (the DSPy Optimizer parallel)
- **Session recording:** every solve is traceable (the DSPy Trace parallel)
- **Multi-agent system:** complex components could spawn Rook sub-agents for heavy reasoning
- **HTTP bridge:** components can call localhost:9950 from SolveInstance

Without Rook, an agent-interactive component is just a slow API call. With Rook, it's a **node in a knowledge-aware, self-optimizing design reasoning system**.

#### Variations

- **Agent-as-solver:** Component delegates its core logic to an LLM call
- **Agent-as-validator:** Component runs its own logic but asks an agent to verify the result
- **Agent-as-configurator:** Component has many parameters, agent sets them based on natural language intent
- **Agent-as-explainer:** Component produces geometry + a human-readable explanation of what it did and why
- **Agent-as-router:** Component takes natural language and produces structured parameters for downstream deterministic components
- **Agent-as-critic:** Component evaluates upstream results against design criteria and provides feedback

#### What Makes This DSPy, Not Just "LLM in a Node"

DSPy's real power isn't prompt optimization — it's the **structural embedding of LLMs within typed contracts**. The optimization is a _consequence_ of making the structure right. Three things make Chirp components structurally DSPy-like rather than just "components that call an API":

**1. Typed I/O contracts (Signature equivalence):**
Every Chirp component declares exactly what the LLM sees and what it must return, as typed fields — not as a freeform prompt string. This is the Signature pattern. The component's spec declares `inputs` with types and `outputs` with types. The Adapter layer (Rook bridge or direct API) handles formatting inputs into LLM messages and parsing LLM text back into typed outputs. The component author never writes a prompt — they declare a contract.

**2. Composability via the canvas (Module equivalence):**
In DSPy, you compose modules by calling them in `forward()`. In Grasshopper, you compose components by wiring them on the canvas. The result is the same: a typed pipeline where each module's outputs feed the next module's inputs. But Grasshopper makes the topology _visible_ and _manipulable_ — a designer can rewire the pipeline without writing code.

**3. Parameter discovery enables learning (not the other way around):**
Because DSPy's modules expose `named_parameters()` and `named_predictors()`, the framework can discover all LLM-interfacing components and collect traces. Because Rook can introspect the GH canvas (it knows every component, connection, and value), it can do the same thing. This makes optimization _possible_ — trace collection, few-shot evolution via A-MEM, strategy selection via MABWiser — but the optimization is downstream of the structure. Get the typed contracts right and the learning follows.

Over time, the components literally get smarter. Not because the LLM improved, but because the typed contracts + trace collection enable Rook to evolve better few-shot examples and prompt strategies from real usage data.

#### Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| **Latency** — LLM calls in SolveInstance make canvas sluggish | Use `GH_TaskCapableComponent<T>` for async solving. Show spinner/placeholder. Cache by input hash. |
| **Non-determinism** — same inputs, different outputs across solves | Explicit "seed" input for reproducibility. Cache previous results. "Lock" mode that freezes output. Temperature=0 default. |
| **Cost** — API calls per solve iteration on large definitions | Aggressive caching (input hash → output). Solve-on-demand (not auto-solve). Budget tracking per component. Rook's existing cost monitoring. |
| **Debugging** — hard to understand why a component produced its output | Every solve logs the full prompt + response. "Explain" output pin on every AI component. Trace viewer in Rook dashboard. |
| **Data trees** — GH iterates SolveInstance per branch/item; N items = N API calls | Batch mode: collect all items, send as single prompt with list, parse list response. Amortize across data tree. |
| **Offline use** — no internet = no LLM = broken definition | Fallback to cached results. Optional local model (Ollama) support. Graceful degradation with warning message. |

#### Open Questions

- What's the base class? `GH_TaskCapableComponent<T>` for async, or a new `ChirpComponent` base that handles the LLM plumbing?
- How does the component discover Rook's HTTP port? Env variable? Discovery file in %TEMP%?
- Should components call the LLM directly (Anthropic API) or route through Rook's agent system?
- Canvas introspection: how much context should a component have about its neighbors? Full graph? Just immediate connections?
- Can a component's prompt be edited by the user in GH (like a script component) or is it sealed?

#### First Prototype Candidates

What should the first prototype component be? Small enough to build quickly, meaty enough to prove the concept:

- **A) "Intent to Parameters"** — takes a text string like "dense near edges" + a surface, outputs UV counts. Simplest possible AI-in-a-node. Proves the plumbing works.
- **B) "Design Critic"** — takes geometry + design rules text, outputs pass/fail + explanation. Proves the feedback/validation pattern.
- **C) "Explain"** — takes any upstream geometry, introspects the canvas, outputs a narrative. Proves canvas awareness works.

**Decision:** TBD — revisiting after full landscape exploration.

---

### 4. On-Demand Component Generation

**Status:** `[exploring]`

Rook describes what it needs, Chirp generates the component at runtime, and it appears on the canvas.

**Concept:**
- During a design cascade, Rook's planner determines that no existing component does what's needed
- It writes a Chirp spec, calls `codegen.py`, gets a compiled `.cs` (or `.gha`)
- The component is loaded into the running Grasshopper session
- Rook places it on the canvas and wires it up

**What this enables:**
- Infinite component library — if it doesn't exist, generate it
- Project-specific components without manual authoring
- The line between "using Grasshopper" and "extending Grasshopper" disappears

**Technical challenges:**
- Hot-loading compiled assemblies into a running Rhino/GH session
- GH_AssemblyInfo registration for dynamically generated plugins
- Component GUID management (must be stable for serialization)
- Icon generation (24x24 bitmaps)
- Testing/validation before placement

**Open questions:**
- Is runtime assembly loading feasible in Rhino 8's .NET 7 host? Or does it require a restart?
- Could we use Grasshopper's C# Script component as an intermediate step (inject generated code into a script node)?
- What's the failure mode? If generation fails mid-cascade, how does Rook recover?

---

### 5. Chirp as a Rook Skill

**Status:** `[exploring]`

Instead of a standalone tool, Chirp becomes a phase in Rook's existing design cascade (Design → Plan → Execute → Learn).

**Concept:**
- A new skill: `generate-component` that fits into the cascade
- When the planner identifies a gap in the component library, it invokes Chirp
- Generated components flow into Rook's knowledge graph automatically
- The consolidation phase (Phase 4) captures what worked and what didn't

**What this enables:**
- No separate toolchain — Chirp is just another Rook capability
- Knowledge graph benefits: generated components are immediately indexed
- Cascade integration: component generation is planned, not ad-hoc

**Open questions:**
- Does this subsume the standalone `codegen.py` approach, or complement it?
- Should Chirp specs be a new knowledge note type in Rook's unified store?

---

### 6. Firm-Specific Component Libraries

**Status:** `[exploring]`

Chirp generates not just individual components but curated, firm-branded component suites.

**Concept:**
- Safdie-specific component categories (Structure, Envelope, Massing, Analysis, etc.)
- Consistent naming, icons, error handling, and documentation style
- A "Safdie GHA" plugin that ships as a unit, compiled from specs
- Other firms could fork the spec library and generate their own branded suites

**What this enables:**
- Institutional knowledge embedded in tooling, not just documentation
- New team members get firm-specific tools on day one
- Standards enforcement through generation constraints, not code review

**Open questions:**
- How many components does Safdie actually need in a first release?
- What's the build/deploy pipeline for the compiled .gha?
- Version management when specs evolve?

---

### 7. Bidirectional Spec Sync (CodeSpeak "Takeover")

**Status:** `[exploring]`

CodeSpeak has a "takeover" mode: point it at existing hand-written code, and it generates specs from the code. The reverse of generation.

**Concept:**
- Point Chirp at existing Safdie GH components → extract specs
- From that point forward, specs are the source of truth, not code
- Edits happen to specs; code is regenerated
- Drift detection: if someone edits the .cs directly, flag the divergence

**What this enables:**
- Migration path for existing component libraries
- Specs become the single source of truth for component behavior
- AI agents can reason about component behavior by reading specs, not parsing C#

**Open questions:**
- How accurate can spec extraction from existing C# code be?
- What's the human review workflow for extracted specs?
- Does this require CodeSpeak's infrastructure, or can we build a simpler version?

---

### 8. Component-as-API — Self-Registering Rook Tools

**Status:** `[exploring]`

Chirp components that register themselves as callable Rook tools when loaded — inverting the agent-to-canvas relationship.

**Concept:**
- Today Rook drives components from the _outside_: place on canvas via reflection, wire inputs, set values, read outputs
- What if Chirp components registered themselves _as MCP tools_ when loaded into GH?
- A "Diagrid Generator" component would appear in Rook's tool list as `chirp_diagrid_generator(surface, u_count, v_count)` — callable directly without touching the canvas
- Same component, two interfaces: visual (canvas node for humans) and programmatic (tool for agents)

**What this enables:**
- Agent can call component logic directly — no canvas manipulation overhead
- Human can place the same component on canvas for interactive parametric control
- Component library is simultaneously a tool library
- Rook's planner can reason about Chirp capabilities as first-class tools, not just "things I can place on a canvas"
- Potential for headless execution — run a Chirp component pipeline without opening Grasshopper at all

**How it could work:**
- On GHA load, a registration hook iterates all Chirp components and calls Rook's HTTP API to register them as available tools
- Each component's spec (inputs, outputs, types, descriptions) maps directly to an MCP tool schema
- When Rook calls the tool, it instantiates the component in-memory, feeds inputs, runs SolveInstance, returns outputs — no canvas needed
- Optionally, the agent can _also_ place the component on canvas if the user should see/interact with it

**Relationship to other opportunities:**
- Combines with **#2 (AI-Discoverable)**: the spec that drives generation also drives tool registration
- Combines with **#3 (Agent-Interactive)**: an AI-native component that's also a tool could be called by _other_ AI-native components, creating agent-to-agent chains
- Combines with **#5 (Chirp as Rook Skill)**: generated components auto-register as tools in the cascade

**The Canvas-vs-API Tension (resolved by the Foundational Analysis):**

The question "why not just call it as an API and skip the canvas?" answers itself when you look at the complementarity table. The canvas IS the value — it gives persistence, reactivity, undo, and legibility that a bare API call doesn't have. So the dual-interface isn't "canvas OR API" — it's:

- **API mode:** for autonomous agent work where the human doesn't need to see/tweak the logic (batch processing, validation, analysis)
- **Canvas mode:** for collaborative design where the human needs to understand, explore, and modify the parametric relationships

The component doesn't decide. The _context_ decides. An agent running a batch analysis at 2am uses the API. A designer exploring massing options with the agent uses the canvas. Same component, right interface for the moment.

**Open questions:**
- Does Rook's MCP server need to be aware of Chirp tools at startup, or can they register dynamically?
- Can a component running as a tool still access RhinoDoc? Or is it sandboxed?
- What's the serialization story — if an agent builds something via API, can it later "materialize" on canvas for the human to pick up?

---

### 9. Canvas-as-Narrative / Intent Metadata (PARKED)

**Status:** `[parked]` — interesting idea, wrong medium

**The idea:** Chirp components carry intent metadata that survives across sessions — not just "SubD component with these inputs" but "this node exists because the designer said 'I want the facade to breathe.'" The canvas becomes a narrative both humans and future agent sessions can read.

**Why it's parked:** Rook's session recorder already maps intent → tool chain calls as lightweight structured data. That data is pure, amenable to ML pipelines, and doesn't require GH overhead. Embedding the same narrative inside component metadata would be a heavier, redundant copy of what Rook already captures better. Intent belongs in Rook's data layer, not in the component.

**Design principle extracted:** Don't put things in the component that belong in Rook's data layer. Components are compute nodes, not journals. Rook records the story; components do the work.

**Also considered and skipped:** "AI-as-sensor" components that give LLMs spatial perception (vision model on viewport captures, proportion analysis, collision detection). Skipped because LLMs can already use vision APIs on 2D projections effectively — Rook can capture a viewport and send it to a vision model as a tool call. No GH component needed. Same principle: don't componentize what Rook handles better as a lightweight tool call.

---

## Technical Research

### Hot-Reload Feasibility in Rhino 8 (Researched 2026-03-13)

**Bottom line: Yes, but through a proxy pattern — not through GH's native loading.**

Three approaches investigated:

#### Approach A: Native GHA loading at runtime — NOT FEASIBLE
- `GH_ComponentServer` has no public `LoadGHA()` method
- GH loads all .gha files at startup; no API to add more after initialization
- The `ObjectProxies` list (`IList<IGH_ObjectProxy>`) technically has `Add()` but this is undocumented and likely incomplete (internal state won't update)
- This is the standard pain point in GH development — restart Rhino every rebuild

#### Approach B: Collectible AssemblyLoadContext — FEASIBLE
- .NET 7 (which Rhino 8 runs on) fully supports `AssemblyLoadContext` with collectible/unloadable contexts
- You can load a compiled assembly at runtime, execute code from it, then unload it and load a new version
- Rhino/GH SDK doesn't use this internally (searched all McNeel repos, zero references) but nothing prevents a plugin from using it
- **The proxy pattern:** A single Chirp GH_Component (loaded normally as a .gha) acts as a host. It uses Roslyn to compile generated C# into an in-memory assembly in a collectible ALC, invokes methods via reflection, and returns outputs. When code changes, unload old context, create new one.
- This sidesteps the GH component registration problem entirely — the proxy is registered once, the hot-loaded code runs inside it

#### Approach C: Inject into C# Script component — PARTIALLY FEASIBLE
- GH's C# Script component already compiles and runs C# at runtime (strongly implies Roslyn under the hood via `#r "nuget:"` syntax)
- No documented public API for setting a script component's code programmatically
- Could potentially create one via serialization (build a .ghx XML snippet with the code, deserialize into the document)
- Rook already has canvas manipulation tools that could place and configure script components
- Less clean than Approach B but requires no custom assembly loading

#### Implications for Chirp

The **proxy pattern (Approach B)** is technically feasible but may be over-engineered. See "The Recipe vs. Component Question" below.

#### The Recipe vs. Component Question

Rook's `gh_edit` endpoint already creates entire GH definitions atomically in ~200 tokens. The recipe system stores and replays reusable graph patterns. This raises a fundamental question: **what does a compiled GH_Component give you that a `gh_edit` recipe with an injected C# Script component doesn't?**

| | Compiled Component (.gha) | Recipe + Script Component |
|---|---|---|
| **Build step** | Requires C# compilation, .gha packaging | None — recipe is pure data |
| **Hot-reload** | Needs AssemblyLoadContext proxy pattern | Free — just update the script code |
| **UX** | Named component in ribbon, icon, discoverable | Generic "C# Script" node on canvas |
| **Distribution** | Ship a .gha file | Ship a recipe JSON in Rook's knowledge store |
| **Agent access** | Via canvas manipulation or Component-as-API | Already native to Rook's `gh_replay_recipe` |
| **Human editing** | Requires recompilation | Double-click the script node, edit code |
| **Knowledge graph** | Needs registration hooks | Recipes are already in the knowledge layer |

**The recipe approach wins on simplicity.** The compiled approach wins on UX and discoverability for human users who browse the component ribbon.

**Possible synthesis:** Start with recipes for rapid prototyping and agent-driven workflows. Graduate proven recipes to compiled components when they need to be distributed to non-agent users (i.e., designers at Safdie who don't use Rook). This is the CodeSpeak value prop applied correctly: specs become compiled components for distribution, but development and iteration happen at the recipe level.

This also means the original Chirp vision (YAML spec → compiled .cs) is most valuable as a **packaging step**, not a development step. You develop AI-native behaviors as recipes with script components, iterate fast, and when something is stable you "compile" it into a proper component for the firm library.

---

### DSPy Architecture Reference (from source review, 2026-03-13)

Reviewed the DSPy source to understand the structural pattern Chirp should parallel. Key findings:

#### The Core Pattern: Signature → Adapter → LM → Adapter → Validated Output

DSPy's architecture has five layers:

```
User Program (dspy.Module subclass)
    ↓
Signature (Pydantic BaseModel — typed I/O contract with field descriptions)
    ↓
Adapter (format/parse bridge — ChatAdapter, JSONAdapter, XMLAdapter)
    ↓
LM Client (provider abstraction via LiteLLM — any model, same interface)
    ↓
External LLM
```

**The LLM is not special.** It's plugged in at a thin interface. Everything above the LM Client is about **typed structure**, not prompting.

#### Key Classes and What They Do

- **`Signature`** (Pydantic `BaseModel` with `SignatureMeta` metaclass): Declares typed input/output fields. Instructions come from the docstring. Fields have types, descriptions, and optional defaults. Signatures are composable — `.prepend()`, `.append()`, `.insert()` to add fields dynamically. `ChainOfThought` literally just prepends a `reasoning: str` output field.

- **`Module`** (base class via `ProgramMeta` metaclass): Composable callable. `__call__` delegates to `forward()`. Exposes `named_parameters()` for recursive parameter discovery and `named_sub_modules()` for recursive module discovery. This is what makes the graph introspectable.

- **`Predict`** (both `Module` and `Parameter`): The binding point. Takes a Signature, holds an LM reference and demo examples. `forward()` does: preprocess inputs → call `Adapter.format()` → call `LM()` → call `Adapter.parse()` → return `Prediction`. The Predict author never writes a prompt.

- **`Adapter`** (abstract base): The format/parse bridge. `format(signature, demos, inputs) → messages` converts typed contracts into LLM message format. `parse(signature, completion) → dict` extracts typed outputs from LLM text and validates against the signature's output field types. Different adapters handle different formats (chat delimiters, JSON, XML) — same signature works with all of them.

- **`Prediction`** (inherits from `Example`): Typed result container. Supports multi-generation via `.completions[i]`. Tracks token usage. The output of every module call.

#### What This Means for Chirp

The Adapter pattern is the critical missing piece. Grasshopper already has:
- **Signatures**: `RegisterInputParams` / `RegisterOutputParams` with typed fields
- **Modules**: `GH_Component` subclasses with `SolveInstance`
- **Composition**: Canvas wiring = pipeline topology
- **Parameter discovery**: Rook's canvas introspection

What Grasshopper lacks is the **Adapter layer** — the typed bridge between a component's I/O contract and an LLM. Chirp's core contribution is this bridge: a format/parse layer that takes the component's registered inputs, formats them into an LLM call according to the spec's contract, parses the LLM's response back into typed GH outputs, and hands them to `DA.SetData`.

The spec YAML is the Signature. The Adapter is Chirp's runtime library. The canvas is the pipeline. Rook is the optimizer.

---

### The Deterministic/Probabilistic Boundary

One of the key tensions in any LLM workflow is balancing deterministic outputs with the probabilistic degrees of freedom of LLM intelligence. This tension is central to Chirp's design and deserves explicit treatment.

#### The Spectrum

Every component sits somewhere on a spectrum:

```
DETERMINISTIC ◄──────────────────────────────► PROBABILISTIC
   │                                                │
   │  Pure geometry math                            │  Raw LLM output
   │  Same inputs → same outputs, always            │  Same inputs → different outputs
   │  No API calls, no cost, instant                │  API calls, cost, latency
   │  Fully debuggable                              │  Opaque without traces
   │  No world knowledge                            │  Rich world knowledge
   │  Rigid — only does exactly what it's told       │  Flexible — interprets intent
   │                                                │
   └── Traditional GH components                    └── Pure "ask the LLM" components
```

Most valuable Chirp components will sit **in the middle** — using the LLM for the parts that require judgment while keeping the geometry math deterministic. The "Adaptive Subdivider" example: the LLM chooses UV counts (probabilistic judgment), then deterministic subdivision code produces the mesh.

#### Design Principle: Make the Boundary Visible

Users (and agents) need to know which parts of a definition are deterministic and which are probabilistic. This suggests:

- **Visual distinction** on canvas — AI-native components should look different from deterministic ones (different color, icon badge, or outline)
- **Explicit typing** — outputs from LLM-driven components could carry a "confidence" or "source" metadata so downstream components know whether their input was computed or inferred
- **Lock/freeze** — any probabilistic component should support locking its output so it becomes deterministic (cached) until explicitly re-solved
- **Deterministic fallback** — when possible, an AI component should degrade gracefully to a deterministic default if the LLM is unavailable

#### How This Informs the Proxy Pattern

The `ChirpHost` proxy component could handle both sides of the spectrum:
- **Deterministic mode:** hot-loads compiled C# code (Approach B) — pure geometry, no LLM
- **Probabilistic mode:** routes inputs to an LLM call via Rook — AI-driven judgment
- **Hybrid mode:** LLM decides parameters, compiled code does geometry — the sweet spot

Same proxy, configured by the spec. The spec declares which inputs go to the LLM and which go to deterministic code. The boundary is explicit in the spec, visible on the canvas, and configurable by the user.

---

## Emerging Themes

As we explore, some cross-cutting themes are appearing:

1. **The spec is the interface** — Whether generating, discovering, or modifying components, the YAML spec is the contract between human intent and machine execution. Getting this format right is foundational.

2. **Knowledge graph integration** — Rook's existing knowledge systems (919 components, 196 notes, pattern memory) are a natural home for Chirp metadata. The question is how tightly to couple them.

3. **The compilation boundary** — Some opportunities (1, 4, 6, 7) require actual C# compilation. Others (2, 3, 5) could work with runtime injection or metadata alone. This is a key architectural decision.

4. **Determinism vs. intelligence** — Traditional GH components are pure functions. Agent-interactive components introduce non-determinism. The design must make this boundary explicit to users.

5. **Hot-loading vs. build-and-deploy** — Runtime component generation is the most exciting possibility but also the hardest technically. Build-and-deploy is simpler but less magical.

6. **Grasshopper as visual DSPy** — The deepest theme. GH already has typed I/O contracts (RegisterParams) and composable modules (components) wired into pipelines (definitions). What it lacks is the **Adapter layer** — the format/parse bridge that lets a component's SolveInstance call an LLM through a typed contract and get structured results back. That's what Chirp provides. The learning (Rook's A-MEM, MABWiser) follows from the structure, not the other way around.

7. **Separation of concerns: components compute, Rook remembers** — Don't embed metadata, intent, or narrative in components when Rook's data layer (session recorder, knowledge graph) already handles it better as lightweight structured data amenable to ML. Components should be lean compute nodes. Rook owns the story.

---

## The Synthesis: Specs as Dual-Compilation Artifacts

Two threads emerged independently in this exploration and converge into something new.

### Thread 1: Token-Efficient Compression

Both `gh_edit` and CodeSpeak are doing the same fundamental thing: **compressing known structures into token-efficient transfer formats** for LLMs to use within limited context windows.

- `gh_edit` compresses a full Grasshopper definition (which would require dozens of tool calls) into ~200 tokens of flow strings: `C1.O0>C2.I1`
- CodeSpeak compresses a full function implementation (which would require pages of boilerplate) into a few lines of spec YAML
- Both identify what's **invariant** (the structure, the scaffolding, the wiring patterns) and strip it away, leaving only what **varies** (the intent, the parameters, the logic)

The drivers are efficiency, speed, and staving off context window collapse. The less boilerplate in the context window, the more room for the thing that matters: the design logic.

### Thread 2: DSPy-Style Structural LLM Embedding

DSPy's core innovation is not prompt optimization — it's the **Signature-as-Contract** pattern: embedding LLMs within typed I/O declarations so the LLM becomes just another backend behind a structured interface. The three-stage pipeline (`Signature → Adapter.format() → LM call → Adapter.parse() → validated output`) means the module author never writes a prompt. They declare a contract: these typed inputs go in, these typed outputs come out, and the Adapter layer handles the messy translation to/from LLM text.

This is exactly the Agent-Interactive Components concept (Opportunity #3): GH nodes where the I/O contract is fixed and typed (RegisterInputParams/RegisterOutputParams), but the transformation inside SolveInstance routes through an LLM via a typed contract. The component doesn't prompt-engineer. It declares what it needs and what it returns. An Adapter layer (Rook's HTTP bridge, or a direct API adapter) handles formatting and parsing.

### The Convergence: A Spec That Compiles in Two Directions

A CodeSpeak spec and a DSPy Signature are the **same artifact viewed from different angles**:

- A spec describes *what* a function does so the LLM can generate *how* → **compiles down to deterministic code**
- A Signature describes *what* an LLM module does (typed inputs, typed outputs, instruction) → **compiles into a typed contract that an Adapter bridges to the LLM**

Both are compressed, declarative descriptions of behavior. Both eliminate boilerplate — one eliminates code boilerplate, the other eliminates prompt boilerplate. And critically, both enforce **structure at the boundary**: the spec ensures the generated code has the right shape; the Signature ensures the LLM's output has the right shape.

**A Chirp spec could do both simultaneously.** A single YAML artifact that describes:

1. The **deterministic scaffolding** — inputs, outputs, type checking, GH boilerplate → compiles to C# structure
2. The **LLM behavior** embedded within that structure — what the intelligence should do with the inputs → compiles to an optimized prompt/chain

```yaml
# Hypothetical dual-compilation spec
component: AdaptiveSubdivider
category: Chirp
subcategory: Intelligence

inputs:
  - name: Surface
    type: Surface
    target: deterministic    # goes to geometry code
  - name: Intent
    type: string
    target: llm              # goes to the prompt
    example: "dense near edges, sparse in center"

outputs:
  - name: Mesh
    type: Mesh
    source: deterministic    # produced by geometry code
  - name: Reasoning
    type: string
    source: llm              # produced by the LLM

llm:
  signature: "Given a surface and a design intent, determine UV subdivision counts and grading parameters"
  output_schema:
    u_count: int
    v_count: int
    grading: float  # 0=uniform, 1=max edge bias
  temperature: 0
  optimize: true  # enable Rook's prompt evolution on this component

deterministic:
  method: subdivide_surface  # the geometry code that receives LLM-chosen parameters
  doc_access: false
```

This spec is **both** a CodeSpeak spec (compresses the C# boilerplate) **and** a DSPy signature (defines the LLM's I/O contract). One artifact, two compilation targets.

### What This Unlocks

**The Grasshopper canvas becomes the orchestration layer that DSPy normally provides programmatically:**

| DSPy Programmatic | Chirp Visual | What's Shared |
|---|---|---|
| Compose modules in `forward()` | Wire components on the GH canvas | **Typed pipeline topology** |
| Signature as Pydantic class | Spec as YAML (inputs/outputs/types) | **Declarative I/O contract** |
| Adapter.format() / Adapter.parse() | Rook HTTP bridge or direct API adapter | **Format/parse bridge to LLM** |
| `Predict(signature)` binds contract to LM | `SolveInstance` routes through adapter | **Typed execution core** |
| `named_parameters()` discovers predictors | Canvas introspection discovers components | **Structure enables learning** |
| Teleprompter optimizes from traces | Rook A-MEM + MABWiser from session data | **Learning is downstream of structure** |

**What else can you do with the spec once you have it:**

- **Enforce contracts** — The spec declares typed I/O for both the deterministic code and the LLM. The Adapter layer validates that the LLM's output conforms before it enters the GH data stream. No hallucinated types leak into the canvas.
- **Compose visually** — Non-programmers wire together deterministic and probabilistic components on a canvas, seeing exactly where the intelligence boundaries are (the `target: llm` / `source: llm` fields make it explicit). The canvas IS the pipeline definition.
- **Swap backends** — Same spec, different Adapter. Route through Anthropic, OpenAI, a local Ollama model, or Rook's agent system. The component doesn't know or care — it declares a contract; the adapter fulfills it.
- **Swap compilation targets** — Same spec → compiled C# component for production distribution, script component + recipe for development, pure LLM call for headless batch processing. The spec is the source of truth; the runtime is a deployment choice.
- **Version and diff** — Specs are tiny YAML. They go in git, they diff cleanly, they review in PRs. The generated code (both C# and prompts) is an artifact, not a source.
- **Introspect** — An agent reading the spec knows both what the component computes deterministically AND what it asks the LLM. Full transparency of the deterministic/probabilistic boundary.
- **Learn** — Because the structure is right (typed contracts, discoverable parameters, traceable execution), optimization follows naturally. Rook can collect traces, evolve few-shot examples, and improve prompt strategies — all without changing the spec.

### The New Programming Artifact

This is genuinely new: **a programming artifact that is partially compiled to code and partially compiled to prompts, orchestrated by a visual dataflow graph that makes the deterministic/probabilistic boundary visible and manipulable by designers.**

The designer sees components on a canvas. Some are pure geometry (fully deterministic). Some have an LLM brain (the spec says so, the visual styling shows it). The wires between them carry typed data. The Rook knowledge system optimizes the LLM components over time. And the entire thing is described by a set of small YAML files that compress all the boilerplate — both code boilerplate and prompt boilerplate — into token-efficient specs.

Neither CodeSpeak alone (compresses code, but no LLM embedding) nor DSPy alone (composes LLM modules, but no visual graph or deterministic geometry) produces this. It's the intersection, enabled by Grasshopper's dataflow graph and Rook's knowledge infrastructure.

---

## What Chirp Actually Is

The exploration converged on a definition. Chirp is **two deliverables** that enable Rook to create intelligent Grasshopper components on the fly:

### 1. The Runtime Library (C# .dll) — The Adapter Layer

A shared library that any GH script component can reference. It handles the format → LLM call → parse → validate → cache → trace cycle. A script component calls it in ~8 lines:

```csharp
var chirp = new ChirpAdapter("http://localhost:9950");
var result = chirp.Call(
    signature: "Given a surface and design intent, determine subdivision parameters",
    inputs: new { surface = Surface.ToString(), intent = Intent },
    schema: new { u_count = typeof(int), v_count = typeof(int), grading = typeof(double) }
);
A = result.Get<int>("u_count");
B = result.Get<int>("v_count");
C = result.Get<double>("grading");
```

The library absorbs all the plumbing: HTTP client, JSON serialization, response parsing, type coercion, error handling, caching by input hash, trace logging. The script author (or Rook) declares a contract. The library fulfills it.

### 2. The Creation Tool — Token-Efficient Intelligent Node Generation

A Rook tool (or recipe format extension) that compresses the specification of an intelligent node into ~100 tokens:

```
chirp_create(
    pins_in:  ["Surface:Surface", "Intent:string"],
    pins_out: ["UCount:int", "VCount:int", "Grading:double"],
    signature: "Given a surface and design intent, determine subdivision parameters",
    schema: {u_count: int, v_count: int, grading: double},
    deterministic: "// code that uses LLM outputs to subdivide Surface → Mesh"
)
```

Rook calls this. The system generates a script component with the Chirp library call inside, sets the typed pins, places it on canvas. Same token-efficiency principle as `gh_edit` — compress the invariant structure, transmit only what varies.

### Why This Works

**The typed output pins are the structural constraint.** Whatever the LLM does inside the script — however flexibly it interprets inputs, however much world knowledge it brings — the result gets squeezed through fixed, typed output pins enforced by the GH runtime. The canvas downstream always receives the types it expects. The probabilistic computation is invisible to the rest of the graph.

This is the DSPy Signature pattern enforced physically by Grasshopper's type system. The component is a **structured boundary between open-ended intelligence and deterministic dataflow**: flexible inputs (accept intent as text), flexible processing (LLM interprets, judges, adapts), rigid outputs (fixed number, fixed types, enforced by runtime).

**Rook is the component author.** It doesn't just place existing components — it designs intelligent nodes on the fly as script components with typed pins and LLM calls inside. The designer says "I need something that interprets facade density intent." Rook decides the pins, the signature, the schema. Rook calls `chirp_create`. The component appears on canvas.

**Rook can chain them.** Multiple intelligent script components wired together — one interprets intent, one generates parameters, one critiques output. That's a DSPy pipeline, created on the fly by an agent, visible on the canvas, with typed contracts at every boundary.

### The Graduation Path

Rook-generated script components are the development medium. When a component has been used enough that it's proven, stable, and needs distribution to designers who don't have Rook, it graduates to a compiled component via the original Chirp vision (spec → compiled .cs → .gha). Recipes for development, compiled components for distribution.

### Architecture Summary

```
Designer intent (natural language)
    ↓
Rook (designs the intelligent node: decides pins, signature, schema, deterministic code)
    ↓
chirp_create tool (token-efficient creation: ~100 tokens → full script component)
    ↓
Script component on canvas
    ├── Typed input pins = Signature input fields
    ├── Script body calls ChirpAdapter (the Adapter layer)
    │   └── format → LLM call → parse → validate → cache → trace
    ├── Deterministic code uses LLM outputs to produce geometry
    └── Typed output pins = Signature output fields (structural constraint)
    ↓
Canvas wiring = pipeline topology (visual DSPy)
    ↓
Rook knowledge system = optimizer (evolves few-shot demos from traces)
```

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-13 | Start with Phase 1-2 (templates + spec format) before building code | Quality of everything downstream depends on the spec format |
| 2026-03-13 | Use mcneel/rhino-developer-samples as reference patterns (no existing Safdie components) | Starting fresh; samples cover the full GH_Component pattern space |
| 2026-03-13 | Expand scope beyond original brief to explore AI-native component design | Rook's capabilities open opportunities not envisioned in the original brief |
| 2026-03-13 | Agent-interactive components ("Visual DSPy") identified as highest-energy opportunity | Unique to Rook's infrastructure; no one else has canvas-aware, knowledge-evolving AI components |
| 2026-03-13 | Hot-reload confirmed feasible via proxy pattern (collectible AssemblyLoadContext) | .NET 7 supports it; no GH native support but proxy sidesteps the problem |
| 2026-03-13 | Components compute, Rook remembers — don't embed narrative/intent in components | Rook's session recorder already handles intent→action mapping as lightweight structured data |
| 2026-03-13 | Deterministic/probabilistic boundary must be explicit in spec and visible on canvas | Key design tension — users and agents need to know which outputs are computed vs. inferred |
| 2026-03-13 | Recipes (gh_edit + script components) may be the development medium; compiled components are the distribution medium | Rook's gh_edit already creates full graphs in ~200 tokens; no need to compile during iteration |
| 2026-03-13 | Core synthesis: Chirp spec = dual-compilation artifact (code + prompt) | CodeSpeak compression and DSPy LLM embedding converge — a spec describes both the deterministic scaffolding and the LLM behavior, compiled to different targets from the same source |
| 2026-03-13 | DSPy's core is Signature-as-Contract (typed I/O), not prompt optimization | Source review confirms: the Adapter format/parse bridge is the key abstraction. Chirp's core contribution is this Adapter layer for Grasshopper — the typed bridge between GH component I/O and LLM calls |
| 2026-03-13 | Typed output pins ARE the structural constraint that makes LLM embedding safe | The component's registered outputs filter LLM flexibility through fixed types — downstream is protected. This is DSPy's Signature enforced physically by GH's runtime |
| 2026-03-13 | Chirp = runtime library + creation tool. Rook is the component author. | Rook creates intelligent script components on the fly via chirp_create (~100 tokens). The Chirp runtime library (C# .dll) handles format/parse/validate/cache/trace. No YAML specs as human-authored files — the spec is Rook's internal representation |
| 2026-03-13 | Compiled components are the graduation/distribution step, not the development step | Development happens as Rook-generated script components. Proven components graduate to compiled .gha for firm-wide distribution to non-Rook users |
| 2026-03-13 | Reasoning output pin auto-added to every Chirp component | Exposes the LLM's chain-of-thought as a wireable GH output. Enables design review, teaching, and debugging. Reserved pin name "Reasoning" with collision detection |
| 2026-03-13 | Chirp's unique value vs. Rook: reactive participation in the parametric graph | Rook has the same LLM reasoning + graph visibility, but operates imperatively. Chirp components re-solve automatically when inputs change — they participate in GH's reactive dataflow natively. Rook is the operator; Chirp is a node |
| 2026-03-13 | Natural language as a first-class GH data type is the core product insight | Chirp's deepest value isn't "AI in a node" — it's that strings carrying design intent become wireable signals that propagate through the graph. "Brutalist" in a Panel → coordinated parameter shifts across the model |
| 2026-03-13 | Discrete design (Wasp) identified as high-value integration target | Shape grammar aggregation has a gap between design intent and algorithm configuration. Chirp bridges it: semantic description → aggregation parameters (part ratios, field gradients, constraint modes). See "Wasp Integration" section |

---

## Where Chirp Shines: The Value Proposition (Refined)

*Added 2026-03-13 after extended design discussion*

### The Overlap Problem

Rook (Claude via MCP) already has:
- LLM reasoning about design decisions
- Full GH graph visibility via `gh_snapshot`
- Ability to create/wire components via `gh_execute_intent`
- Domain knowledge about architecture, materials, structures

So what does embedding an LLM inside a GH component add that Rook can't do from the outside?

### The Answer: Reactive Semantic Parametrics

**Rook is imperative.** It acts when asked: "Claude, I changed the span, update the beam depth." The relationships live in the conversation, not the graph. They're gone next session.

**Chirp is declarative.** A Chirp component encodes the relationship `design_language → facade_parameters` as a persistent, visible, wired node on the canvas. When inputs change, it re-reasons automatically — no Claude session required. The intelligence is in the graph, not the chat.

**The unique capability:** Natural language becomes a first-class data type in the parametric graph. A text Panel with `"brutalist, exposed concrete, heavy proportions"` becomes as powerful as a Number Slider — but it controls semantic intent instead of a single value.

### The Design Language Pattern

The most compelling use case: one text Panel drives an entire model's character.

```
┌──────────────────────────────────────────┐
│ Panel: "brutalist, exposed concrete"     │
└─────────────────┬────────────────────────┘
                  │
    ┌─────────────┼──────────────┐
    │             │              │
 ★ Chirp:     ★ Chirp:      ★ Chirp:
 facade       structure     ground plane
 params       expression    treatment
    │             │              │
    ▼             ▼              ▼
 [GH facade]  [GH sizing]   [GH landscape]
```

Change the text to `"nordic minimalist, light timber, airy"` and every Chirp component re-reasons. The facade gets thinner modules, higher transparency. The structure hides connections. The landscape softens. One string drives the whole model's character.

No traditional GH component maps "brutalist" to a reveal depth. No lookup table covers every aesthetic. The LLM generalizes.

### Where Chirp Is NOT the Right Tool

Anything with a closed-form solution. Don't use an LLM to compute structural deflection — there's an equation. Don't use it to subdivide a surface into equal panels — that's just math. Chirp belongs at the **decision points** where a human designer would normally pause, think about context, and make a judgment call they'd struggle to express as a formula.

### The Reasoning Pin

Every Chirp component auto-includes a `Reasoning` output pin exposing the LLM's chain of thought. Wire it to a Panel to see:

> *"Art deco emphasizes bold geometric forms and pronounced shadow lines. Setting frame_depth=80mm for strong reveals, corner_radius=0 for sharp geometry, solid_ratio=0.85 for monumental opacity."*

This makes Chirp components a **teaching tool** — junior designers see the relationship between design language and dimensional decisions made explicit. It's also the debugging interface — when outputs seem wrong, the reasoning shows why.

---

## Wasp Integration: Discrete Design with Semantic Configuration

*Added 2026-03-13 — Safdie Architects context*

### Why Wasp

[Wasp](https://github.com/ar0551/Wasp) is a Grasshopper plugin for discrete design with modular aggregation. It enables procedural generation of complex structures from simple modular parts using shape grammar rules and constraint checking. The system is grounded in graph grammar theory (Klavins et al. 2004).

Wasp is directly relevant to Safdie Architects' design methodology — Habitat 67 is the canonical example of modular/discrete architecture. The firm's work often involves modular units aggregated into complex spatial arrangements with structural, environmental, and programmatic constraints.

### Wasp's Architecture

**Core workflow:** Define parts → Define rules → Run aggregation → Check constraints

**Key concepts:**
- **Parts:** Geometry + connections (planes) + optional constraints
- **Rules:** Directed graph grammar — `Part1|Conn1 → Part2|Conn2`
- **Aggregation:** Stochastic (random), field-driven (scalar field prioritization), or graph-grammar (explicit sequence)
- **Constraints:** Local (colliders, supports, adjacency, orientation) and global (plane bounds, mesh containment)

**Three aggregation modes:**
1. **Stochastic:** Random part selection, random rule application, constraint filtering
2. **Field-driven:** Scalar field values prioritize connections — always picks highest field value. Creates gradient-aligned growth patterns
3. **Graph-grammar:** Explicit rule sequences — fully deterministic

### The Gap Chirp Fills

Wasp's algorithm is powerful and well-designed. But every **decision upstream of the algorithm** is manual:

| Manual Decision | What the Designer Sets | What They're Thinking |
|---|---|---|
| Part proportions | `wall=0.7, opening=0.2, roof=0.1` | "Mostly closed with scattered openings" |
| Constraint mode | `mode=3` (local + global) | "I need structural validity" |
| Field direction | `vector=(0,0,1)` | "Heavy base, lighter top" |
| Field strength | `0.8` | "Strong vertical gradient" |
| Target parts | `150` | "Dense enough to read as a pavilion" |
| Rule activation | Enable/disable specific rules | "No openings next to corners" |

The designer thinks in **intent** but Wasp needs **numbers**. That translation is currently done through experience and trial-and-error.

### One Chirp Component Bridges the Gap

```
Signature: "design_intent, part_types, site_constraints
            -> wall_ratio, opening_ratio, roof_ratio,
               field_direction_x, field_direction_y, field_direction_z,
               field_strength, constraint_mode, target_parts"
```

```
┌────────────────────────────────────────────────┐
│ Panel: "dense pavilion, 3m tall, mostly closed │
│  walls with scattered openings for ventilation,│
│  heavy base, lighter top"                      │
└──────────────────────┬─────────────────────────┘
                       │
                ★ Chirp Component
                       │
     ┌─────────┬───────┼────────┬──────────┐
     │         │       │        │          │
  wall_ratio opening field_  field_    target_
    0.7      ratio  direction strength   parts
              0.2   (0,0,1)    0.8        150
     │         │       │        │          │
     ▼         ▼       ▼        ▼          ▼
   [Wasp Parts    [Wasp Field      [Wasp Stochastic
    Catalog]       Generation]      Aggregation]
```

The Reasoning pin outputs:

> *"Dense pavilion with scattered openings suggests predominantly closed structure. 70/20/10 wall/opening/roof ratio gives ~1 opening per 3.5 wall panels — 'scattered' rather than regular. Vertical field direction (0,0,1) with strength 0.8 creates strong gradient: parts placed near ground first (heavy base). Lighter top emerges naturally as field weakens upward. Constraint mode 3 (local + global) ensures structural supports are checked."*

### Why This Is Different From the Facade Pattern

With the facade, Chirp maps aesthetics to proportions — subjective but relatively low-stakes. With Wasp, Chirp is mapping **design intent to algorithmic behavior**. The LLM isn't just picking numbers — it's reasoning about how those numbers will affect a generative process:

- "Heavy base, light top" → vertical field gradient (the LLM understands how field-driven aggregation works conceptually)
- "Scattered openings" → 20% ratio, not 50% (the LLM understands what "scattered" means in terms of density)
- "Dense pavilion" → 150 parts, not 30 (the LLM reasons about what density means for a given scale)

### Future: Rule Activation

A second Chirp component could take the same design intent and output which **rule categories** to activate or deactivate. "Load-bearing wall: don't allow openings adjacent to corners" → the LLM translates structural intuition into rule state changes. This encodes the kind of design knowledge that's currently in the architect's head, not in the algorithm.

### The Safdie Connection

This isn't theoretical. Safdie's work is built on modular aggregation — units arranged according to structural, environmental, and spatial logic. The decisions about how modules aggregate (density gradients, opening distribution, structural continuity) are exactly the kind of context-dependent judgment calls that:
1. Can't be reduced to a formula (each project is different)
2. Require expertise to get right (structural, environmental, programmatic knowledge)
3. Are currently done by manual parameter tuning in tools like Wasp
4. Are exactly what LLMs are good at — synthesizing domain knowledge into specific parameter recommendations

Chirp makes that expertise available as a reactive node in the parametric graph.
