"""Tests for the ChirpAdapter — type coercion and caching (no live LLM)."""

import json
import os
import pytest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch
from chirp.adapter import ChirpAdapter, _load_providers, configure_secure_dspy_cache
from chirp.vertex_bootstrap import (
    VertexAuthError,
    VertexBootstrap,
    VertexRestartRequired,
)


VERTEX_MODEL = "vertex_ai/gemini-2.5-pro"
VERTEX_GENERATION = "0123456789abcdef0123456789abcdef"
VERTEX_CREDENTIALS = {
    "type": "authorized_user",
    "client_id": "adapter-client-sentinel",
    "client_secret": "adapter-secret-sentinel",
    "refresh_token": "adapter-refresh-sentinel",
}


def _vertex_bootstrap():
    return VertexBootstrap(
        schema_version=1,
        generation=VERTEX_GENERATION,
        mode="oauth",
        project_id="company-ai-project",
        region="us-central1",
        vertex_credentials=dict(VERTEX_CREDENTIALS),
    )


def _write_vertex_generation(tmp_path):
    path = tmp_path / "Rook" / "data" / "provider_auth" / "vertex.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"generation": VERTEX_GENERATION}),
        encoding="utf-8",
    )
    return path


class TestCoercion:
    """Test the adapter's type coercion without hitting an LLM."""

    def setup_method(self):
        self.adapter = ChirpAdapter(inference_timeout_seconds=300)

    def test_int_coercion(self):
        assert self.adapter._coerce("42", "int") == 42
        assert self.adapter._coerce("42.7", "int") == 42
        assert self.adapter._coerce(42, "int") == 42

    def test_float_coercion(self):
        assert self.adapter._coerce("3.14", "float") == 3.14
        assert self.adapter._coerce(3, "float") == 3.0

    def test_bool_coercion(self):
        assert self.adapter._coerce("true", "bool") is True
        assert self.adapter._coerce("false", "bool") is False
        assert self.adapter._coerce("yes", "bool") is True
        assert self.adapter._coerce("0", "bool") is False

    def test_string_coercion(self):
        assert self.adapter._coerce(42, "string") == "42"
        assert self.adapter._coerce("hello", "string") == "hello"

    def test_bool_not_coerced_as_int(self):
        """bool is a subclass of int in Python — ensure True doesn't pass as int."""
        result = self.adapter._coerce(True, "int")
        assert result == 1
        assert type(result) is int  # not bool

    def test_geometry_type_coercion(self):
        assert self.adapter._coerce("a flat surface", "Surface") == "a flat surface"


class TestCacheKey:
    """Test deterministic cache key generation."""

    def setup_method(self):
        self.adapter = ChirpAdapter(inference_timeout_seconds=300)

    def test_same_inputs_same_key(self):
        k1 = self.adapter._cache_key("a -> b", {"a": 1}, {"b": "int"}, "model-a")
        k2 = self.adapter._cache_key("a -> b", {"a": 1}, {"b": "int"}, "model-a")
        assert k1 == k2

    def test_different_inputs_different_key(self):
        k1 = self.adapter._cache_key("a -> b", {"a": 1}, {"b": "int"}, "model-a")
        k2 = self.adapter._cache_key("a -> b", {"a": 2}, {"b": "int"}, "model-a")
        assert k1 != k2

    def test_different_model_different_key(self):
        k1 = self.adapter._cache_key("a -> b", {"a": 1}, {"b": "int"}, "model-a")
        k2 = self.adapter._cache_key("a -> b", {"a": 1}, {"b": "int"}, "model-b")
        assert k1 != k2


class TestLoadProviders:
    """Test provider config loading from CHIRP_PROVIDERS env var."""

    def test_empty_env(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHIRP_PROVIDERS", None)
            assert _load_providers() == {}

    def test_valid_json(self):
        cfg = '{"openai/mercury-2": {"api_base": "https://api.inceptionlabs.ai/v1", "api_key_env": "INCEPTION_API_KEY"}}'
        with patch.dict(os.environ, {"CHIRP_PROVIDERS": cfg}):
            result = _load_providers()
            assert "openai/mercury-2" in result
            assert result["openai/mercury-2"]["api_base"] == "https://api.inceptionlabs.ai/v1"
            assert result["openai/mercury-2"]["api_key_env"] == "INCEPTION_API_KEY"

    def test_invalid_json_returns_empty(self):
        with patch.dict(os.environ, {"CHIRP_PROVIDERS": "not json"}):
            assert _load_providers() == {}


class TestSecureDspyCache:
    """Test DSPy cache hardening for the Chirp runtime."""

    def test_configure_secure_cache_uses_restricted_pickle(self, tmp_path):
        with patch.dict(os.environ, {"CHIRP_HOME": str(tmp_path)}, clear=False):
            with patch("chirp.adapter.dspy.configure_cache") as configure_cache:
                result = configure_secure_dspy_cache()

        configure_cache.assert_called_once()
        kwargs = configure_cache.call_args.kwargs
        assert kwargs["restrict_pickle"] is True
        assert kwargs["enable_disk_cache"] is True
        assert kwargs["disk_cache_dir"].replace("\\", "/").endswith("data/dspy-cache")
        assert result["restrict_pickle"] is True

    def test_adapter_initialization_configures_secure_cache(self):
        with patch("chirp.adapter.configure_secure_dspy_cache") as configure_cache:
            with patch("chirp.adapter.dspy.LM") as mock_lm:
                with patch("chirp.adapter.dspy.configure"):
                    mock_lm.return_value = "fake_lm"
                    ChirpAdapter(inference_timeout_seconds=300)

        configure_cache.assert_called_once()

    def test_release_mode_fails_if_dspy_lacks_restricted_pickle(self):
        def reject_restrict_pickle(**kwargs):
            if "restrict_pickle" in kwargs:
                raise TypeError("unexpected keyword argument 'restrict_pickle'")

        with patch.dict(os.environ, {"ROOK_MODE": "release"}, clear=False):
            with patch("chirp.adapter.dspy.configure_cache", reject_restrict_pickle):
                with pytest.raises(RuntimeError, match="restrict_pickle"):
                    configure_secure_dspy_cache()


class TestGetLm:
    """Test that _get_lm resolves provider config into dspy.LM kwargs."""

    def setup_method(self):
        self.adapter = ChirpAdapter(inference_timeout_seconds=300)

    def test_default_model_returns_none(self):
        assert self.adapter._get_lm(None) is None
        assert self.adapter._get_lm(self.adapter._default_model) is None

    def test_override_model_creates_lm(self):
        lm = self.adapter._get_lm("anthropic/claude-haiku-4-5-20251001")
        assert lm is not None

    def test_override_model_is_cached(self):
        lm1 = self.adapter._get_lm("anthropic/claude-haiku-4-5-20251001")
        lm2 = self.adapter._get_lm("anthropic/claude-haiku-4-5-20251001")
        assert lm1 is lm2

    def test_provider_config_passes_api_base(self):
        """When CHIRP_PROVIDERS maps a model, _get_lm should pass api_base to dspy.LM."""
        self.adapter._providers = {
            "openai/mercury-2": {
                "api_base": "https://api.inceptionlabs.ai/v1",
                "api_key_env": "INCEPTION_API_KEY",
            }
        }
        with patch.dict(os.environ, {"INCEPTION_API_KEY": "test-key-123"}):
            with patch("chirp.adapter.dspy.LM") as mock_lm:
                mock_lm.return_value = "fake_lm"
                lm = self.adapter._get_lm("openai/mercury-2")
                mock_lm.assert_called_once_with(
                    "openai/mercury-2",
                    timeout=300,
                    api_base="https://api.inceptionlabs.ai/v1",
                    api_key="test-key-123",
                )
                assert lm == "fake_lm"


class TestDefaultModelProviderRouting:
    """Test that the default model also uses CHIRP_PROVIDERS config."""

    @pytest.mark.parametrize(
        "category",
        ["interpreter", "critic", "narrator", "classifier", "gate", "editor"],
    )
    @pytest.mark.asyncio
    async def test_non_planner_calls_use_sonnet_5(self, category):
        class FakeProgram:
            def __init__(self, _signature):
                pass

            async def acall(self, **_inputs):
                return SimpleNamespace(answer="ok", reasoning="done")

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHIRP_MODEL", None)
            with patch("chirp.adapter.dspy.LM") as mock_lm:
                with patch("chirp.adapter.dspy.configure"):
                    adapter = ChirpAdapter(inference_timeout_seconds=300)

                with patch.dict(
                    "chirp.adapter._MODULE_MAP",
                    {"ChainOfThought": FakeProgram, "Predict": FakeProgram},
                ):
                    with patch(
                        "chirp.adapter.dspy.context", return_value=nullcontext()
                    ):
                        result = await adapter.acall(
                            "prompt -> answer",
                            {"prompt": "hello"},
                            {"answer": "string"},
                            category=category,
                            use_cache=False,
                        )

        assert result["model"] == "anthropic/claude-sonnet-5"
        assert [call.args[0] for call in mock_lm.call_args_list] == [
            "anthropic/claude-opus-5",
            "anthropic/claude-sonnet-5",
        ]
        assert [call.kwargs["timeout"] for call in mock_lm.call_args_list] == [300, 300]

    def test_no_override_uses_opus_5(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHIRP_MODEL", None)
            with patch("chirp.adapter.dspy.LM") as mock_lm:
                with patch("chirp.adapter.dspy.configure"):
                    mock_lm.return_value = "fake_lm"
                    adapter = ChirpAdapter(inference_timeout_seconds=300)

        assert adapter._default_model == "anthropic/claude-opus-5"
        mock_lm.assert_called_once_with("anthropic/claude-opus-5", timeout=300)

    def test_default_model_uses_provider_config(self):
        """CHIRP_MODEL=openai/mercury-2 + CHIRP_PROVIDERS should route correctly."""
        providers_json = json.dumps({
            "openai/mercury-2": {
                "api_base": "https://api.inceptionlabs.ai/v1",
                "api_key_env": "INCEPTION_API_KEY",
            }
        })
        with patch.dict(os.environ, {
            "CHIRP_MODEL": "openai/mercury-2",
            "CHIRP_PROVIDERS": providers_json,
            "INCEPTION_API_KEY": "test-key-456",
        }):
            with patch("chirp.adapter.dspy.LM") as mock_lm:
                with patch("chirp.adapter.dspy.configure"):
                    mock_lm.return_value = "fake_lm"
                    adapter = ChirpAdapter(inference_timeout_seconds=300)
                    mock_lm.assert_called_once_with(
                        "openai/mercury-2",
                        timeout=300,
                        api_base="https://api.inceptionlabs.ai/v1",
                        api_key="test-key-456",
                    )


class TestVertexRouting:
    def test_vertex_lm_receives_only_bootstrapped_runtime_arguments(self):
        bootstrap = _vertex_bootstrap()
        with patch("chirp.adapter.dspy.LM") as create_lm:
            with patch("chirp.adapter.dspy.configure"):
                adapter = ChirpAdapter(
                    inference_timeout_seconds=300,
                    vertex_bootstrap=bootstrap,
                )
            create_lm.reset_mock()

            adapter._make_lm(VERTEX_MODEL)

        create_lm.assert_called_once_with(
            VERTEX_MODEL,
            timeout=300,
            vertex_project="company-ai-project",
            vertex_location="us-central1",
            vertex_credentials=VERTEX_CREDENTIALS,
        )

    def test_managed_vertex_lm_requires_bootstrap_and_rejects_partner_family(self):
        adapter = ChirpAdapter(
            inference_timeout_seconds=300,
            rook_managed=True,
        )

        with pytest.raises(VertexAuthError) as signed_out:
            adapter._make_lm(VERTEX_MODEL)
        assert signed_out.value.code == "vertex_signed_out"

        with pytest.raises(VertexAuthError) as unsupported:
            adapter._make_lm("vertex_ai/claude-sonnet")
        assert unsupported.value.code == "vertex_model_family_unsupported"

    def test_standalone_vertex_lm_preserves_litellm_adc_resolution(self):
        adapter = ChirpAdapter(inference_timeout_seconds=300)

        with patch("chirp.adapter.dspy.LM") as create_lm:
            adapter._make_lm(VERTEX_MODEL)

        create_lm.assert_called_once_with(VERTEX_MODEL, timeout=300)

    @pytest.mark.asyncio
    async def test_managed_vertex_inference_without_bootstrap_blocks_provider(self):
        provider_calls = 0

        class FakeProgram:
            def __init__(self, _signature):
                pass

            async def acall(self, **_inputs):
                nonlocal provider_calls
                provider_calls += 1
                return SimpleNamespace(answer="unexpected")

        adapter = ChirpAdapter(
            inference_timeout_seconds=300,
            rook_managed=True,
        )
        with patch.dict("chirp.adapter._MODULE_MAP", {"Predict": FakeProgram}):
            with pytest.raises(VertexAuthError) as error:
                await adapter.acall(
                    "prompt -> answer",
                    {"prompt": "hello"},
                    {"answer": "string"},
                    category="classifier",
                    use_cache=False,
                    model=VERTEX_MODEL,
                )

        assert error.value.code == "vertex_signed_out"
        assert provider_calls == 0

    @pytest.mark.asyncio
    async def test_standalone_vertex_inference_has_no_rook_generation_check(
        self,
        monkeypatch,
        tmp_path,
    ):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        provider_calls = 0

        class FakeProgram:
            def __init__(self, _signature):
                pass

            async def acall(self, **_inputs):
                nonlocal provider_calls
                provider_calls += 1
                return SimpleNamespace(answer="standalone")

        fake_lm = SimpleNamespace(history=[])
        with patch("chirp.adapter.dspy.LM", return_value=fake_lm):
            with patch("chirp.adapter.dspy.configure"):
                adapter = ChirpAdapter(inference_timeout_seconds=300)
        with patch.dict("chirp.adapter._MODULE_MAP", {"Predict": FakeProgram}):
            with patch("chirp.adapter.dspy.context", return_value=nullcontext()):
                result = await adapter.acall(
                    "prompt -> answer",
                    {"prompt": "hello"},
                    {"answer": "string"},
                    category="classifier",
                    use_cache=False,
                    model=VERTEX_MODEL,
                )

        assert provider_calls == 1
        assert result["outputs"] == {"answer": "standalone"}

    def test_vertex_lm_constructor_failure_is_redacted(self):
        adapter = ChirpAdapter(
            inference_timeout_seconds=300,
            vertex_bootstrap=_vertex_bootstrap(),
        )
        with patch("chirp.adapter.dspy.LM") as create_lm:
            create_lm.side_effect = RuntimeError(repr(VERTEX_CREDENTIALS))
            with pytest.raises(VertexAuthError) as error:
                adapter._make_lm(VERTEX_MODEL)

        assert error.value.code == "vertex_request_failed"
        assert "adapter-secret-sentinel" not in str(error.value)
        assert "adapter-refresh-sentinel" not in str(error.value)

    @pytest.mark.asyncio
    async def test_vertex_provider_failure_is_redacted(self, monkeypatch, tmp_path):
        _write_vertex_generation(tmp_path)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

        class FakeProgram:
            def __init__(self, _signature):
                pass

            async def acall(self, **_inputs):
                raise RuntimeError(repr(VERTEX_CREDENTIALS))

        with patch("chirp.adapter.dspy.LM", return_value=SimpleNamespace(history=[])):
            with patch("chirp.adapter.dspy.configure"):
                adapter = ChirpAdapter(
                    inference_timeout_seconds=300,
                    vertex_bootstrap=_vertex_bootstrap(),
                )
        with patch.dict("chirp.adapter._MODULE_MAP", {"Predict": FakeProgram}):
            with patch("chirp.adapter.dspy.context", return_value=nullcontext()):
                with pytest.raises(VertexAuthError) as error:
                    await adapter.acall(
                        "prompt -> answer",
                        {"prompt": "hello"},
                        {"answer": "string"},
                        category="classifier",
                        use_cache=False,
                        model=VERTEX_MODEL,
                    )

        assert error.value.code == "vertex_request_failed"
        assert "adapter-secret-sentinel" not in str(error.value)
        assert "adapter-refresh-sentinel" not in str(error.value)

    @pytest.mark.asyncio
    async def test_stale_generation_blocks_provider_before_inference(
        self,
        monkeypatch,
        tmp_path,
    ):
        store = _write_vertex_generation(tmp_path)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        provider_calls = 0

        class FakeProgram:
            def __init__(self, _signature):
                pass

            async def acall(self, **_inputs):
                nonlocal provider_calls
                provider_calls += 1
                return SimpleNamespace(answer="unexpected")

        with patch("chirp.adapter.dspy.LM") as create_lm:
            with patch("chirp.adapter.dspy.configure"):
                adapter = ChirpAdapter(
                    inference_timeout_seconds=300,
                    vertex_bootstrap=_vertex_bootstrap(),
                )
            create_lm.return_value = "vertex-lm"
            store.unlink()
            with patch.dict("chirp.adapter._MODULE_MAP", {"Predict": FakeProgram}):
                with patch("chirp.adapter.dspy.context", return_value=nullcontext()):
                    with pytest.raises(VertexRestartRequired):
                        await adapter.acall(
                            "prompt -> answer",
                            {"prompt": "hello"},
                            {"answer": "string"},
                            category="classifier",
                            use_cache=False,
                            model=VERTEX_MODEL,
                        )

        assert provider_calls == 0

    @pytest.mark.asyncio
    async def test_stale_generation_blocks_cached_vertex_result(
        self,
        monkeypatch,
        tmp_path,
    ):
        store = _write_vertex_generation(tmp_path)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

        class FakeProgram:
            def __init__(self, _signature):
                pass

            async def acall(self, **_inputs):
                return SimpleNamespace(answer="authorized")

        fake_lm = SimpleNamespace(history=[])
        with patch("chirp.adapter.dspy.LM", return_value=fake_lm):
            with patch("chirp.adapter.dspy.configure"):
                adapter = ChirpAdapter(
                    inference_timeout_seconds=300,
                    vertex_bootstrap=_vertex_bootstrap(),
                )
            with patch.dict("chirp.adapter._MODULE_MAP", {"Predict": FakeProgram}):
                with patch("chirp.adapter.dspy.context", return_value=nullcontext()):
                    result = await adapter.acall(
                        "prompt -> answer",
                        {"prompt": "hello"},
                        {"answer": "string"},
                        category="classifier",
                        use_cache=True,
                        model=VERTEX_MODEL,
                    )
                    assert result["outputs"] == {"answer": "authorized"}
                    store.unlink()
                    with pytest.raises(VertexRestartRequired):
                        await adapter.acall(
                            "prompt -> answer",
                            {"prompt": "hello"},
                            {"answer": "string"},
                            category="classifier",
                            use_cache=True,
                            model=VERTEX_MODEL,
                        )
