"""FastAPI HTTP server for the Chirp adapter."""

from __future__ import annotations

import atexit
import json
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from chirp.adapter import ChirpAdapter
from chirp.rook_tool import chirp_create
from chirp.tracing import TraceLogger

# --- Discovery file (written only after server is ready) ---
_DISCOVERY_FOLDER = Path(tempfile.gettempdir()) / "rook"
_CHIRP_PORT = int(
    os.environ.get("_CHIRP_BOUND_PORT", os.environ.get("CHIRP_PORT", "9900"))
)
_DISCOVERY_FILE = _DISCOVERY_FOLDER / f"chirp-service-{_CHIRP_PORT}.json"


def _is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is still running."""
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _write_discovery():
    _DISCOVERY_FOLDER.mkdir(parents=True, exist_ok=True)
    # Remove stale discovery files from dead processes (port 0 creates new
    # filenames each time; without cleanup the glob finds multiple entries).
    for stale in _DISCOVERY_FOLDER.glob("chirp-service-*.json"):
        try:
            data = json.loads(stale.read_text(encoding="utf-8"))
            pid = data.get("pid")
            if pid is not None and _is_pid_alive(pid):
                continue  # Another live Chirp instance — leave its file
        except (OSError, json.JSONDecodeError):
            pass
        try:
            stale.unlink()
        except OSError:
            pass
    payload = {
        "service": "chirp",
        "host": "127.0.0.1",
        "port": _CHIRP_PORT,
        "pid": os.getpid(),
        "home": str(Path(__file__).resolve().parent.parent.parent),
        "version": "0.1.0",
        "startTime": datetime.now().isoformat(timespec="seconds"),
    }
    # Atomic write: mkstemp + fsync + os.replace() (matches Rook chat server pattern).
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{_DISCOVERY_FILE.name}.",
        suffix=".tmp",
        dir=_DISCOVERY_FOLDER,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(json.dumps(payload, indent=2))
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_name, _DISCOVERY_FILE)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _cleanup_discovery():
    try:
        _DISCOVERY_FILE.unlink(missing_ok=True)
    except OSError:
        pass


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _write_discovery()
    atexit.register(_cleanup_discovery)
    yield
    _cleanup_discovery()


app = FastAPI(title="Chirp", version="0.1.0", lifespan=_lifespan)
adapter = ChirpAdapter()
tracer = TraceLogger()


class CallRequest(BaseModel):
    model_config = {"populate_by_name": True}

    signature: str
    inputs: dict
    schema_: dict[str, str] = Field(alias="schema")
    category: str | None = None
    cache: bool | None = None
    model: str | None = None


class CallResponse(BaseModel):
    outputs: dict
    reasoning: str | None = None
    usage: dict
    cached: bool
    latency_ms: float
    model: str | None = None


class ErrorResponse(BaseModel):
    error: str
    details: str


@app.post("/chirp/call", response_model=CallResponse)
def chirp_call(req: CallRequest):
    effective_model = req.model or adapter._default_model
    try:
        result = adapter.call(
            signature=req.signature,
            inputs=req.inputs,
            schema=req.schema_,
            category=req.category,
            use_cache=req.cache,
            model=req.model,
        )
        tracer.log(
            signature=req.signature,
            inputs=req.inputs,
            schema=req.schema_,
            outputs=result["outputs"],
            error=None,
            latency_ms=result["latency_ms"],
            usage=result["usage"],
            cache_hit=result["cached"],
            model=result.get("model"),
        )
        return CallResponse(**result)
    except Exception as e:
        tracer.log(
            signature=req.signature,
            inputs=req.inputs,
            schema=req.schema_,
            outputs=None,
            error=str(e),
            latency_ms=0,
            usage={"input_tokens": 0, "output_tokens": 0},
            cache_hit=False,
            model=effective_model,
        )
        return JSONResponse(
            status_code=500,
            content={"error": type(e).__name__, "details": str(e)},
        )


class CreateRequest(BaseModel):
    pins_in: list[str]
    pins_out: list[str]
    signature: str
    category: str
    name: str | None = None
    deterministic_code: str | None = None
    deterministic_only: bool = False
    port: int | None = None
    model: str | None = None


@app.post("/chirp/create")
def chirp_create_endpoint(req: CreateRequest):
    try:
        result = chirp_create(
            pins_in=req.pins_in,
            pins_out=req.pins_out,
            signature=req.signature,
            category=req.category,
            name=req.name,
            deterministic_code=req.deterministic_code,
            deterministic_only=req.deterministic_only,
            port=req.port,
            model=req.model,
        )
        return result
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": "ValueError", "details": str(e)},
        )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
