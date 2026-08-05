"""Tests for the FastAPI server — health check and request/response shape."""

import asyncio
import importlib
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import chirp.adapter as adapter_module
import chirp.server as server


client = TestClient(server.app)


def _call_request() -> server.CallRequest:
    return server.CallRequest(
        signature="input -> result",
        inputs={"input": "x"},
        schema={"result": "string"},
        cache=False,
    )


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_chirp_call_success():
    """Mock the adapter and verify request parsing + response serialization."""
    mock_result = {
        "outputs": {"count": 5, "label": "test"},
        "reasoning": None,
        "usage": {"input_tokens": 100, "output_tokens": 20},
        "cached": False,
        "latency_ms": 500.0,
    }
    with patch("chirp.server.adapter.acall", new=AsyncMock(return_value=mock_result)):
        resp = client.post("/chirp/call", json={
            "signature": "input_text -> count, label",
            "inputs": {"input_text": "hello"},
            "schema": {"count": "int", "label": "string"},
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["outputs"] == {"count": 5, "label": "test"}
    assert data["cached"] is False
    assert data["latency_ms"] == 500.0


def test_chirp_call_with_cache_override():
    """Verify cache field is passed through to the adapter."""
    mock_result = {
        "outputs": {"x": 1},
        "reasoning": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "cached": False,
        "latency_ms": 100.0,
    }
    with patch(
        "chirp.server.adapter.acall", new=AsyncMock(return_value=mock_result)
    ) as mock_call:
        resp = client.post("/chirp/call", json={
            "signature": "a -> x",
            "inputs": {"a": "test"},
            "schema": {"x": "int"},
            "cache": False,
        })
    assert resp.status_code == 200
    mock_call.assert_called_once_with(
        signature="a -> x",
        inputs={"a": "test"},
        schema={"x": "int"},
        category=None,
        use_cache=False,
        model=None,
    )


def test_chirp_call_with_model_override():
    """Verify model field is passed through to the adapter."""
    mock_result = {
        "outputs": {"x": 1},
        "reasoning": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "cached": False,
        "latency_ms": 100.0,
        "model": "openai/mercury-2",
    }
    with patch(
        "chirp.server.adapter.acall", new=AsyncMock(return_value=mock_result)
    ) as mock_call:
        resp = client.post("/chirp/call", json={
            "signature": "a -> x",
            "inputs": {"a": "test"},
            "schema": {"x": "int"},
            "model": "openai/mercury-2",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "openai/mercury-2"
    mock_call.assert_called_once_with(
        signature="a -> x",
        inputs={"a": "test"},
        schema={"x": "int"},
        category=None,
        use_cache=None,
        model="openai/mercury-2",
    )


def test_chirp_call_error_returns_500():
    """Verify adapter exceptions return structured 500 errors, not 200."""
    with patch(
        "chirp.server.adapter.acall",
        new=AsyncMock(side_effect=ValueError("bad input")),
    ):
        resp = client.post("/chirp/call", json={
            "signature": "a -> b",
            "inputs": {"a": "test"},
            "schema": {"b": "int"},
        })
    assert resp.status_code == 500
    data = resp.json()
    assert data["error"] == "ValueError"
    assert "bad input" in data["details"]


def test_chirp_call_error_logs_override_model():
    """Verify that the error path includes the override model in the trace."""
    with patch(
        "chirp.server.adapter.acall", new=AsyncMock(side_effect=ValueError("bad"))
    ):
        with patch("chirp.server.tracer.log") as mock_log:
            client.post("/chirp/call", json={
                "signature": "a -> b",
                "inputs": {"a": "test"},
                "schema": {"b": "int"},
                "model": "openai/mercury-2",
            })
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args[1]
    assert call_kwargs["model"] == "openai/mercury-2"
    assert call_kwargs["error"] == "bad"


def test_chirp_call_error_logs_default_model():
    """Verify that the error path logs the default model when no override is set."""
    with patch(
        "chirp.server.adapter.acall", new=AsyncMock(side_effect=ValueError("bad"))
    ):
        with patch("chirp.server.tracer.log") as mock_log:
            client.post("/chirp/call", json={
                "signature": "a -> b",
                "inputs": {"a": "test"},
                "schema": {"b": "int"},
            })
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args[1]
    assert call_kwargs["model"] is not None
    assert call_kwargs["model"] != ""


def test_chirp_create_returns_script():
    """Verify /chirp/create returns generated C# script and pin metadata."""
    resp = client.post("/chirp/create", json={
        "pins_in": ["SurfaceDesc:string", "Intent:string"],
        "pins_out": ["UCount:int", "VCount:int", "Grading:float"],
        "signature": "surface_desc, intent -> u_count, v_count, grading",
        "category": "planner",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "script" in data
    assert "localhost:9900/chirp/call" in data["script"]
    # 2 user pins + auto-added Correction
    assert len(data["pins_in"]) == 3
    # 3 user pins + auto-added Reasoning
    assert len(data["pins_out"]) == 4


def test_chirp_create_with_deterministic_code():
    resp = client.post("/chirp/create", json={
        "pins_in": ["X:string"],
        "pins_out": ["Y:int"],
        "signature": "x -> y",
        "category": "planner",
        "deterministic_code": "Y = Y * 2;",
    })
    assert resp.status_code == 200
    assert "Y = Y * 2;" in resp.json()["script"]


def test_chirp_create_with_deterministic_only():
    resp = client.post("/chirp/create", json={
        "pins_in": ["X:string"],
        "pins_out": ["Y:string"],
        "signature": "x -> y",
        "category": "planner",
        "deterministic_code": 'Y = X?.ToString() ?? "";',
        "deterministic_only": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["deterministic_only"] is True
    assert "/chirp/call" not in data["script"]


def test_chirp_create_invalid_type_returns_400():
    resp = client.post("/chirp/create", json={
        "pins_in": ["X:string"],
        "pins_out": ["Y:FooBar"],
        "signature": "x -> y",
        "category": "planner",
    })
    assert resp.status_code == 400
    assert "Unknown output type" in resp.json()["details"]


def test_chirp_create_with_model():
    """Verify model field passes through to chirp_create and appears in result."""
    resp = client.post("/chirp/create", json={
        "pins_in": ["X:string"],
        "pins_out": ["Y:int"],
        "signature": "x -> y",
        "category": "gate",
        "model": "openai/mercury-2",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "openai/mercury-2"
    assert "mercury-2" in data["script"]


@pytest.mark.asyncio
async def test_wait_for_timeout_cancels_fake_provider_and_returns_504(monkeypatch):
    cancelled = asyncio.Event()
    provider_calls = 0

    class FakeProviderProgram:
        def __init__(self, _signature):
            pass

        async def acall(self, **_inputs):
            nonlocal provider_calls
            provider_calls += 1
            try:
                await asyncio.sleep(60)
            finally:
                cancelled.set()

    monkeypatch.setitem(adapter_module._MODULE_MAP, "ChainOfThought", FakeProviderProgram)
    monkeypatch.setattr(server, "inference_timeout_seconds", 0.02)
    started = time.monotonic()
    response = await server.chirp_call(_call_request())
    elapsed = time.monotonic() - started
    assert response.status_code == 504
    assert json.loads(response.body) == {
        "error": "chirp_inference_timeout",
        "details": "Chirp inference exceeded its configured total request budget.",
        "timeout_seconds": 0.02,
    }
    assert provider_calls == 1
    assert cancelled.is_set()
    assert elapsed < 0.5
    await asyncio.sleep(0.05)
    assert provider_calls == 1


@pytest.mark.asyncio
async def test_external_cancellation_is_not_timeout(monkeypatch):
    entered = asyncio.Event()

    async def blocked_acall(**_kwargs):
        entered.set()
        await asyncio.sleep(60)

    monkeypatch.setattr(server.adapter, "acall", blocked_acall)
    task = asyncio.create_task(server.chirp_call(_call_request()))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_invalid_timeout_disables_only_chirp_without_initializing_models(monkeypatch):
    monkeypatch.setenv("CHIRP_INFERENCE_TIMEOUT_SECONDS", "bad")
    constructor = patch(
        "chirp.adapter.ChirpAdapter",
        side_effect=AssertionError("invalid configuration must not initialize models"),
    )
    with constructor as mock_constructor:
        disabled_server = importlib.reload(server)
    try:
        disabled_client = TestClient(disabled_server.app)
        health = disabled_client.get("/health")
        assert health.status_code == 200
        assert health.json() == {
            "status": "disabled",
            "version": "0.1.0",
            "error": {
                "code": "chirp_invalid_inference_timeout",
                "message": (
                    "Chirp is disabled because CHIRP_INFERENCE_TIMEOUT_SECONDS must "
                    "contain only ASCII digits and resolve to 1–1800 seconds."
                ),
            },
        }
        expected = {
            "error": "chirp_invalid_inference_timeout",
            "details": (
                "Chirp is disabled because CHIRP_INFERENCE_TIMEOUT_SECONDS must "
                "contain only ASCII digits and resolve to 1–1800 seconds."
            ),
        }
        call = disabled_client.post(
            "/chirp/call",
            json={
                "signature": "input -> result",
                "inputs": {"input": "x"},
                "schema": {"result": "string"},
            },
        )
        create = disabled_client.post(
            "/chirp/create",
            json={
                "pins_in": ["Input:string"],
                "pins_out": ["Result:string"],
                "signature": "input -> result",
                "category": "classifier",
            },
        )
        assert call.status_code == 503
        assert call.json() == expected
        assert create.status_code == 503
        assert create.json() == expected
        mock_constructor.assert_not_called()
    finally:
        monkeypatch.delenv("CHIRP_INFERENCE_TIMEOUT_SECONDS", raising=False)
        importlib.reload(server)
