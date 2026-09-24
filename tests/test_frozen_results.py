"""Frozen results and deterministic fallback (docs/plans/2026-09-23-chirp-frozen-results-and-fallback.md).

Every LLM-backed Chirp component carries Freeze/Frozen pins, replays its last
model result when the model is unavailable or when asked, and otherwise degrades
to typed defaults. The adapter refuses a credential-less model at once so the
component never waits on LiteLLM's auth retries.
"""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from chirp.adapter import ChirpAdapter, ModelUnavailable, missing_credential
from chirp.rook_tool import chirp_create
from chirp.server import app

client = TestClient(app)


def _create(**overrides):
    args = dict(
        pins_in=["Brief:string"],
        pins_out=["Span:float", "Bays:int", "Curved:bool", "Material:string"],
        signature="brief -> span, bays, curved, material",
        category="planner",
    )
    args.update(overrides)
    return chirp_create(**args)


class TestUniversalPins:
    def test_llm_components_get_freeze_and_frozen_after_correction(self):
        result = _create()
        names = [p["name"] for p in result["pins_in"]]
        assert names == ["Brief", "Correction", "Freeze", "Frozen"]
        freeze, frozen = result["pins_in"][2], result["pins_in"][3]
        assert freeze["type"] == "bool" and freeze["optional"] is True
        assert frozen["type"] == "string" and frozen["optional"] is True
        assert "travels with the .gh" in frozen["description"]

    def test_deterministic_only_components_carry_neither(self):
        result = _create(deterministic_code='Material = "steel";', deterministic_only=True)
        names = [p["name"] for p in result["pins_in"]]
        assert names == ["Brief", "Correction"]
        assert "Frozen" not in result["script"]

    @pytest.mark.parametrize("name", ["Freeze", "frozen", "FROZEN"])
    def test_reserved_names_are_rejected(self, name):
        with pytest.raises(ValueError, match="reserved"):
            _create(pins_in=["Brief:string", f"{name}:string"])

    def test_run_script_signature_includes_the_new_pins(self):
        script = _create()["script"]
        assert "object Brief, object Correction, object Freeze, object Frozen, ref object Span" in script
        assert "private const int FrozenPinIndex = 3;" in script


class TestGeneratedSolvePaths:
    def test_replay_and_fallback_paths_are_emitted(self):
        script = _create()["script"]
        assert 'mode = "frozen";' in script
        assert 'mode = "frozen-fallback";' in script
        assert 'mode = "defaults";' in script
        assert '"[frozen] "' in script
        assert '"[frozen replay: "' in script
        assert '"[deterministic fallback: "' in script
        assert "inputs changed since capture" in script

    def test_snapshot_is_written_to_the_frozen_pins_persistent_data(self):
        script = _create()["script"]
        assert "TryWriteFrozen(store, slot, BuildEntry(inputsHash, body));" in script
        assert "PersistentData.Clear();" in script
        # GH_String, never GH_ObjectWrapper: the wrapper does not serialise its payload into the .gh.
        assert "PersistentData.Append(new GH_String(updated));" in script
        assert "GH_ObjectWrapper(" not in script
        assert "RefreshPin(param);" in script
        assert "if (param.SourceCount > 0) return;" in script
        assert "using Grasshopper.Kernel.Parameters;" in script
        assert "using Grasshopper.Kernel.Types;" in script

    def test_typed_defaults_per_output_pin(self):
        script = _create()["script"]
        assert "Span = (object)0.0;" in script
        assert "Bays = (object)0;" in script
        assert "Curved = (object)false;" in script
        assert 'Material = (object)"";' in script

    def test_live_and_replay_share_one_reader_path(self):
        script = _create()["script"]
        assert script.count('ReadDouble(result, "span")') == 1
        assert 'body = ExtractObject(entry, "body");' in script

    def test_missing_model_never_throws_but_timeouts_stay_hard_errors(self):
        script = _create()["script"]
        assert "throw new Exception($\"Chirp error" not in script
        # An unreachable adapter is caught inside the call and becomes a fallback...
        assert "catch (HttpRequestException)" in script
        assert "Warn(\"Chirp used deterministic defaults" in script
        # ...while Rook's timeout contract is preserved as hard errors.
        assert 'throw new Exception($"chirp_inference_timeout: {text}");' in script
        assert "chirp_transport_timeout" in script
        assert "catch (TaskCanceledException)" in script

    def test_entries_are_kept_per_list_item(self):
        script = _create()["script"]
        # One aggregate store (a single GH_String) with one entry per iteration.
        assert 'var slot = "i" + Iteration;' in script
        assert "FindEntry(store, slot, inputsHash, out entryMatches)" in script
        assert "TryWriteFrozen(store, slot, BuildEntry(inputsHash, body));" in script
        assert "BuildStore(store, Iteration, entry)" in script
        assert '"count"' in script and '"items"' in script
        # Later iterations read the pin's persistent data, not the solve-start input value.
        assert "goo.PersistentData.AllData(true)" in script
        assert "if (IsLastIteration()) RefreshPin(param);" in script

    def test_freeze_without_a_frozen_result_never_calls_the_model(self):
        script = _create()["script"]
        start = script.index("if (freeze)")
        end = script.index("                try", start)  # the adapter call begins the else branch
        freeze_block = script[start:end]
        assert "Freeze is on and no frozen result exists for this item" in freeze_block
        assert "/chirp/call" not in freeze_block
        assert 'mode = "defaults";' in freeze_block

    def test_deterministic_code_runs_after_every_path(self):
        script = _create(deterministic_code="Bays = (object)(Convert.ToInt32(Bays) * 2);")["script"]
        post = script.index("=== Deterministic post-processing ===")
        assert post > script.index('"[deterministic fallback: "')
        assert post > script.index('"[frozen] "')

    def test_still_no_system_text_json(self):
        script = _create()["script"]
        assert "System.Text.Json" not in script
        assert "JsonSerializer" not in script


class TestCredentialFailFast:
    def test_missing_credential_by_prefix(self):
        with patch.dict(os.environ, {}, clear=False):
            for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENROUTER_API_KEY"):
                os.environ.pop(name, None)
            assert missing_credential("anthropic/claude-opus-5") == "ANTHROPIC_API_KEY is not set for anthropic/claude-opus-5"
            assert missing_credential("openrouter/x/y") == "OPENROUTER_API_KEY is not set for openrouter/x/y"
            assert missing_credential("ollama/llama3") is None
            os.environ["ANTHROPIC_AUTH_TOKEN"] = "token"
            assert missing_credential("anthropic/claude-opus-5") is None

    def test_custom_endpoint_requires_only_its_declared_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("INCEPTION_API_KEY", None)
            cfg = {"api_base": "https://api.inceptionlabs.ai/v1", "api_key_env": "INCEPTION_API_KEY"}
            assert missing_credential("openai/mercury-2", cfg) == "INCEPTION_API_KEY is not set for openai/mercury-2"
            assert missing_credential("openai/local", {"api_base": "http://127.0.0.1:1234/v1"}) is None

    def test_call_raises_model_unavailable_before_any_llm_work(self):
        with patch.dict(os.environ, {}, clear=False):
            for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
                os.environ.pop(name, None)
            os.environ["CHIRP_MODEL"] = "anthropic/claude-opus-5"
            adapter = ChirpAdapter(inference_timeout_seconds=30)
            assert adapter.model_ready() is False
            with patch("chirp.adapter.dspy.ChainOfThought", side_effect=AssertionError("LLM path must not run")):
                with pytest.raises(ModelUnavailable, match="ANTHROPIC_API_KEY is not set"):
                    asyncio.run(adapter.acall("brief -> span", {"brief": "x"}, {"span": "float"}, category="planner", use_cache=False))

    def test_model_ready_when_credential_present(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test", "CHIRP_MODEL": "anthropic/claude-opus-5"}):
            adapter = ChirpAdapter(inference_timeout_seconds=30)
            assert adapter.model_ready() is True
            assert adapter.model_unavailable_reason("openrouter/x/y") is not None


class TestServerContract:
    def test_call_maps_model_unavailable_to_503(self):
        async def unavailable(*_args, **_kwargs):
            raise ModelUnavailable("ANTHROPIC_API_KEY is not set for anthropic/claude-opus-5")

        with patch("chirp.server.adapter.acall", side_effect=unavailable):
            resp = client.post("/chirp/call", json={
                "signature": "brief -> span",
                "inputs": {"brief": "x"},
                "schema": {"span": "float"},
                "category": "planner",
            })
        assert resp.status_code == 503
        assert resp.json() == {"error": "model_unavailable", "details": "ANTHROPIC_API_KEY is not set for anthropic/claude-opus-5"}

    def test_health_model_reports_readiness_from_the_environment_only(self):
        # /health keeps its exact contract (Rook's manager parses it); readiness has
        # its own endpoint, computed from env vars without initialising any model.
        with patch.dict(os.environ, {}, clear=False):
            for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
                os.environ.pop(name, None)
            with patch("chirp.server.adapter", SimpleNamespace(_default_model="anthropic/claude-opus-5")):
                with patch("chirp.adapter.dspy.LM", side_effect=AssertionError("readiness must not initialise models")):
                    data = client.get("/health/model").json()
        assert data == {
            "model": "anthropic/claude-opus-5",
            "model_ready": False,
            "model_reason": "ANTHROPIC_API_KEY is not set for anthropic/claude-opus-5",
        }
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("chirp.server.adapter", SimpleNamespace(_default_model="anthropic/claude-opus-5")):
                assert client.get("/health/model").json()["model_ready"] is True
        assert "model_ready" not in client.get("/health").json()
