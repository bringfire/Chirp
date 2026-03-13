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
        use_cache=False,
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
