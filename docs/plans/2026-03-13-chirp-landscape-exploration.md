# Chirp — Landscape Exploration

**Date:** 2026-03-13
**Status:** Active exploration
**Authors:** Aryan + Claude

---

## Context

Chirp started as a spec-driven code generation pipeline for Grasshopper components, inspired by CodeSpeak. The original brief described a YAML-to-C# compiler with a retry loop — "let AI write the code."

Then we looked at Rook. And then we built something different: components with live LLM reasoning at solve time, where the intelligence isn't in the generated code but in the runtime call. Chirp became "let AI **be** the code." The CodeSpeak insight wasn't wrong — it pointed toward a deeper version of itself. If components can reason at runtime, you don't need a clever compiler. You need a thin shell and a live brain.

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

---

## The Reasoning Pin as Shared Context Bus

*Added 2026-03-13 — emerged from design discussion about wiring Reasoning outputs*

### Chain-of-Thought as a Wireable Signal

The Reasoning pin started as a transparency feature — "see why the LLM chose those values." But in Grasshopper, every output is wireable. The moment you connect a Reasoning pin to another Chirp component's input, something qualitatively different happens: **the downstream LLM doesn't just get numbers, it gets the rationale that produced them.**

### One Reasoning, Many Interpreters

When a Reasoning output fans out to multiple downstream Chirp components, each reads the same rationale but interprets it through its own domain:

```
"dense pavilion, heavy base, scattered openings"
         │
    ★ Chirp: Aggregation Config
         │
         ├── wall_ratio=0.7 ──→ [Wasp Catalog]
         ├── field_strength=0.8 ──→ [Wasp Field]
         │
         └── Reasoning: "heavy base → vertical gradient,
                         scattered → 20% ratio, dense →
                         150 parts for pavilion scale"
                    │
          ┌─────────┼──────────┬──────────────┐
          │         │          │              │
          ▼         ▼          ▼              ▼
     ★ Structure  ★ MEP    ★ Envelope    ★ Critic

     "heavy base    "dense    "heavy base   "aggregation
      means more     lower     means less    targets 20%
      load at        floors    glazing at    openings but
      base →         need      base, more    clustering
      deeper         more      at top →      detected on
      beams          HVAC      thermal       south face →
      below"         capacity" gradient      suggest
                               follows       exclusion
                               massing"      constraint"
```

Each downstream component extracts different implications from the same source rationale. The structural component cares about load distribution. MEP cares about density and occupancy. Envelope cares about transparency gradients. The critic evaluates whether the aggregation achieved its stated intent.

### This Is How Design Teams Actually Work

The architect says "heavy base, light top" in a meeting. The structural engineer hears "more load at the base." The facade consultant hears "less glazing at the base." The mechanical engineer hears "denser occupancy below." Same intent, domain-specific interpretations, coherent outcome.

Chirp makes that coordination pattern **explicit and persistent in the graph** instead of implicit in a meeting that everyone remembers differently.

### Two Parallel Data Streams

Traditional GH carries one kind of signal: data (numbers, geometry, text as literal values). With Chirp's Reasoning pin, the graph carries two:

| Stream | What flows | What it does |
|--------|-----------|--------------|
| **Data** (numbers, geometry) | `wall_ratio=0.7`, `field_strength=0.8` | Drives geometry and algorithm parameters |
| **Reasoning** (semantic context) | "heavy base because...", "scattered means..." | Drives coherence between independent decisions |

When a number fans out to multiple components, each gets the same value and uses it mechanically. When reasoning fans out, each component gets the same rationale but **interprets** it contextually. The LLM in each downstream node acts like a different discipline expert reading the same design brief.

### Spatial Chain-of-Thought

In DSPy, `ChainOfThought` is linear — reasoning flows forward through `forward()`. In LangGraph, it flows through code-defined edges. In Chirp on the GH canvas, **the designer decides which reasoning flows where by dragging wires:**

```
DSPy:     A.reasoning → B.reasoning → C.reasoning         (linear)

Chirp/GH: A.Reasoning ──→ B (structural)
              │
              └──────────→ C (environmental)
              │
              └──────────→ D (critic)                      (graph)
```

The reasoning topology is a design decision in itself — visible and manipulable on the canvas. Route facade reasoning to the structural component but NOT to the landscape. Merge reasoning from two upstream components into a single downstream critic. The reasoning architecture becomes a design artifact alongside the geometry.

This is genuinely novel. Nobody is doing spatial chain-of-thought composition in a visual dataflow graph where a non-programmer can rewire the reasoning flow by dragging connections.

### Implications

- **The Reasoning pin is not optional debugging output.** It's a shared context bus — the mechanism by which design coherence propagates across disciplines in a parametric model.
- **Coordination without a coordinator.** The graph topology enforces that all downstream components work from the same intent. No meeting notes, no "did everyone get the memo."
- **The graph has two layers.** One layer is the computation graph (numbers → geometry). The other is the reasoning graph (intent → coherence). They share the same canvas but do fundamentally different work.

---

## Reasoning Branching: What It Actually Means

*Added 2026-03-14 — emerged from first working reasoning cascade demo*

### The Problem With Numbers

In traditional parametric design, you wire numbers. A spacing of `4.0` flows from one component to the next. But `4.0` is context-free — the downstream component doesn't know if it's 4.0 because of structural efficiency, aesthetic rhythm, site constraints, or cost. It just gets `4.0`.

With Chirp, you wire **intent alongside value**. The Planner doesn't just output `ColumnSpacing = 3.6`. It outputs *why* — "timber beams work well at 3.6m, and 3 bays creates a 10.8m garden feature." When the Structure component receives that reasoning, it doesn't just size a beam for a 3.6m span. It sizes a beam for a *timber pergola carrying mature wisteria in a garden*. That's why it chose 240mm instead of the 200mm it chose for the steel walkway — same span range, completely different sizing rationale.

### First Demo: What We Observed

Three-component fan-out cascade (Planner → Structure + Envelope), tested with two briefs:

| Brief | Structure Output | Envelope Output |
|-------|-----------------|-----------------|
| "covered walkway, steel, polycarbonate roof" | IPE 200 beams, 3m spacing, M16 bolts | 16mm polycarbonate, 1200mm module, 15% open |
| "timber pergola, garden setting, wisteria coverage" | 240×120mm glulam, 3.6m spacing, stainless lag screws | Cedar 140×45 battens, 200mm spacing, 65% open |

The same graph produced fundamentally different design systems from a single text change. Not because the numbers were recalculated — because the *reasoning* about what those numbers should be was re-derived from shifted intent.

### Branching Is Parallel Interpretation

When a Reasoning wire fans out to multiple components, you get something that mirrors how design teams actually work:

1. The architect describes a vision
2. The structural engineer interprets it through *their* lens
3. The facade consultant interprets the *same* vision through a *different* lens
4. Both produce domain-appropriate responses that are coherent with each other — not because they coordinated, but because they share the same design intent

No single component "knows" the whole design. But coherence emerges from shared context. This is distributed cognition — the same pattern that makes real multi-disciplinary design work.

### What This Unlocks

**1. One word changes everything.** Swap "timber" for "steel" in the brief and every component re-reasons from scratch. You don't retune 50 sliders — the LLMs re-derive appropriate values from the shifted intent. The parametric model becomes *semantically* parametric.

**2. Critic nodes.** A downstream Chirp component that receives ALL reasoning outputs from the cascade and checks for contradictions — "Structure assumes lightweight cladding but Envelope specified heavy stone panels." Automated cross-discipline conflict detection, live in the graph.

**3. Multi-scale cascades.** Urban massing → building form → structural system → detail design. Each level's reasoning feeds the next. The detail designer knows it's working on a *civic plaza canopy in a seismic zone*, not just "a 12m cantilever."

**4. Regulatory checking.** A Chirp component that reads the design reasoning and cross-references against code requirements — not just checking numbers, but understanding *what the design is trying to do* and whether that intent is code-compliant.

**5. Design narrative generation.** A terminal node that reads all reasoning wires and produces a coherent design statement — the kind you'd put in a competition submission. Generated live as the model evolves.

### How This Differs From Prompt Chaining

This is **not** LangChain or LangGraph with a visual skin. The distinction matters:

| Prompt chaining (LangChain etc.) | Chirp on GH canvas |
|---|---|
| LLM output is the ONLY data flowing | Reasoning coexists with numbers, geometry, booleans |
| Chain topology defined in code | Topology defined by dragging wires — non-programmers can rewire reasoning flow |
| LLM-only pipeline | Hybrid: LLM nodes interleave with deterministic GH components (Multiply, Offset, Boolean) |
| Ephemeral — runs once, produces result | Persistent — the graph lives across sessions, sliders re-trigger reasoning |
| No spatial exploration | Sliders = instant re-reasoning over the parameter space |

The critical difference: **the LLM is embedded inside the parametric graph alongside deterministic components.** Reasoning coexists with Booleans, Panels, sliders, Breps. You can branch reasoning to an LLM node AND branch a number to a standard `Multiply` component in the same graph. Semantic and parametric in one canvas.

### The Deeper Principle

Traditional Grasshopper has one data layer: geometry and numbers. Chirp adds a second: **natural language carrying design intent**. These two layers flow through the same graph but serve different purposes:

- **Numbers** drive geometry
- **Reasoning** drives coherence

The graph becomes a **thinking graph**, not just a computing graph. It doesn't just calculate what the design IS — it carries the reasoning about WHY the design is what it is, and that reasoning propagates, branches, and compounds as it flows through the canvas.

This is the thing Chirp provides that Rook cannot: Rook sees the graph from outside and manipulates it. Chirp puts intelligence *inside* the graph nodes, making reasoning a first-class wireable signal that the designer can route, branch, merge, and inspect — just like any other data type in Grasshopper.

---

## What's Inside a Chirp Component (And What Isn't)

*Added 2026-03-15 — central architectural principle*

A Chirp component is **domain-agnostic by design.** The component knows the *shape* of an answer, never the *domain* of the question. This is the most important thing to understand about the architecture, and the thing that makes it powerful.

### The Three Layers

When a Chirp component solves, three distinct layers contribute to the result. Only one is visible to the user. None of them contain the design problem.

**Layer 1: Embedded in the C# script (invisible on canvas)**

These are baked into the component at creation time and never change:

| What | Example | Purpose |
|------|---------|---------|
| DSPy signature | `brief -> span_m, bay_count, material` | Defines the typed contract — what goes in, what comes out |
| Category string | `"planner"` | Selects the reasoning strategy (ChainOfThought vs Predict) |
| Output schema | `{"span_m": "float", "bay_count": "int", "material": "string"}` | Type coercion for LLM outputs |
| Adapter URL | `localhost:9900/chirp/call` | Where to send the request |

Note what's absent: no mention of pergolas, bridges, facades, or any specific design domain. The signature says "given a brief, produce a span, a bay count, and a material." It doesn't say what *kind* of span or *what* material.

**Layer 2: Injected by the adapter at call time (invisible everywhere)**

The Chirp adapter adds context that the component doesn't carry:

| What | Example | Purpose |
|------|---------|---------|
| Category prompt | *"You are a design planner. Given a brief, determine appropriate parameters."* | Primes the LLM for the reasoning approach |
| Correction text | *"HUMAN CORRECTION (takes priority): use steel, not timber"* | Per-node human override, only when non-empty |

These are also domain-agnostic. "Design planner" works for bridges, pergolas, furniture, or urban infrastructure. The prompt doesn't name a domain.

**Layer 3: User input at runtime (visible on canvas)**

This is where the domain lives — and it's entirely in the user's hands:

| What | Example | Purpose |
|------|---------|---------|
| Brief text (Panel → pin) | *"timber pergola, garden setting, wisteria coverage"* | The actual design problem — the ONLY place the domain exists |
| Correction text (Panel → pin) | *"actually use cedar, not pine"* | Human steering of a specific node |

### Why This Matters

**The same component handles any domain.** A planner with `brief -> span_m, bay_count, material` produces reasonable outputs whether the brief says "timber pergola for a courtyard garden" or "steel pedestrian bridge over a canal." The LLM re-derives appropriate values from scratch because it has world knowledge about both. You don't retune the component — you change the text.

**Components are reusable across projects.** A "Structure Planner" made for a pergola study works unchanged for a bridge study. The signature defines the output contract (I need a span, a bay count, and a material), not the input domain (this is about pergolas). This is why a firm could build a library of Chirp components — they're typed contracts, not domain-specific calculators.

**The design problem is always visible.** Because domain context lives in Panels connected to input pins, the user can always see (and change) what's driving the reasoning. Nothing is hidden in a prompt template or buried in code. The entire design intent is on the canvas, in plain text, editable by the human.

**This is the inverse of traditional AI tools.** Most AI-for-design tools embed domain knowledge in the tool (a "pergola designer" that only does pergolas). Chirp embeds *reasoning structure* in the tool and lets the domain flow through as data. The component is a lens, not a calculator — it shapes how the LLM thinks about the problem, not what problem it thinks about.

### The Analogy

A Chirp component is like a meeting template. A "design review" template says: "present the concept, list the concerns, propose next steps." It doesn't say what the concept IS — that comes from whoever fills it in. The template structures the conversation. The participants bring the content.

Similarly, a planner component says: "given a brief, determine span, bay count, and material." It structures the LLM's reasoning. The user brings the design problem.

---

## Component Categories

*Added 2026-03-14 — toward a shared vocabulary for Chirp components*

### The Problem With Freeform Creation

`chirp_create` is currently fully freeform — any pins, any signature, any purpose. That's flexible but it means Claude reinvents the wheel every time, and there's no consistency between sessions or users. If we define **component categories**, we get a shared vocabulary: the user says "add a critic" and Claude knows exactly what pin pattern, signature shape, and wiring behavior that implies.

Categories are to Chirp what component palettes are to Grasshopper — not constraints, but conventions that make composition predictable.

### The Six Categories

#### 1. Planner

The entry point. Translates a design brief into structured parameters.

| | |
|---|---|
| **Inputs** | `Brief` (string), optional context inputs (site area, program, constraints) |
| **Outputs** | Typed parameters (numbers, strings, enums) + `Reasoning` |
| **Role** | First node in a cascade. Converts intent to values. |
| **Example** | "timber pergola, garden setting" → `Span=3.6`, `Height=3.0`, `BayCount=3`, `Material="glulam"` |

#### 2. Interpreter

Reads upstream Reasoning through a discipline-specific lens.

| | |
|---|---|
| **Inputs** | `Reasoning` (string) + domain context inputs |
| **Outputs** | Domain-specific parameters + `Reasoning` |
| **Role** | Fan-out target. Each Interpreter reads the same Reasoning but produces discipline-appropriate outputs. |
| **Examples** | Structure Interpreter, Envelope Interpreter, MEP Interpreter, Landscape Interpreter |

#### 3. Critic

Cross-checks multiple reasoning streams for contradictions.

| | |
|---|---|
| **Inputs** | 2+ `Reasoning` inputs (from Planners/Interpreters) |
| **Outputs** | `Conflicts` (string), `Score` (float), `Coherent` (bool) + `Reasoning` |
| **Role** | Terminal or mid-graph validator. Catches when disciplines diverge. |
| **Example** | "Structure assumes lightweight cladding but Envelope specified heavy stone panels" |

#### 4. Narrator

Produces human-readable design statements from reasoning streams.

| | |
|---|---|
| **Inputs** | 2+ `Reasoning` inputs |
| **Outputs** | `Narrative` (string), `Summary` (string) + `Reasoning` |
| **Role** | Terminal node. Generates presentation-ready text — competition briefs, client reports. |
| **Example** | Reads Planner + Structure + Envelope reasoning → coherent design statement |

#### 5. Classifier

Makes categorical decisions from data.

| | |
|---|---|
| **Inputs** | Geometry/data + optional `Intent` (string) |
| **Outputs** | `Category` (string), `Confidence` (float) + `Reasoning` |
| **Role** | Standalone. Routes data based on LLM judgment, not geometric computation. |
| **Example** | Surface → "flat / single-curve / double-curve / freeform" with confidence score |

#### 6. Gate

Translates design intent into algorithmic rule activations.

| | |
|---|---|
| **Inputs** | `Reasoning` (string) |
| **Outputs** | Boolean/enum flags + `Reasoning` |
| **Role** | Bridges reasoning to deterministic rule engines (e.g., Wasp constraint toggles). |
| **Example** | "load-bearing wall" → `AllowCornerOpenings=false`, `RequireLintel=true` |

### How Categories Change the Workflow

**Without categories** (current):
```
User: "Build me something that takes a brief and figures out structure"
Claude: (improvises pins, signature, wiring from scratch every time)
```

**With categories:**
```
User: "Add a structural interpreter"
Claude: knows the pattern — Reasoning input + domain context,
        domain-specific parameter outputs, signature template.
        Creates it in one chirp_create call with consistent naming.

User: "Add a critic watching structure and envelope"
Claude: knows the pattern — 2 Reasoning inputs, conflict/score/coherent
        outputs. Wires both upstream Reasoning pins automatically.
```

Categories become the vocabulary layer between the user and Claude. No skill needed for each specific cascade — Claude knows the building blocks and composes them on request.

### Implementation Path

Two layers, both lightweight:

**1. `chirp_create` gets a `category` parameter** — selects a pin template and signature pattern. `chirp_create(category="interpreter", domain="structural", ...)` gives you the right pins and signature shape in one call. The freeform mode remains available for one-offs.

**2. The Chirp adapter gets category-aware prompting** — each category can have a tuned system prompt or DSPy module that shapes LLM behavior for that role. A Critic gets a prompt that emphasizes contradiction detection. A Narrator gets one that emphasizes prose quality. The LLM isn't just receiving different inputs — it's operating in a different mode.

### Composition Patterns

Categories imply natural wiring patterns:

```
Planner ──→ Interpreter (1:N fan-out, the core cascade)
Interpreter ──→ Critic (N:1 fan-in, cross-discipline check)
Planner ──→ Gate (1:1, intent to rule state)
Interpreter ──→ Narrator (N:1, design statement generation)
Classifier ──→ Planner (1:1, classify first, then plan from category)
Critic ──→ Planner (1:1 feedback loop — critic flags issues, planner revises)
```

These aren't enforced — any output can wire to any input. But knowing the natural patterns lets Claude suggest wiring and lets the user think in terms of design process rather than pin names.

---

## Human-in-the-Loop: Steering the Reasoning Chain

*Added 2026-03-14 — the mechanism that keeps the human in control*

### The Problem

Without human intervention points, a reasoning cascade is fire-and-forget. The designer sets a brief, the chain runs, and the outputs are whatever the LLMs decided. If the Planner's reasoning drifts — "timber" when the budget demands steel — every downstream component inherits that drift. The designer only discovers the problem at the end, in the geometry.

The chain needs steering points where the human can read the reasoning, correct it, and watch the correction propagate — **before** it reaches geometry.

### Two Mechanisms, Both Active

#### 1. The Correction Pin (Universal)

Every Chirp component gets an optional `Correction` input pin. When connected (typically to a Panel), the LLM treats the human's text as a priority override that modifies its reasoning. When empty or disconnected, the component behaves exactly as it does today — no overhead, no change.

```
Planner ──Reasoning──→ Structure Interpreter ──→ ...
                              ↑
                         Panel: "Use steel, not timber.
                          Budget constraint."
```

The Interpreter reads the upstream reasoning ("timber pergola, 3.6m spans...") AND the correction ("use steel, budget constraint") and reconciles them. Its output reasoning reflects the override: "Overriding upstream timber recommendation per budget constraint. Steel IPE 200 at 3m spacing..."

**When to use:** Lightweight nudges on specific components. The designer spots one wrong assumption and corrects it without restructuring the graph.

**Implementation:** `chirp_create` auto-adds a `Correction` pin (type: string, optional) to every component, same as it auto-adds `Reasoning` to outputs. The adapter prepends correction text to the LLM prompt when the input is non-empty.

**Critical: corrections are per-node, not global.** This is a fundamental design property. Changing the upstream Panel (the design brief) re-triggers the entire cascade — every downstream node re-reasons. But the Correction pin targets a single node. If you correct the Structure Interpreter to use steel, the Envelope Interpreter still works from the original upstream reasoning. You're steering one discipline without disturbing the others — exactly how design review works in practice.

**Three states of the Correction pin:**

| State | Behavior |
|---|---|
| **Disconnected** (no Panel wired) | Component reasons normally. The pin exists but is inert. Zero overhead. |
| **Connected, Panel empty** | Same as disconnected — empty string treated as no correction. |
| **Connected, Panel has text** | Adapter includes both upstream reasoning AND the correction in the LLM prompt. The LLM reconciles them, prioritizing the correction. Output Reasoning explains the reconciliation. |

**What "reconciliation" means:** The LLM doesn't blindly apply the correction text. It *reasons about* the relationship between the upstream context and the human's override. If the Planner said "timber at 3.6m spacing" and the correction says "use steel," the Structure Interpreter doesn't just swap the word — it re-derives: "steel allows longer spans → spacing increases to 6m, beam depth decreases to 180mm, connection type changes to bolted." The Reasoning output shows this chain of consequence so the designer can verify it propagated correctly.

**Corrections as persistent design decisions:** The Panel stays on canvas as a visible record. When the designer returns to the definition after weeks, the Correction Panels show exactly where they intervened and why. This is not debugging scaffolding — it's the design narrative embedded in the graph.

**The practical workflow:**
1. Run the cascade. Read all the Reasoning outputs.
2. Structure looks wrong — it assumed lightweight cladding.
3. Drop a Panel, connect it to Structure's Correction pin.
4. Type: "Heavy stone cladding, 80kg/m². Size for this."
5. Structure re-solves. New Reasoning explains the heavier load. New BeamDepth reflects it.
6. Envelope Interpreter is untouched — it already assumed stone.
7. Check the Critic. If it flagged a conflict before, does it resolve now?

#### 2. The Editor Node (7th Category)

A dedicated review checkpoint. Takes upstream `Reasoning` as input, displays it for human review, accepts a `Correction` (Panel), and produces reconciled `Reasoning` as output. The Editor's own Reasoning output shows *how* it reconciled the original with the correction, so the designer can verify before propagation continues.

| | |
|---|---|
| **Inputs** | `Reasoning` (string) + `Correction` (string, from Panel) |
| **Outputs** | `Reasoning` (string — reconciled output) |
| **Role** | Explicit review checkpoint. Makes human steering visible on the canvas. |

```
Planner ──Reasoning──→ [Editor] ──Reasoning──→ Structure Interpreter
                          ↑                          │
                     Panel: "Steel, not         Interpreter output
                      timber. Also add            is also visible
                      seismic bracing."           before it feeds
                                                  downstream.
```

**When to use:** Critical decision points where the designer wants to review and approve reasoning before it fans out to multiple downstream components. Place an Editor between the Planner and the fan-out, and every discipline inherits the corrected intent.

**The key difference from the Correction pin:** The Editor is *visible on the canvas as a node*. Anyone looking at the graph can see exactly where human steering happened and what was changed. The Correction pin is invisible unless you click on the component. For auditable design processes — competition submissions, regulatory reviews — the Editor creates a legible record of human judgment in the graph.

### Both Together

The two mechanisms complement each other:

```
                    ┌──────────────────────────────┐
                    │ EDITOR (visible checkpoint)  │
Brief ──→ Planner ──→ [Editor] ──→ Structure Interpreter ──→ ...
              │          ↑               ↑
              │     Panel: "Steel,   Panel: "Add
              │      not timber"      seismic bracing"
              │                    (Correction pin — quick nudge)
              │
              └──→ Envelope Interpreter ──→ ...
```

- The **Editor** steers the reasoning at the trunk — before it fans out. Every downstream branch inherits the corrected intent.
- The **Correction pin** steers individual branches — the Structure Interpreter gets an additional nudge about seismic bracing that the Envelope Interpreter doesn't need.

### Why This Matters

This is what separates Chirp from autonomous AI pipelines. The designer isn't just a prompt writer who fires and waits. They're an active participant who can intervene at any depth of the reasoning chain, with corrections that are:

- **Visible** — Editor nodes mark where human judgment happened
- **Contextual** — corrections flow through the same reasoning channel as LLM output
- **Propagating** — a correction at the trunk affects every downstream branch
- **Optional** — empty Correction pin = no change, remove the Editor = direct wire

The reasoning chain is collaborative, not autonomous. The human and the LLMs trade control at every junction the designer chooses to monitor.

---

## Enforcement Architecture: Making Claude Follow the Rules

*Added 2026-03-15 — ensuring consistency across sessions*

### The Problem

Claude Code forgets. YAML files it "should" read, knowledge store entries it "should" query, conventions it "should" follow — all unreliable without structural enforcement. Categories, pin patterns, and prompt strategies defined in documentation will be ignored in practice unless the system forces compliance.

### The Enforcement Stack

Four layers, each catching what the one above might miss:

| Layer | Mechanism | What it enforces | Reliability |
|---|---|---|---|
| **Tool** (`chirp_create`) | Required `category` param, server-side validation | Can't create without a valid category. Tool handles pin templates, colors, DSPy module. | Mechanical — impossible to bypass |
| **Skill** (`/chirp`, `/chirp-cascade`) | Structured workflow with `<HARD-GATE>` | Step-by-step process: preflight → category → design → create → verify | High — enforced by skill text |
| **SessionStart hook** | Context injection at session start | Claude always knows categories exist, knows to use `/chirp` skill | Medium — awareness, not enforcement |
| **PreToolUse hook** (optional) | Validates `chirp_create` calls | Additional guardrails (e.g., Interpreter must have Reasoning input) | Mechanical — blocks invalid calls |

### Layer 1: The Tool (Foundation)

`chirp_create` requires a `category` parameter. Without it, the tool returns an error. The tool internally:
- Applies the category's pin template (universal pins auto-added)
- Selects the DSPy module (ChainOfThought, Predict, MultiChainComparison)
- Sets the prompt strategy for the adapter
- Assigns visual treatment (color, icon, Message label)

Claude only provides: **category, domain, and domain-specific pins**. Everything else is determined by the category definition inside the tool.

### Layer 2: The Skills

**`/chirp`** — Single component creation:
1. Preflight (Rhino, adapter, GH)
2. Determine category from user's description
3. Design domain-specific pins and signature
4. Create via `chirp_create` with category
5. Verify output

**`/chirp-cascade`** — Multi-component workflows:
1. Preflight
2. Decompose brief into disciplines
3. Design cascade topology
4. Build in dependency order, each component via the category system
5. Wire Reasoning pins, test coherence

The skills contain `<HARD-GATE>` directives preventing creation before design approval.

### Layer 3: SessionStart Hook

Injects category awareness into every Rook session:

```
"Chirp component categories are available: planner, interpreter, critic,
 narrator, classifier, gate, editor. When creating Chirp components,
 use the /chirp skill for single components or /chirp-cascade for
 multi-component workflows."
```

This ensures Claude knows the system exists even in conversations that don't start with a Chirp request.

### Layer 4: PreToolUse Hook (Optional)

A hookify rule that validates `chirp_create` calls before they execute:
- Category is one of the 7 valid values
- Reserved pin names aren't used for domain pins
- Interpreter/Critic categories have Reasoning inputs

This is belt-and-suspenders — the tool already validates, but the hook catches edge cases.

### Why Not Just Documentation?

The brainstorming skill (superpowers plugin) demonstrates the pattern: it uses a `<HARD-GATE>` in the skill text to prevent premature implementation. This works *most* of the time, but Claude can and does ignore it. The mechanical layers (tool validation, hooks) make compliance involuntary.

For Chirp, the categories aren't suggestions — they're the architecture. A component without a category has no color, no icon, no message label, no appropriate DSPy module. The tool should refuse to create it, not just hope Claude remembers.

### Categories Are Claude's Vocabulary, Not the User's

The user never needs to say "create an Interpreter." They say "I need to think about drainage for this pergola." Claude recognizes this as an Interpreter-shaped problem and selects the category internally.

The categories are invisible scaffolding — they give Claude consistency and predictability without the user learning a taxonomy. The user learns ONE gesture: describe the design problem. The skill determines the category. The tool enforces the template.

Over time, designers naturally pick up the vocabulary from seeing labeled components on canvas ("Planner: Pergola Spacing", "Interpreter: Drainage"). The labels become a shared language through use, not study — like layer colors in Rhino.

---

## Connecting Chirp to External Knowledge: The RAG Bridge

*Added 2026-03-15 — linking reasoning components to project databases*

### The Knowledge Gap

A Chirp component's LLM currently has exactly two sources of knowledge:

1. **World knowledge** — what the LLM already knows about timber, steel, structural spans, building codes, design precedent. Broad but generic.
2. **Pin data** — whatever text flows in through Brief, Reasoning, Correction. Specific but limited to what the user types or what upstream components produce.

This is powerful for general design reasoning, but it's *generic*. The LLM doesn't know:
- The firm's past projects — what worked, what failed, what it cost, how long it took
- The firm's material library, preferred suppliers, and standard details
- Relevant code requirements for the specific jurisdiction and building type
- Photos and drawings of precedent work (the firm's own or reference projects)
- Specification sections, product data sheets, manufacturer constraints

A Structure Planner that says "timber pergola" can reason about timber in general. But it can't say "the last three timber pergolas we built used 240×120 glulam at 3.6m spacing and the client was happy" — because that knowledge lives in project archives, not in the LLM's training data.

### Multimodal RAG: Same Vector Space, All Media Types

Google's Gemini Embeddings 2 (and similar models) embed text, images, video, audio, and documents into the **same vector space**. A single model understands cross-modal relationships natively:

- A text query ("timber pergola detail") retrieves relevant drawings, photos, AND text descriptions
- An uploaded photo retrieves similar past projects with metadata (cost, timeline, team size)
- A specification section retrieves related detail drawings and construction photos

For architecture firms, this is transformative. Project knowledge isn't just text — it's drawings, photos, models, specs, cost sheets. A multimodal embedding model treats all of these as queryable knowledge in one index.

The retrieval architecture:

```
Query (text from Chirp pin, or image, or drawing)
    ↓
Embedding Model (Gemini Embeddings 2 — single model, all modalities)
    ↓
Vector Database (Pinecone — stores embeddings + metadata per record)
    ↓
Similarity Search (find nearest neighbors in vector space)
    ↓
Retrieved Context (text descriptions, image references, metadata)
    ↓
Passed to LLM alongside the original query
```

### Where RAG Fits in the Chirp Architecture

Given the principle documented above — *the design problem should always be visible on the canvas* — the RAG layer should be **an explicit component on the canvas**, not hidden inside the adapter. Three options evaluated:

**Option A: RAG inside the adapter** — The Chirp adapter does retrieval before calling the LLM, injecting retrieved context alongside the category prompt. Invisible to the user. *Rejected: violates the visibility principle. The user can't see what knowledge is informing the reasoning.*

**Option B: RAG as a Chirp component (a new category: `retriever`)** — A visible node on the canvas that takes a query, searches the vector DB, and outputs enriched context as text. The user wires it into downstream components. *Preferred: keeps knowledge sourcing visible, editable, disconnectable.*

**Option C: RAG at the server level** — Middleware that enriches every call. *Rejected: too invisible, too automatic, too hard to debug when retrieval quality is poor.*

### Option B: The Retriever Component

A retriever is a new Chirp category — but unlike planners and interpreters, it doesn't reason. It *retrieves*. Its job is to translate a query into relevant context from an external knowledge base.

```
[Panel: "timber pergola"]  →  [Retriever: "Firm Projects"]  →  [Structure Planner]
                                    ↓                              ↓
                              Context (text)                  SpanM, BayCount, Material
                              Sources (string)                Reasoning
```

The retriever queries the vector DB with the brief text, retrieves the top-k matching records (past projects, details, specs), formats them as structured context text, and passes that as an input pin to downstream components. The planner now reasons with *firm-specific knowledge*, not just generic LLM world knowledge.

What the planner's LLM sees (conceptually):

```
Brief: "timber pergola, garden setting, wisteria coverage"

Context from firm knowledge base:
- Project #2019-047 (Hillside Residence Pergola): 240×120 glulam, 3.6m bays,
  cedar battens at 200mm, total cost $45k, client rated 9/10
- Project #2021-112 (Courtyard Canopy): 190×90 LVL, 2.8m bays, needed
  reinforcement after 2 years due to vine load — lesson: oversize for
  climbing plants
- Detail Standard DS-T-04: Stainless steel connectors required for all
  exterior timber, minimum 316 grade in coastal zones

→ Determine: span_m, bay_count, material
```

The planner can now say "use 240×120 glulam at 3.6m spacing — this matches our successful Hillside project and accounts for vine loading (lesson from Courtyard Canopy: oversize for climbing plants)." That's reasoning grounded in the firm's actual experience, not just LLM world knowledge.

### What Gets Embedded (For an Architecture Firm)

| Source | Modality | What It Provides |
|--------|----------|-----------------|
| Project sheets / post-mortems | Text | Costs, timelines, lessons learned, client feedback |
| Detail drawings (DWG/PDF) | Image | Standard assemblies, connection types, material configurations |
| Construction photos | Image | As-built conditions, installation sequences, failure modes |
| Specifications (PDF sections) | Text + diagrams | Material properties, performance requirements, code references |
| Product data sheets | Text + images | Manufacturer constraints, available sizes, lead times |
| Site photos | Image | Context, climate, existing conditions |
| Rhino/GH screenshots | Image | Design precedent from past parametric studies |

The multimodal embedding places all of these in the same vector space. A text query retrieves across all modalities. A photo query finds similar photos AND related text specs.

### Metadata Is the Multiplier

The embedding captures *semantic meaning*, but metadata makes retrieval actionable. Each record in the vector DB should carry structured metadata:

- **Project ID, name, year** — for traceability
- **Building type** — residential, commercial, institutional, infrastructure
- **Material system** — timber, steel, concrete, hybrid
- **Climate zone** — drives material selection and detailing
- **Cost per unit** — enables instant cost estimation from precedent
- **Lessons learned tag** — flags records that contain failure/correction knowledge
- **Confidence/quality score** — how reliable is this precedent

When the retriever queries, it can filter by metadata before similarity search: "show me timber projects in coastal climates" narrows the search space before the embedding model finds semantic matches.

### The Ingestion Question

Who populates and maintains the vector database is a separate workflow from Chirp:

- **Initial bulk ingestion**: A script/tool processes a firm's project archive — PDFs, photos, specs — into embeddings with metadata. This is a one-time setup effort.
- **Ongoing maintenance**: New projects get ingested as they complete. Post-mortems and lessons learned get added to existing project records (upsert, not insert).
- **Quality depends on descriptions**: The embedding model needs good text descriptions alongside media. "Photo of roof" retrieves worse than "Standing seam zinc roof, 25-degree pitch, parapet detail at north edge, showing expansion joint at 12m intervals." Subject matter expertise in crafting descriptions matters more than technical configuration.

This is NOT a Chirp responsibility — it's a firm-level knowledge management workflow. Chirp consumes the database through the retriever component. The database exists independently.

### The Technical Mechanism: How the Pieces Connect

Three services participate in a RAG query. Each does exactly one thing:

| Service | Role | What It Does | What It Doesn't Do |
|---------|------|-------------|-------------------|
| **Embedding model** (Gemini Embeddings 2) | Translator | Converts content (text, image, PDF) into a numerical vector — a point in semantic space | Doesn't store, doesn't search, doesn't reason |
| **Vector database** (Pinecone) | Warehouse + search | Stores vectors with metadata; finds nearest neighbors on query | Doesn't create vectors, doesn't understand content |
| **LLM** (Claude, etc.) | Reasoner | Generates a response using retrieved text as context | Never touches vectors; only sees the retrieved text descriptions |

**At ingestion time** (populating the database — a one-time or periodic workflow):

```
Source data (PDF page, photo, spec section, drawing)
    ↓
Embedding model: converts content → vector [0.23, -0.87, 0.41, ...]
    ↓
Vector database: stores vector + metadata + human-written text description
    (upsert to avoid duplicates on re-ingestion)
```

**At query time** (when a retriever component solves in GH):

```
Query text from GH pin: "timber pergola, garden setting"
    ↓
Embedding model: converts query → vector in same space as stored content
    ↓
Vector database: "which stored vectors are nearest?" → returns top-k matches
    ↓
Retrieved records: text descriptions + metadata + similarity scores
    ↓
Returned to GH as structured context text (via retriever output pin)
    ↓
Downstream Chirp planner/interpreter uses retrieved context alongside Brief
```

The critical insight: **the embedding model and the reasoning LLM are separate services with separate roles.** The embedding model creates the map; the vector DB navigates it; the LLM reads what was found. The retriever component orchestrates steps 1-4. The downstream Chirp component handles step 5.

### Decided: Mechanism A — Retrieval Through the Chirp Server

*Decision: 2026-03-15*

The retriever component's C# script calls a new `/chirp/retrieve` endpoint on the existing Chirp FastAPI server. The Chirp server handles embedding and vector DB calls in Python, where the SDKs are strongest. The C# script stays thin — same HTTP + JSON pattern as every other Chirp component.

```
GH Canvas (solve time)
    ↓
Retriever component (C# script)
    → HTTP POST localhost:9900/chirp/retrieve
      { "query": "timber pergola, garden setting",
        "top_k": 5,
        "filters": { "material_system": "timber" } }
    ↓
Chirp Server (Python — new /chirp/retrieve endpoint)
    ├── Embed query via Gemini Embeddings 2 API
    ├── Search Pinecone/Chroma for top-k matches (with metadata filters)
    ├── Format results as structured context text
    └── Return { "context": "...", "sources": [...], "scores": [...] }
    ↓
Retriever output pins
    ├── Context (string) — formatted text of retrieved records
    ├── Sources (string) — source attribution (project IDs, page numbers, file paths)
    └── Scores (string) — similarity scores for transparency
    ↓
Wired to downstream Planner/Interpreter input pins
```

**Why this mechanism:**

- **Consistent pattern.** Every Chirp component is a thin C# HTTP client calling the Chirp server. The retriever follows the same pattern — the only difference is the endpoint (`/retrieve` vs `/call`).
- **Python SDK advantage.** Pinecone, Chroma, Google AI, and OpenAI all have mature Python SDKs. The C# equivalents are less maintained or nonexistent. Keeping external API calls in Python avoids fragile C# HTTP wrappers.
- **Single gateway.** The Chirp server becomes the single point of contact for all external intelligence — LLM calls AND knowledge retrieval. One process to configure, one `.env` file with API keys, one place to add logging/caching/rate limiting.
- **API key isolation.** Embedding API keys and vector DB credentials stay in the Python server's `.env`, never exposed to the GH component or the C# runtime.

### Retriever as a Chirp Category

The retriever becomes the 8th Chirp category. Unlike the other 7, it doesn't call an LLM — it calls an embedding model + vector DB. But it follows the same lifecycle: `chirp_create` with `category: "retriever"`, auto-added pins, NickName on canvas, wirable into cascades.

| Category | Purpose | Backend | Module |
|----------|---------|---------|--------|
| planner | Brief → structured parameters | LLM (ChainOfThought) | DSPy |
| interpreter | Reasoning → domain parameters | LLM (ChainOfThought) | DSPy |
| critic | Multiple Reasonings → conflicts | LLM (ChainOfThought) | DSPy |
| narrator | Multiple Reasonings → narrative | LLM (ChainOfThought) | DSPy |
| classifier | Data → categorical decision | LLM (Predict) | DSPy |
| gate | Reasoning → rule activations | LLM (Predict) | DSPy |
| editor | Reasoning + Correction → reconciled | LLM (ChainOfThought) | DSPy |
| **retriever** | **Query → relevant context from knowledge base** | **Embedding + Vector DB** | **Similarity search** |

The retriever's auto-added pins would differ from the LLM categories:
- **No Reasoning output** — a retriever doesn't reason, it retrieves
- **No Correction input** — there's nothing to correct (but metadata filters serve a similar steering role)
- **Sources output** — attribution is mandatory for trust (which project, which page, what confidence)

### The Ingestion Pipeline (Separate From Chirp)

Populating and maintaining the vector database is NOT a Chirp responsibility. It's a firm-level knowledge management workflow that runs independently:

```
Project Archive (PDFs, photos, specs, drawings, post-mortems)
    ↓
Ingestion Script (Python — batch process)
    ├── For each document/image:
    │   ├── Generate embedding via Gemini Embeddings 2
    │   ├── Attach metadata (project ID, year, building type, material, cost, lessons)
    │   ├── Attach human-written description (quality here = retrieval quality later)
    │   └── Upsert to Pinecone (avoids duplicates on re-ingestion)
    └── Output: populated vector index, ready to query
```

**Quality depends on descriptions.** The embedding captures semantic meaning, but what the downstream LLM ultimately sees is the text description stored alongside the vector. "Photo of roof" retrieves far worse than "Standing seam zinc roof, 25-degree pitch, parapet detail at north edge, showing expansion joint at 12m intervals." Subject matter expertise in writing descriptions is more valuable than any technical configuration.

This could be a Rook tool (`knowledge_ingest`) or a standalone CLI script. The important thing is that it runs separately from the design workflow — you populate the database once (or periodically), and Chirp retriever components query it live during design.

### Open Questions

1. **How does the retriever handle images in its output?** GH pins are typed — a string pin can carry a text description of a retrieved image, but not the image itself. Options: (a) text summaries only, (b) file paths for downstream visualization, (c) both. For a first prototype, text descriptions are sufficient — the LLM reasons from text, not from pixels.

2. **Vector DB choice**: Pinecone (managed, free tier for prototyping) vs. Chroma (local, open source, no data leaves the firm). For architecture firms with sensitive project data, local Chroma may be preferred. For production scale, managed services handle indexing and availability.

3. **Embedding model choice**: Gemini Embeddings 2 is multimodal-native (one model for text + images + documents). Alternatives: OpenAI text-embedding-3 (text only, high quality), Voyage AI (text, strong on technical content), CLIP (images). The tradeoff is simplicity (one model, one vector space) vs. per-modality quality (specialized models, but multiple indices to manage).

4. **How many records is "enough"?** A small firm might have 50-200 projects. A large firm might have thousands. Retrieval quality depends on index density — too few records and the top-k results may be irrelevant. Need to test with real firm data to understand the minimum viable index size.

5. **Should retrieval results be cached?** If the same brief text hits the retriever repeatedly (e.g., during iterative design with sliders changing downstream), caching avoids redundant embedding + search calls. The Chirp adapter already caches LLM calls by input hash — the same pattern could apply to retrieval.
