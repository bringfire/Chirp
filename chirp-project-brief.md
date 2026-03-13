# Chirp — Project Brief for Claude Code

## What is Chirp?

Chirp is a spec-driven code generation pipeline for **Grasshopper components** (RhinoCommon / C#), built for use at **Safdie Architects**. It is inspired by [CodeSpeak](https://codespeak.dev/) — a next-generation LLM-powered programming language that compiles plain-English specs into traditional code, achieving 5-10x LOC reduction. Chirp applies the same core concept to a narrow, high-value target: Grasshopper component authoring inside Rhino.

The name "Chirp" references the sound a grasshopper makes — a spec is a chirp: minimal, intentional, enough.

---

## Background & Inspiration

### CodeSpeak (https://codespeak.dev/)
- Built by **Andrey Breslav**, creator of the Kotlin programming language
- Currently in alpha; install via `uv tool install codespeak-cli`
- Supports Python, Go, JS/TS as compile targets (Kotlin and Swift mentioned in broader docs)
- Core idea: maintain **specs** not code; LLM agents generate the implementation
- BYOK (Bring Your Own Key) model — uses your own Anthropic/OpenAI API key
- Real-world case studies show 6-10x LOC reduction on open-source Python projects with all tests passing
- Mixed-mode projects supported: some files are spec-managed, others are hand-written
- Relevant blog posts to read:
  - https://codespeak.dev/blog/mixed-mode-tutorial-20260210
  - https://codespeak.dev/blog/codespeak-takeover-20260223
  - https://codespeak.dev/blog/modularity-20260309

CodeSpeak is **closed source** and does not currently support UE5 C++ or RhinoCommon/C#. Chirp is an independent implementation of the same concept for the Safdie architectural workflow.

---

## Why RhinoCommon / Grasshopper?

- **Grasshopper components** are the primary computational design tool at Safdie Architects
- Component authorship is extremely boilerplate-heavy:
  - Every component requires `RegisterInputParams`, `RegisterOutputParams`, `SolveInstance`
  - `DA.GetData` / `DA.GetDataList` calls must exactly match registered input types
  - All geometry requires null/validity checks with `AddRuntimeMessage`
  - Doc-accessing components need `RhinoDoc` + transaction scaffolding
- The variation between components is only in *what they do*, not *how they are structured*
- This is exactly the CodeSpeak value proposition: the **what** is spec, the **how** is generated

### Existing context at Safdie:
- Aaron is the AI lead at Safdie Architects, actively building a **Claude-in-Rhino MCP plugin** with HTTP API capabilities
- The firm uses Rhino/Grasshopper extensively on projects including **King Salman Park** in Riyadh
- Aaron has previously built Rhino Python scripting tools and Grasshopper parametric workflows
- The end goal is to integrate Chirp as a **tool inside the Claude-in-Rhino plugin**, so developers can describe a component in plain English inside Rhino and get a compilable `.cs` file back without leaving the environment

---

## Implementation Plan

### Phase 1: Golden Templates
Collect 3-5 real, compilable Grasshopper components from existing Safdie project work. Target variety:
- Simple geometry-in / geometry-out
- Multiple mixed input/output types (curves, numbers, booleans)
- A component that accesses `RhinoDoc` (layers, objects)

**Annotate each inline** — explain *why* each section is mandatory, not just what it does. These annotations are what constrain the LLM's generation space.

### Phase 2: Spec Format
Plain YAML. Example:

```yaml
component: DiagridGenerator
category: Safdie
subcategory: Structure
description: Generates a diagrid surface from a base surface and division counts

inputs:
  - name: Surface
    type: Surface
    description: Base surface to diagrid
  - name: UCount
    type: int
    default: 10
    description: Divisions in U direction
  - name: VCount
    type: int
    default: 10
    description: Divisions in V direction

outputs:
  - name: Mesh
    type: Mesh
    description: Resulting diagrid mesh
  - name: Curves
    type: Curve
    list: true
    description: Individual diagrid members as curves

doc_access: false
```

The `doc_access` boolean flag determines which template branch is used — doc-accessing components require meaningfully different scaffolding.

### Phase 3: Generation Prompt
A system prompt with three sections:

**Section 1 — Hard rules:**
- `DA.GetData` / `DA.GetDataList` must match registered input type exactly
- `DA.SetData` / `DA.SetDataList` must match registered output type exactly
- All geometry must be null/validity checked; use `AddRuntimeMessage` on failure
- `GH_RuntimeMessageLevel.Warning` allows downstream to continue; `Error` halts — specify which to use
- Namespace conventions for Safdie firm codebase

**Section 2 — Golden templates in full** (verbatim, annotated)

**Section 3 — Output format rules:**
- Single `.cs` file only
- No explanation, no markdown outside the code block
- No placeholder comments like `// add logic here`
- Incomplete generation = hard failure, do not emit partial output

### Phase 4: Compile Loop (`codegen.py`)
A Python script, lives in the repo, invoked as `python codegen.py <spec.yaml>`:

```python
# Pseudocode
spec = load_yaml(sys.argv[1])
prompt = build_prompt(system_prompt, spec)
response = call_claude_api(prompt)
cs_code = parse_code_block(response)
write_file(f"Components/{spec['component']}.cs", cs_code)

for attempt in range(3):
    result = run("dotnet build")
    if result.success:
        print("Success:", output_path)
        exit(0)
    else:
        errors = extract_build_errors(result.stderr)
        cs_code = call_claude_api_fix(cs_code, errors)
        write_file(...)

# If still failing after 3 attempts:
write_log(errors)
exit(1)
```

Three retry passes is the ceiling. If it hasn't resolved in three attempts, the spec or template has a problem requiring human intervention.

### Phase 5: Rhino Plugin Integration
Add a tool to the existing Claude-in-Rhino MCP server:

```
generate_gh_component(spec: string) -> string
```

- Input: YAML spec as string
- Action: runs `codegen.py`, waits for result
- Output: file path on success, error log on failure

This enables the end-state: describe a Grasshopper component to Claude inside Rhino → Claude generates the spec → calls the tool → compiles → reports back, without leaving Rhino.

---

## Rollout Timeline

| Week | Goal |
|------|------|
| 1 | Write golden templates + finalize spec format. Write 5 specs manually for existing components. Revise format until spec-writing feels natural. No code yet. |
| 2 | Write the generation prompt. Test manually in Claude (not Claude Code) — paste prompt + spec, iterate until 80%+ of outputs are compilable on first try. |
| 3 | Build `codegen.py`, wire compile loop, test retry logic deliberately with broken specs. |
| 4 | Integrate as tool in Claude-in-Rhino plugin. Internal demo at Safdie. |

**Real milestone: end of Week 2.** Everything after is plumbing.

---

## Key Technical References

### RhinoCommon / Grasshopper SDK
- RhinoCommon API docs: https://developer.rhino3d.com/api/rhinocommon/
- Grasshopper SDK docs: https://developer.rhino3d.com/api/grasshopper/
- Grasshopper component authoring guide: https://developer.rhino3d.com/guides/grasshopper/your-first-component/
- RhinoCommon C# guides: https://developer.rhino3d.com/guides/rhinocommon/

### CodeSpeak (reference implementation to study)
- Homepage: https://codespeak.dev/
- Mixed-mode tutorial: https://codespeak.dev/blog/mixed-mode-tutorial-20260210
- Takeover (code → spec): https://codespeak.dev/blog/codespeak-takeover-20260223
- Modularity post: https://codespeak.dev/blog/modularity-20260309
- Case studies: https://codespeak.dev/#case-studies

---

## Scope Boundaries

Chirp is **not** an attempt to cover all of RhinoCommon. It covers:
- `GH_Component` subclasses (Grasshopper components) — primary target
- Potentially `RhinoCommand` subclasses — secondary target, same approach
- Firm-specific namespace/category conventions baked into templates

It does **not** attempt to cover:
- Arbitrary RhinoCommon geometry operations
- Rhino plugin boilerplate beyond commands
- Any automatic Grasshopper canvas manipulation

---

## Project Name

**Chirp** — named for the sound a grasshopper makes. A spec is a chirp: minimal, intentional, sufficient.
