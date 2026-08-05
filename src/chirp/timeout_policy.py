from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping

from dotenv import dotenv_values


TIMEOUT_ENV_NAME = "CHIRP_INFERENCE_TIMEOUT_SECONDS"
DEFAULT_INFERENCE_TIMEOUT_SECONDS = 300
MAX_INFERENCE_TIMEOUT_SECONDS = 1800
TRANSPORT_SLACK_SECONDS = 30
ACCEPTANCE_SLACK_SECONDS = 30
GENERATED_CLIENT_TIMEOUT_SECONDS = (
    MAX_INFERENCE_TIMEOUT_SECONDS + TRANSPORT_SLACK_SECONDS
)
ACCEPTANCE_WATCHDOG_SECONDS = (
    GENERATED_CLIENT_TIMEOUT_SECONDS + ACCEPTANCE_SLACK_SECONDS
)
INVALID_TIMEOUT_CODE = "chirp_invalid_inference_timeout"
INVALID_TIMEOUT_MESSAGE = (
    "Chirp is disabled because CHIRP_INFERENCE_TIMEOUT_SECONDS must contain "
    "only ASCII digits and resolve to 1–1800 seconds."
)
_ASCII_WHOLE_SECONDS = re.compile(r"[0-9]+", re.ASCII)
_TIMEOUT_ASSIGNMENT = re.compile(
    rf"^\s*(?:export\s+)?{re.escape(TIMEOUT_ENV_NAME)}\s*="
)


@dataclass(frozen=True)
class InferenceTimeoutPolicy:
    timeout_seconds: int | None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def enabled(self) -> bool:
        return self.timeout_seconds is not None


def canonical_chirp_home(environ: Mapping[str, str] | None = None) -> Path:
    source = os.environ if environ is None else environ
    configured = source.get("CHIRP_HOME")
    return Path(configured) if configured else Path(__file__).resolve().parents[2]


def _invalid_policy() -> InferenceTimeoutPolicy:
    return InferenceTimeoutPolicy(None, INVALID_TIMEOUT_CODE, INVALID_TIMEOUT_MESSAGE)


def _parse_timeout(*, present: bool, raw: str | None) -> InferenceTimeoutPolicy:
    if not present:
        return InferenceTimeoutPolicy(DEFAULT_INFERENCE_TIMEOUT_SECONDS)
    if raw is None or _ASCII_WHOLE_SECONDS.fullmatch(raw) is None:
        return _invalid_policy()
    try:
        seconds = int(raw)
    except ValueError:
        return _invalid_policy()
    if not 1 <= seconds <= MAX_INFERENCE_TIMEOUT_SECONDS:
        return _invalid_policy()
    return InferenceTimeoutPolicy(seconds)


def _read_exact_file_timeout(env_path: Path) -> tuple[bool, str | None]:
    if not env_path.is_file():
        return False, None
    prefix = f"{TIMEOUT_ENV_NAME}="
    values: list[str] = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            values.append(line[len(prefix):])
        elif _TIMEOUT_ASSIGNMENT.match(line):
            return True, None
    if not values:
        return False, None
    if len(values) != 1:
        return True, None
    return True, values[0]


def load_canonical_environment(
    chirp_home: Path | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> Path:
    source = os.environ if environ is None else environ
    home = canonical_chirp_home(source) if chirp_home is None else Path(chirp_home)
    env_path = home / ".env"
    if env_path.is_file():
        for key, value in dotenv_values(env_path).items():
            if key != TIMEOUT_ENV_NAME and value is not None:
                source.setdefault(key, value)
    return env_path


def read_inference_timeout_policy(
    chirp_home: Path | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> InferenceTimeoutPolicy:
    source = os.environ if environ is None else environ
    env_path = load_canonical_environment(chirp_home, source)
    if TIMEOUT_ENV_NAME in source:
        return _parse_timeout(present=True, raw=source[TIMEOUT_ENV_NAME])
    present, raw = _read_exact_file_timeout(env_path)
    return _parse_timeout(present=present, raw=raw)
