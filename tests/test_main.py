from __future__ import annotations

import importlib
import io
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from chirp.vertex_bootstrap import VertexBootstrapError


GENERATION = "0123456789abcdef0123456789abcdef"


class _UntouchableInput:
    def readline(self, *_args, **_kwargs):
        raise AssertionError("standalone startup read stdin")

    def read(self, *_args, **_kwargs):
        raise AssertionError("standalone startup read stdin")


def _bootstrap_stream():
    payload = {
        "schema_version": 1,
        "generation": GENERATION,
        "mode": "oauth",
        "project_id": "company-ai-project",
        "region": "us-central1",
        "vertex_credentials": {
            "type": "authorized_user",
            "client_id": "main-client-sentinel",
            "client_secret": "main-secret-sentinel",
            "refresh_token": "main-refresh-sentinel",
        },
    }
    return io.BytesIO(json.dumps(payload).encode("utf-8") + b"\n")


@pytest.fixture
def main_module(monkeypatch):
    prior_bound_port = os.environ.get("_CHIRP_BOUND_PORT")
    monkeypatch.setenv("CHIRP_PORT", "0")
    os.environ.pop("_CHIRP_BOUND_PORT", None)
    sys.modules.pop("chirp.__main__", None)
    with patch("uvicorn.Server.run"), patch("uvicorn.run"):
        module = importlib.import_module("chirp.__main__")
    old_socket = getattr(module, "sock", None)
    if old_socket is not None:
        old_socket.close()
    try:
        yield module
    finally:
        if prior_bound_port is None:
            os.environ.pop("_CHIRP_BOUND_PORT", None)
        else:
            os.environ["_CHIRP_BOUND_PORT"] = prior_bound_port


def test_standalone_startup_never_reads_stdin(main_module):
    with patch("chirp.server.configure_runtime") as configure:
        with patch.object(main_module, "_run_server") as run_server:
            main_module.main([], stdin=_UntouchableInput())

    configure.assert_called_once_with(rook_managed=False, vertex_bootstrap=None)
    run_server.assert_called_once()
    assert run_server.call_args.kwargs["rook_managed"] is False


def test_managed_vertex_bootstrap_is_applied_only_in_memory(main_module):
    argv = ["--rook-managed", "--rook-vertex-bootstrap-stdin"]
    with patch("chirp.server.configure_runtime") as configure:
        with patch.object(main_module, "_run_server") as run_server:
            main_module.main(argv, stdin=_bootstrap_stream())

    bootstrap = configure.call_args.kwargs["vertex_bootstrap"]
    assert configure.call_args.kwargs["rook_managed"] is True
    assert bootstrap.generation == GENERATION
    assert run_server.call_args.kwargs["rook_managed"] is True
    combined_process_surface = " ".join(argv) + " " + " ".join(
        f"{key}={value}" for key, value in main_module.os.environ.items()
    )
    for secret in (
        "main-client-sentinel",
        "main-secret-sentinel",
        "main-refresh-sentinel",
    ):
        assert secret not in combined_process_surface


def test_invalid_bootstrap_fails_before_server_start(main_module):
    with patch.object(main_module, "_run_server") as run_server:
        with pytest.raises(VertexBootstrapError):
            main_module.main(
                ["--rook-vertex-bootstrap-stdin"],
                stdin=_bootstrap_stream(),
            )
    run_server.assert_not_called()


def test_managed_server_registers_retirement_listener(main_module, monkeypatch):
    class FakeSocket:
        def __init__(self, *_args):
            pass

        def setsockopt(self, *_args):
            pass

        def bind(self, address):
            assert address == ("127.0.0.1", 0)

        def getsockname(self):
            return ("127.0.0.1", 43123)

        def close(self):
            pass

    server_instance = SimpleNamespace(run=lambda **_kwargs: None, should_exit=False)
    monkeypatch.setenv("CHIRP_PORT", "0")
    monkeypatch.setenv("CHIRP_RELOAD", "0")
    monkeypatch.setattr(main_module.socket, "socket", FakeSocket)
    monkeypatch.setattr(main_module.uvicorn, "Config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(main_module.uvicorn, "Server", lambda _config: server_instance)
    configured_ports = []
    server_module = SimpleNamespace(
        app=object(),
        configure_bound_port=configured_ports.append,
    )
    with patch.object(main_module, "start_retirement_listener") as start_listener:
        main_module._run_server(server_module, rook_managed=True)

    start_listener.assert_called_once_with(server_instance, rook_managed=True)
    assert configured_ports == [43123]
    assert main_module.os.environ["_CHIRP_BOUND_PORT"] == "43123"
