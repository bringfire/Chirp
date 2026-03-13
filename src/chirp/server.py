"""FastAPI HTTP server for the Chirp adapter."""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from chirp.adapter import ChirpAdapter
from chirp.rook_tool import chirp_create
from chirp.tracing import TraceLogger

app = FastAPI(title="Chirp", version="0.1.0")
adapter = ChirpAdapter()
tracer = TraceLogger()


class CallRequest(BaseModel):
    model_config = {"populate_by_name": True}

    signature: str
    inputs: dict
    schema_: dict[str, str] = Field(alias="schema")
    cache: bool | None = None


class CallResponse(BaseModel):
    outputs: dict
    reasoning: str | None = None
    usage: dict
    cached: bool
    latency_ms: float


class ErrorResponse(BaseModel):
    error: str
    details: str


@app.post("/chirp/call", response_model=CallResponse)
def chirp_call(req: CallRequest):
    try:
        result = adapter.call(
            signature=req.signature,
            inputs=req.inputs,
            schema=req.schema_,
            use_cache=req.cache,
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
        )
        return JSONResponse(
            status_code=500,
            content={"error": type(e).__name__, "details": str(e)},
        )


class CreateRequest(BaseModel):
    pins_in: list[str]
    pins_out: list[str]
    signature: str
    deterministic_code: str | None = None
    port: int | None = None


@app.post("/chirp/create")
def chirp_create_endpoint(req: CreateRequest):
    try:
        result = chirp_create(
            pins_in=req.pins_in,
            pins_out=req.pins_out,
            signature=req.signature,
            deterministic_code=req.deterministic_code,
            port=req.port,
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
