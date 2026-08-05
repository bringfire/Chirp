<h1 align="center">CHIRP</h1>

<p align="center">
  <img src="docs/Images/Chirp.png" alt="Chirp Logo" width="345">
</p>

<p align="center">
  <strong>Adapter service for intelligent Grasshopper components with embedded LLM calls</strong>
</p>

<p align="center">
  7 component categories &bull; DSPy-powered reasoning &bull; Typed pin contracts &bull; JSONL tracing
</p>

---

Chirp enables [Rook](https://github.com/bringfire/Rook) to create intelligent Grasshopper script components on the fly. Each component embeds an LLM call constrained by typed output pins — the Grasshopper type system becomes the structural boundary between open-ended intelligence and deterministic dataflow.

## Quick Start

```
1. Clone the repo and create a virtual environment
2. pip install -e ".[dev]"
3. Set ANTHROPIC_API_KEY in a .env file
4. python -m chirp
5. The adapter binds to 127.0.0.1 on an OS-assigned port (discovery file written to %TEMP%/rook/)
```

## Architecture

```
Rook MCP Server (Python)
       │
       │  chirp_create tool call (~100 tokens)
       ▼
Chirp Adapter (FastAPI)              ← format → LLM → parse → validate → cache → trace
       │
       │  DSPy module (ChainOfThought / Predict)
       ▼
LLM (Claude, via LiteLLM)           ← model-agnostic, configurable via CHIRP_MODEL
       │
       ▼
Generated C# Script Component       ← typed pins enforce output contract on GH canvas
```

| Layer | Role |
|-------|------|
| **chirp_create** | Token-efficient creation tool. Rook passes pin definitions, a DSPy signature, and a category in ~100 tokens. Returns complete C# script component source with typed pins. |
| **ChirpAdapter** | Core bridge — builds typed DSPy signatures from schema, selects module per category, calls LLM, coerces outputs to target types, caches results. |
| **Discovery** | OS-assigned port with `chirp-service-{port}.json` written to `%TEMP%/rook/`. Rook consumers discover the adapter via glob. Atomic write, PID-aware stale cleanup. |
| **Tracing** | Every call logged as JSONL — signature, inputs, outputs, errors, latency, token usage, cache hits. |

## Component Categories

Each category determines the DSPy module and prompt strategy:

| Category | Module | Purpose |
|----------|--------|---------|
| **planner** | ChainOfThought | Translates a design brief into structured parameters |
| **interpreter** | ChainOfThought | Reads upstream reasoning through a domain-specific lens |
| **critic** | ChainOfThought | Checks consistency across multiple reasoning streams |
| **narrator** | ChainOfThought | Synthesizes reasoning streams into a design narrative |
| **classifier** | Predict | Classifies data into categories with confidence |
| **gate** | Predict | Activates or deactivates rules based on reasoning |
| **editor** | ChainOfThought | Reconciles upstream reasoning with human corrections |

Every component automatically gets a **Correction** input pin (human override) and a **Reasoning** output pin (LLM chain-of-thought).

## Key Features

### Typed Pin Contracts

GH component typed output pins *are* the structural constraint — the DSPy Signature-as-Contract pattern enforced physically. The LLM has full flexibility inside the component, but downstream dataflow is protected by the type system.

Supported types: `int`, `float`, `double`, `string`, `bool`, `Point3d`, `Vector3d`, `Plane`, `Line`, `Curve`, `Surface`, `Brep`, `Mesh`, `Box`, `Circle`, `Arc`, `Polyline`

### Reasoning Cascades

Chain multiple Chirp components into multi-disciplinary reasoning cascades. The Reasoning pin fans out from upstream components into downstream interpreters, critics, and narrators — each reading through their own domain lens.

### Port-Zero Discovery

The adapter binds to `127.0.0.1:0` by default — the OS assigns a free port. A discovery file is written atomically to `%TEMP%/rook/chirp-service-{port}.json` after the server is ready. Set `CHIRP_PORT` to a nonzero value to pin a specific port.

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `CHIRP_MODEL` | `anthropic/claude-opus-5` | LLM model (any LiteLLM-compatible string) |
| `CHIRP_PORT` | `0` (OS-assigned) | Port override — nonzero pins a specific port |
| `CHIRP_CACHE` | `true` | Enable/disable in-memory result cache |
| `CHIRP_TRACE_DIR` | `./traces` | Directory for JSONL trace logs |
| `CHIRP_RELOAD` | `0` | Set to `1` for uvicorn hot-reload during development |
| `ANTHROPIC_API_KEY` | — | API key (loaded from `.env`) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chirp/call` | Execute an LLM call with typed schema validation |
| `POST` | `/chirp/create` | Generate a C# script component from pin definitions |
| `GET`  | `/health` | Health check |

## Project Structure

```
Chirp/
├── src/chirp/
│   ├── __main__.py          # Entry point — pre-bound socket, uvicorn startup
│   ├── server.py            # FastAPI app, discovery file, lifespan management
│   ├── adapter.py           # Core adapter — DSPy module selection, type coercion, caching
│   ├── rook_tool.py         # chirp_create — C# script generation with typed pins
│   ├── types.py             # Type mapping (schema strings ↔ Python/Pydantic types)
│   └── tracing.py           # JSONL trace logger
│
├── skills/
│   └── chirp-cascade/       # Claude Code skill for multi-component reasoning cascades
│
├── templates/               # Reference C# templates
├── tests/                   # pytest suite
├── traces/                  # JSONL trace output
├── docs/
│   ├── Images/              # Project assets
│   └── plans/               # Design docs and implementation plans
└── pyproject.toml           # Package config (Python 3.10+, setuptools)
```

## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.10+ | 3.13 recommended |
| **Rook** | Latest | The MCP bridge that calls chirp_create |
| **Rhino** | 8.x | Windows only |

## Installation

```bash
git clone https://github.com/bringfire/Chirp.git
cd Chirp
python -m venv .venv
source .venv/Scripts/activate   # Windows/Git Bash
pip install -e ".[dev]"
```

Create a `.env` file with your API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Run the adapter:

```bash
python -m chirp
```

## License

MIT License
