from __future__ import annotations

import io
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from chirp.vertex_bootstrap import (
    RETIREMENT_EVENT_NAME,
    VertexAuthError,
    VertexBootstrap,
    VertexBootstrapError,
    VertexRestartRequired,
    read_managed_bootstrap,
    start_retirement_listener,
)


GENERATION = "0123456789abcdef0123456789abcdef"
ROTATED_GENERATION = "fedcba9876543210fedcba9876543210"
AUTHORIZED_USER = {
    "type": "authorized_user",
    "client_id": "vertex-client-sentinel",
    "client_secret": "vertex-secret-sentinel",
    "refresh_token": "vertex-refresh-sentinel",
}


def _payload(**overrides):
    payload = {
        "schema_version": 1,
        "generation": GENERATION,
        "mode": "oauth",
        "project_id": "company-ai-project",
        "region": "us-central1",
        "vertex_credentials": dict(AUTHORIZED_USER),
    }
    payload.update(overrides)
    return payload


def _stream(payload, *, trailing=b""):
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return io.BytesIO(encoded + b"\n" + trailing)


class _UntouchableInput:
    def readline(self, *_args, **_kwargs):
        raise AssertionError("stdin was read without the bootstrap flag")

    def read(self, *_args, **_kwargs):
        raise AssertionError("stdin was read without the bootstrap flag")


def test_standalone_and_managed_without_bootstrap_never_read_stdin():
    assert read_managed_bootstrap([], _UntouchableInput()) == (False, None)
    assert read_managed_bootstrap(
        ["--rook-managed"],
        _UntouchableInput(),
    ) == (True, None)


def test_managed_bootstrap_reads_one_bounded_line_and_eof():
    managed, bootstrap = read_managed_bootstrap(
        ["--rook-managed", "--rook-vertex-bootstrap-stdin"],
        _stream(_payload()),
    )

    assert managed is True
    assert bootstrap == VertexBootstrap(**_payload())
    assert "vertex-refresh-sentinel" not in repr(bootstrap)
    assert "vertex-secret-sentinel" not in repr(bootstrap)


@pytest.mark.parametrize(
    ("argv", "stream"),
    [
        (["--rook-vertex-bootstrap-stdin"], _stream(_payload())),
        (["--rook-managed", "--rook-managed"], _UntouchableInput()),
        (
            [
                "--rook-managed",
                "--rook-vertex-bootstrap-stdin",
                "--rook-vertex-bootstrap-stdin",
            ],
            _stream(_payload()),
        ),
        (
            ["--rook-managed", "--rook-vertex-bootstrap-stdin"],
            io.BytesIO(b"{not-json}\n"),
        ),
        (
            ["--rook-managed", "--rook-vertex-bootstrap-stdin"],
            _stream(_payload(), trailing=b"second-line\n"),
        ),
        (
            ["--rook-managed", "--rook-vertex-bootstrap-stdin"],
            io.BytesIO(b"{" + (b"x" * 65_536) + b"}\n"),
        ),
        (
            ["--rook-managed", "--rook-vertex-bootstrap-stdin"],
            io.BytesIO(b"\xff\n"),
        ),
    ],
)
def test_bootstrap_transport_rejects_invalid_flag_or_stream_shapes(argv, stream):
    with pytest.raises(VertexBootstrapError) as exc_info:
        read_managed_bootstrap(argv, stream)

    message = str(exc_info.value)
    assert "vertex-refresh-sentinel" not in message
    assert "vertex-secret-sentinel" not in message


@pytest.mark.parametrize(
    "raw",
    [
        '{"schema_version":1,"schema_version":1}',
        json.dumps({**_payload(), "extra": "forbidden"}),
        json.dumps(_payload(schema_version=2)),
        json.dumps(_payload(generation="ABC")),
        json.dumps(_payload(project_id="Bad Project")),
        json.dumps(_payload(region="bad region")),
        json.dumps(_payload(mode="oauth", vertex_credentials=None)),
        json.dumps(
            _payload(
                mode="oauth",
                vertex_credentials={**AUTHORIZED_USER, "extra": "forbidden"},
            )
        ),
        json.dumps(_payload(mode="adc", vertex_credentials=AUTHORIZED_USER)),
        json.dumps(_payload(mode="service_account", vertex_credentials="relative.json")),
    ],
)
def test_bootstrap_payload_rejects_incoherent_or_noncanonical_records(raw):
    stream = io.BytesIO(raw.encode("utf-8") + b"\n")

    with pytest.raises(VertexBootstrapError):
        read_managed_bootstrap(
            ["--rook-managed", "--rook-vertex-bootstrap-stdin"],
            stream,
        )


def test_adc_and_service_account_modes_are_strict(tmp_path: Path):
    service_account = tmp_path / "service-account.json"
    service_account.write_text("{}", encoding="utf-8")

    _, adc = read_managed_bootstrap(
        ["--rook-managed", "--rook-vertex-bootstrap-stdin"],
        _stream(_payload(mode="adc", vertex_credentials=None)),
    )
    _, service = read_managed_bootstrap(
        ["--rook-managed", "--rook-vertex-bootstrap-stdin"],
        _stream(
            _payload(
                mode="service_account",
                vertex_credentials=str(service_account.resolve()),
            )
        ),
    )

    assert adc.vertex_credentials is None
    assert service.vertex_credentials == str(service_account.resolve())


def test_vertex_model_kwargs_are_closed_and_non_vertex_is_untouched():
    bootstrap = VertexBootstrap(**_payload())

    assert bootstrap.vertex_kwargs_for_model("gemini/gemini-2.5-pro") == {}
    assert bootstrap.vertex_kwargs_for_model("vertex_ai/gemini-2.5-pro") == {
        "vertex_project": "company-ai-project",
        "vertex_location": "us-central1",
        "vertex_credentials": AUTHORIZED_USER,
    }
    with pytest.raises(VertexAuthError) as exc_info:
        bootstrap.vertex_kwargs_for_model("vertex_ai/claude-sonnet")
    assert exc_info.value.code == "vertex_model_family_unsupported"


def test_generation_change_or_removal_requires_restart_before_provider(tmp_path: Path):
    store = tmp_path / "vertex.json"
    store.write_text(json.dumps({"generation": GENERATION}), encoding="utf-8")
    bootstrap = VertexBootstrap(**_payload())

    bootstrap.assert_current_generation(store)
    store.write_text(
        json.dumps({"generation": ROTATED_GENERATION}),
        encoding="utf-8",
    )
    with pytest.raises(VertexRestartRequired) as changed:
        bootstrap.assert_current_generation(store)
    assert changed.value.code == "vertex_restart_required"

    store.write_text(
        '{"generation":"fedcba9876543210fedcba9876543210",'
        '"generation":"0123456789abcdef0123456789abcdef"}',
        encoding="utf-8",
    )
    with pytest.raises(VertexRestartRequired):
        bootstrap.assert_current_generation(store)

    store.unlink()
    with pytest.raises(VertexRestartRequired) as absent:
        bootstrap.assert_current_generation(store)
    assert absent.value.code == "vertex_restart_required"


def test_managed_retirement_event_requests_graceful_uvicorn_exit():
    release = threading.Event()
    server = SimpleNamespace(should_exit=False)
    observed_names = []

    def wait_for_event(name):
        observed_names.append(name)
        assert release.wait(timeout=1)

    listener = start_retirement_listener(
        server,
        rook_managed=True,
        event_waiter=wait_for_event,
    )
    release.set()
    listener.join(timeout=1)

    assert observed_names == [RETIREMENT_EVENT_NAME]
    assert server.should_exit is True
    assert listener.is_alive() is False


def test_standalone_process_does_not_create_or_wait_on_retirement_event():
    server = SimpleNamespace(should_exit=False)

    def forbidden_waiter(_name):
        raise AssertionError("standalone Chirp waited on the managed event")

    assert start_retirement_listener(
        server,
        rook_managed=False,
        event_waiter=forbidden_waiter,
    ) is None
    assert server.should_exit is False
