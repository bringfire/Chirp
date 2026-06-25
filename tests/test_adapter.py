"""Tests for the ChirpAdapter — type coercion and caching (no live LLM)."""

import json
import os
import pytest
from unittest.mock import patch
from chirp.adapter import ChirpAdapter, _load_providers, configure_secure_dspy_cache


class TestCoercion:
    """Test the adapter's type coercion without hitting an LLM."""

    def setup_method(self):
        self.adapter = ChirpAdapter()

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
        self.adapter = ChirpAdapter()

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
    """Test release-safe DSPy cache configuration."""

    def test_uses_chirp_home_cache_dir_and_restricts_pickle(self, tmp_path):
        chirp_home = tmp_path / "chirp"
        expected_cache = chirp_home / "data" / "dspy-cache"
        env = {
            "CHIRP_HOME": str(chirp_home),
            "CHIRP_DSPY_RESTRICT_PICKLE": "1",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("DSPY_CACHEDIR", None)
            with patch("chirp.adapter.dspy.configure_cache", create=True) as configure_cache:
                result = configure_secure_dspy_cache()

        configure_cache.assert_called_once_with(
            enable_disk_cache=True,
            enable_memory_cache=True,
            restrict_pickle=True,
            disk_cache_dir=str(expected_cache),
        )
        assert result["restrict_pickle"] is True
        assert result["disk_cache_dir"] == str(expected_cache)
        assert expected_cache.exists()


class TestGetLm:
    """Test that _get_lm resolves provider config into dspy.LM kwargs."""

    def setup_method(self):
        self.adapter = ChirpAdapter()

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
                    api_base="https://api.inceptionlabs.ai/v1",
                    api_key="test-key-123",
                )
                assert lm == "fake_lm"


class TestDefaultModelProviderRouting:
    """Test that the default model also uses CHIRP_PROVIDERS config."""

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
                    adapter = ChirpAdapter()
                    mock_lm.assert_called_once_with(
                        "openai/mercury-2",
                        api_base="https://api.inceptionlabs.ai/v1",
                        api_key="test-key-456",
                    )
