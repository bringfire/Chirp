"""Tests for the FastAPI server — health check and request/response shape."""

from unittest.mock import patch
from fastapi.testclient import TestClient
from chirp.server import app


client = TestClient(app)


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
    with patch("chirp.server.adapter.call", return_value=mock_result):
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
    with patch("chirp.server.adapter.call", return_value=mock_result) as mock_call:
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
    with patch("chirp.server.adapter.call", return_value=mock_result) as mock_call:
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
    with patch("chirp.server.adapter.call", side_effect=ValueError("bad input")):
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
    with patch("chirp.server.adapter.call", side_effect=ValueError("bad")):
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
    with patch("chirp.server.adapter.call", side_effect=ValueError("bad")):
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
