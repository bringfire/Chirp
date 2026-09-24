import os
from pathlib import Path

import pytest

from chirp.timeout_policy import (
    DEFAULT_INFERENCE_TIMEOUT_SECONDS,
    INVALID_TIMEOUT_CODE,
    INVALID_TIMEOUT_MESSAGE,
    load_canonical_environment,
    read_inference_timeout_policy,
)


@pytest.mark.parametrize("raw", ["1", "300", "1800"])
def test_valid_timeout_values_are_accepted(monkeypatch, tmp_path: Path, raw):
    monkeypatch.setenv("CHIRP_INFERENCE_TIMEOUT_SECONDS", raw)
    policy = read_inference_timeout_policy(tmp_path)
    assert policy.timeout_seconds == int(raw)
    assert policy.error_code is None
    assert policy.error_message is None


@pytest.mark.parametrize(
    "raw",
    ["", "0", "1801", "-1", "+300", "300.0", "3e2", "300s", " 300", "300 ", "٣٠٠", "9" * 5000],
)
def test_invalid_timeout_values_disable_chirp(monkeypatch, tmp_path: Path, raw):
    monkeypatch.setenv("CHIRP_INFERENCE_TIMEOUT_SECONDS", raw)
    policy = read_inference_timeout_policy(tmp_path)
    assert policy.timeout_seconds is None
    assert policy.error_code == INVALID_TIMEOUT_CODE
    assert policy.error_message == INVALID_TIMEOUT_MESSAGE


def test_absence_uses_builtin_default(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("CHIRP_INFERENCE_TIMEOUT_SECONDS", raising=False)
    policy = read_inference_timeout_policy(tmp_path)
    assert policy.timeout_seconds == DEFAULT_INFERENCE_TIMEOUT_SECONDS == 300
    assert policy.error_code is None


def test_process_environment_wins_over_canonical_env(monkeypatch, tmp_path: Path):
    (tmp_path / ".env").write_text(
        "CHIRP_INFERENCE_TIMEOUT_SECONDS=600\n", encoding="utf-8"
    )
    monkeypatch.setenv("CHIRP_INFERENCE_TIMEOUT_SECONDS", "900")
    assert read_inference_timeout_policy(tmp_path).timeout_seconds == 900


def test_present_invalid_process_value_does_not_fall_through(monkeypatch, tmp_path: Path):
    (tmp_path / ".env").write_text(
        "CHIRP_INFERENCE_TIMEOUT_SECONDS=600\n", encoding="utf-8"
    )
    monkeypatch.setenv("CHIRP_INFERENCE_TIMEOUT_SECONDS", "bad")
    assert read_inference_timeout_policy(tmp_path).error_code == INVALID_TIMEOUT_CODE


@pytest.mark.parametrize("raw", ["", " 300", "300 ", '"300"', "300 # seconds"])
def test_canonical_env_timeout_is_not_normalized(monkeypatch, tmp_path: Path, raw):
    monkeypatch.delenv("CHIRP_INFERENCE_TIMEOUT_SECONDS", raising=False)
    (tmp_path / ".env").write_text(
        f"CHIRP_INFERENCE_TIMEOUT_SECONDS={raw}\n", encoding="utf-8"
    )
    assert read_inference_timeout_policy(tmp_path).error_code == INVALID_TIMEOUT_CODE


def test_load_canonical_environment_skips_timeout_normalization(monkeypatch, tmp_path: Path):
    environ: dict[str, str] = {}
    (tmp_path / ".env").write_text(
        "CHIRP_MODEL=openai/example\nCHIRP_INFERENCE_TIMEOUT_SECONDS= 300\n",
        encoding="utf-8",
    )
    assert load_canonical_environment(tmp_path, environ) == tmp_path / ".env"
    assert environ == {"CHIRP_MODEL": "openai/example"}


def test_policy_is_immutable_after_startup(monkeypatch, tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("CHIRP_INFERENCE_TIMEOUT_SECONDS=600\n", encoding="utf-8")
    monkeypatch.delenv("CHIRP_INFERENCE_TIMEOUT_SECONDS", raising=False)
    policy = read_inference_timeout_policy(tmp_path)
    env_path.write_text("CHIRP_INFERENCE_TIMEOUT_SECONDS=900\n", encoding="utf-8")
    assert policy.timeout_seconds == 600


def test_canonical_env_does_not_follow_working_directory(monkeypatch, tmp_path: Path):
    chirp_home = tmp_path / "chirp-home"
    other = tmp_path / "other"
    chirp_home.mkdir()
    other.mkdir()
    (chirp_home / ".env").write_text(
        "CHIRP_INFERENCE_TIMEOUT_SECONDS=600\n", encoding="utf-8"
    )
    (other / ".env").write_text(
        "CHIRP_INFERENCE_TIMEOUT_SECONDS=900\n", encoding="utf-8"
    )
    monkeypatch.delenv("CHIRP_INFERENCE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.chdir(other)
    assert read_inference_timeout_policy(chirp_home).timeout_seconds == 600


def test_python_floor_and_timeout_primitive_remain_python_310_compatible():
    root = Path(__file__).resolve().parents[1]
    assert 'requires-python = ">=3.10"' in (root / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    active_source = "\n".join(
        (root / relative).read_text(encoding="utf-8")
        for relative in (
            "src/chirp/server.py",
            "src/chirp/adapter.py",
            "src/chirp/__main__.py",
        )
    )
    assert "asyncio.timeout" not in active_source
    assert active_source.count("timeout_graceful_shutdown=30") == 2
