"""Memory-only Vertex authorization bootstrap for Rook-managed Chirp."""

from __future__ import annotations

import ctypes
import json
import os
import re
import threading
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import BinaryIO, Callable, Mapping, Sequence


RETIREMENT_EVENT_NAME = r"Local\BringFire.Rook.Chirp.VertexGenerationChanged.v1"
_MAX_BOOTSTRAP_BYTES = 65_536
_SCHEMA_VERSION = 1
_GENERATION = re.compile(r"[0-9a-f]{32}\Z")
_PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]\Z")
_REGION = re.compile(r"(?:global|[a-z][a-z0-9]*(?:-[a-z0-9]+)+)\Z")
_VERTEX_GEMINI_MODEL = re.compile(r"gemini-[a-z0-9][a-z0-9._-]{0,127}\Z")
_BOOTSTRAP_FIELDS = frozenset(
    {
        "schema_version",
        "generation",
        "mode",
        "project_id",
        "region",
        "vertex_credentials",
    }
)
_AUTHORIZED_USER_FIELDS = frozenset(
    {"type", "client_id", "client_secret", "refresh_token"}
)
_UNSUPPORTED_MODEL_MESSAGE = (
    "This release supports only Gemini publisher models on Vertex AI "
    "(vertex_ai/gemini-*)."
)
_RESTART_MESSAGE = "Vertex authorization changed; restart managed Chirp."
_INVALID_BOOTSTRAP_MESSAGE = "Managed Vertex bootstrap is invalid."


class VertexAuthError(RuntimeError):
    """Bounded failure from Chirp's local Vertex authorization boundary."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.public_message = message
        super().__init__(message)


class VertexBootstrapError(VertexAuthError):
    code = "vertex_bootstrap_invalid"

    def __init__(self):
        super().__init__(self.code, _INVALID_BOOTSTRAP_MESSAGE)


class VertexRestartRequired(VertexAuthError):
    code = "vertex_restart_required"

    def __init__(self):
        super().__init__(self.code, _RESTART_MESSAGE)


def _invalid_bootstrap() -> VertexBootstrapError:
    return VertexBootstrapError()


def _authorized_user(value: object) -> Mapping[str, str]:
    if not isinstance(value, dict) or set(value) != _AUTHORIZED_USER_FIELDS:
        raise _invalid_bootstrap()
    if value.get("type") != "authorized_user":
        raise _invalid_bootstrap()
    if any(not isinstance(value[field], str) or not value[field] for field in value):
        raise _invalid_bootstrap()
    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class VertexBootstrap:
    schema_version: int
    generation: str
    mode: str
    project_id: str
    region: str
    vertex_credentials: dict[str, str] | str | None = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise _invalid_bootstrap()
        if not isinstance(self.generation, str) or not _GENERATION.fullmatch(
            self.generation
        ):
            raise _invalid_bootstrap()
        if not isinstance(self.project_id, str) or not _PROJECT_ID.fullmatch(
            self.project_id
        ):
            raise _invalid_bootstrap()
        if not isinstance(self.region, str) or not _REGION.fullmatch(self.region):
            raise _invalid_bootstrap()

        if self.mode == "oauth":
            credentials: object = _authorized_user(self.vertex_credentials)
        elif self.mode == "adc":
            if self.vertex_credentials is not None:
                raise _invalid_bootstrap()
            credentials = None
        elif self.mode == "service_account":
            if not isinstance(self.vertex_credentials, str):
                raise _invalid_bootstrap()
            path = Path(self.vertex_credentials)
            if not path.is_absolute() or not path.is_file():
                raise _invalid_bootstrap()
            credentials = str(path.resolve())
        else:
            raise _invalid_bootstrap()
        object.__setattr__(self, "vertex_credentials", credentials)

    def vertex_kwargs_for_model(self, model: object) -> dict[str, object]:
        publisher_model = vertex_gemini_model_name(model)
        if publisher_model is None:
            return {}
        credentials = self.vertex_credentials
        if isinstance(credentials, Mapping):
            credentials = dict(credentials)
        result: dict[str, object] = {
            "vertex_project": self.project_id,
            "vertex_location": self.region,
        }
        if credentials is not None:
            result["vertex_credentials"] = credentials
        return result

    def assert_current_generation(self, store_path: Path | str | None = None) -> None:
        path = Path(store_path) if store_path is not None else _production_store_path()
        try:
            raw = path.read_text(encoding="utf-8")
            value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
            generation = value.get("generation") if isinstance(value, dict) else None
        except (OSError, UnicodeError, json.JSONDecodeError, VertexBootstrapError):
            raise VertexRestartRequired() from None
        if generation != self.generation:
            raise VertexRestartRequired()


def vertex_gemini_model_name(model: object) -> str | None:
    if not isinstance(model, str) or not model.startswith("vertex_ai/"):
        return None
    publisher_model = model[len("vertex_ai/") :]
    if _VERTEX_GEMINI_MODEL.fullmatch(publisher_model):
        return publisher_model
    raise VertexAuthError("vertex_model_family_unsupported", _UNSUPPORTED_MODEL_MESSAGE)


def _production_store_path() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        raise VertexRestartRequired()
    return Path(local_appdata) / "Rook" / "data" / "provider_auth" / "vertex.json"


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _invalid_bootstrap()
        result[key] = value
    return result


def _parse_bootstrap_line(line: bytes) -> VertexBootstrap:
    try:
        text = line.decode("utf-8")
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except VertexBootstrapError:
        raise
    except (UnicodeError, json.JSONDecodeError):
        raise _invalid_bootstrap() from None
    if not isinstance(payload, dict) or set(payload) != _BOOTSTRAP_FIELDS:
        raise _invalid_bootstrap()
    try:
        return VertexBootstrap(**payload)
    except TypeError:
        raise _invalid_bootstrap() from None


def read_managed_bootstrap(
    argv: Sequence[str],
    stdin: BinaryIO,
) -> tuple[bool, VertexBootstrap | None]:
    allowed = {"--rook-managed", "--rook-vertex-bootstrap-stdin"}
    if any(arg not in allowed for arg in argv):
        raise _invalid_bootstrap()
    if len(set(argv)) != len(argv):
        raise _invalid_bootstrap()
    rook_managed = "--rook-managed" in argv
    reads_bootstrap = "--rook-vertex-bootstrap-stdin" in argv
    if reads_bootstrap and not rook_managed:
        raise _invalid_bootstrap()
    if not reads_bootstrap:
        return rook_managed, None

    line = stdin.readline(_MAX_BOOTSTRAP_BYTES + 2)
    if not isinstance(line, bytes) or not line:
        raise _invalid_bootstrap()
    if line.endswith(b"\n"):
        line = line[:-1]
        if line.endswith(b"\r"):
            line = line[:-1]
    if not line or len(line) > _MAX_BOOTSTRAP_BYTES:
        raise _invalid_bootstrap()
    if stdin.read(1) != b"":
        raise _invalid_bootstrap()
    return True, _parse_bootstrap_line(line)


def _wait_for_retirement_event(name: str) -> None:
    if os.name != "nt":
        raise OSError("managed retirement events require Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateEventW.argtypes = [
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.CreateEventW(None, True, False, name)
    if not handle:
        raise OSError("managed retirement event unavailable")
    try:
        if kernel32.WaitForSingleObject(handle, 0xFFFFFFFF) != 0:
            raise OSError("managed retirement event wait failed")
    finally:
        kernel32.CloseHandle(handle)


def start_retirement_listener(
    server: object,
    *,
    rook_managed: bool,
    event_waiter: Callable[[str], None] | None = None,
) -> threading.Thread | None:
    if not rook_managed:
        return None
    wait = event_waiter or _wait_for_retirement_event

    def retire() -> None:
        try:
            wait(RETIREMENT_EVENT_NAME)
        finally:
            server.should_exit = True

    listener = threading.Thread(
        target=retire,
        name="chirp-managed-retirement",
        daemon=True,
    )
    listener.start()
    return listener
