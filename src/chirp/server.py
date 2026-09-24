"""FastAPI HTTP server for the Chirp adapter."""

from __future__ import annotations

import atexit
import asyncio
import json
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from chirp.adapter import ChirpAdapter, ModelUnavailable, _load_providers, missing_credential
from chirp.rook_tool import chirp_create
from chirp.timeout_policy import (
    INVALID_TIMEOUT_CODE,
    INVALID_TIMEOUT_MESSAGE,
    read_inference_timeout_policy,
)
from chirp.tracing import TraceLogger
from chirp.vertex_bootstrap import (
    VertexAuthError,
    VertexBootstrap,
    VertexRestartRequired,
    vertex_gemini_model_name,
)

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
inference_timeout_policy = read_inference_timeout_policy()
inference_timeout_seconds = inference_timeout_policy.timeout_seconds
_rook_managed = False
_vertex_bootstrap: VertexBootstrap | None = None
adapter = (
    ChirpAdapter(
        inference_timeout_seconds=inference_timeout_seconds,
        rook_managed=_rook_managed,
        vertex_bootstrap=_vertex_bootstrap,
    )
    if inference_timeout_seconds is not None
    else None
)
tracer = TraceLogger()


def configure_bound_port(port: int) -> None:
    """Update discovery paths after the entry point binds an OS-assigned port."""
    global _CHIRP_PORT, _DISCOVERY_FILE
    _CHIRP_PORT = port
    _DISCOVERY_FILE = _DISCOVERY_FOLDER / f"chirp-service-{port}.json"


def configure_runtime(
    *,
    rook_managed: bool,
    vertex_bootstrap: VertexBootstrap | None,
) -> None:
    """Apply private process bootstrap state before the server starts."""
    global _rook_managed, _vertex_bootstrap, adapter
    _rook_managed = bool(rook_managed)
    _vertex_bootstrap = vertex_bootstrap
    if inference_timeout_seconds is None:
        adapter = None
        return
    adapter = ChirpAdapter(
        inference_timeout_seconds=inference_timeout_seconds,
        rook_managed=rook_managed,
        vertex_bootstrap=vertex_bootstrap,
    )


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
async def chirp_call(req: CallRequest):
    if not inference_timeout_policy.enabled:
        return _invalid_timeout_response()

    effective_model = req.model or adapter._default_model
    try:
        result = await asyncio.wait_for(
            adapter.acall(
                signature=req.signature,
                inputs=req.inputs,
                schema=req.schema_,
                category=req.category,
                use_cache=req.cache,
                model=req.model,
            ),
            timeout=inference_timeout_seconds,
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
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={
                "error": "chirp_inference_timeout",
                "details": "Chirp inference exceeded its configured total request budget.",
                "timeout_seconds": inference_timeout_seconds,
            },
        )
    except asyncio.CancelledError:
        raise
    except ModelUnavailable as e:
        # No credential for the model: answer at once so the component can fall
        # back to its frozen result or deterministic defaults.
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
            status_code=503,
            content={"error": "model_unavailable", "details": str(e)},
        )
    except VertexAuthError as e:
        return JSONResponse(
            status_code=503,
            content={"error": e.code, "details": e.public_message},
        )
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
    if not inference_timeout_policy.enabled:
        return _invalid_timeout_response()

    try:
        effective_model = adapter.resolve_model(req.category, req.model)
        _assert_vertex_runtime(effective_model)
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
    except VertexAuthError as e:
        return JSONResponse(
            status_code=503,
            content={"error": e.code, "details": e.public_message},
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": "ValueError", "details": str(e)},
        )


def _invalid_timeout_response() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": INVALID_TIMEOUT_CODE,
            "details": INVALID_TIMEOUT_MESSAGE,
        },
    )


@app.get("/health")
def health() -> dict:
    vertex_state, vertex_error = _vertex_health()
    base = {
        "version": "0.1.0",
        "rook_managed": _rook_managed,
        "vertex": {"status": vertex_state},
    }
    if not inference_timeout_policy.enabled:
        return {
            "status": "disabled",
            **base,
            "error": {
                "code": INVALID_TIMEOUT_CODE,
                "message": INVALID_TIMEOUT_MESSAGE,
            },
        }
    if vertex_error is not None:
        return {
            "status": "disabled",
            **base,
            "error": {
                "code": vertex_error.code,
                "message": vertex_error.public_message,
            },
        }
    return {"status": "ok", **base}


@app.get("/health/model")
def health_model() -> dict:
    """Credential readiness of the default model, from the environment alone.

    Lets components and Rook tell "no key" apart from "adapter down" without
    initialising any model or resolving managed credentials. Vertex models are
    reported through /health instead.
    """
    default_model = (
        adapter._default_model
        if adapter is not None
        else os.environ.get("CHIRP_MODEL", "anthropic/claude-opus-5")
    )
    try:
        is_vertex = vertex_gemini_model_name(default_model) is not None
    except VertexAuthError:
        is_vertex = True
    reason = None if is_vertex else missing_credential(default_model, _load_providers().get(default_model))
    return {"model": default_model, "model_ready": reason is None, "model_reason": reason}


def _vertex_health() -> tuple[str, VertexAuthError | None]:
    state = "absent"
    generation_error: VertexRestartRequired | None = None
    if _vertex_bootstrap is not None:
        try:
            _vertex_bootstrap.assert_current_generation()
            state = "ready"
        except VertexRestartRequired as exc:
            state = "stale"
            generation_error = exc

    default_model = (
        adapter._default_model
        if adapter is not None
        else os.environ.get("CHIRP_MODEL", "anthropic/claude-opus-5")
    )
    try:
        is_vertex = vertex_gemini_model_name(default_model) is not None
    except VertexAuthError as exc:
        return state, exc
    if not is_vertex:
        return state, None
    if _vertex_bootstrap is None and _rook_managed:
        return state, VertexAuthError(
            "vertex_signed_out",
            "Vertex AI is not configured for this managed Chirp process.",
        )
    if generation_error is not None:
        return state, generation_error
    default_error = getattr(adapter, "_default_model_error", None)
    if isinstance(default_error, VertexAuthError):
        return state, default_error
    return state, None


def _assert_vertex_runtime(model: str | None) -> None:
    if vertex_gemini_model_name(model) is None:
        return
    if _vertex_bootstrap is None:
        if _rook_managed:
            raise VertexAuthError(
                "vertex_signed_out",
                "Vertex AI is not configured for this managed Chirp process.",
            )
        return
    _vertex_bootstrap.assert_current_generation()
