"""Core Chirp adapter — format → LLM call → parse → validate."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import dspy

from chirp.types import build_output_model, resolve_type


# Module selection per category
_MODULE_MAP: dict[str, type] = {
    "ChainOfThought": dspy.ChainOfThought,
    "Predict": dspy.Predict,
}

# Category prompt prefixes — injected into signature instructions
_CATEGORY_PROMPTS: dict[str, str] = {
    "planner": "You are a design planner. Given a brief, determine appropriate parameters.",
    "interpreter": (
        "You are a domain specialist interpreting a design reasoning chain. "
        "If a correction is provided, prioritize it over upstream assumptions "
        "and explain the reconciliation."
    ),
    "critic": (
        "You are a design critic evaluating coherence across disciplines. "
        "Identify contradictions, score overall coherence, and flag conflicts."
    ),
    "narrator": (
        "You are a design narrator. Synthesize the reasoning streams into "
        "a coherent, presentation-ready design statement."
    ),
    "classifier": "Classify the input into the most appropriate category.",
    "gate": "Based on the design reasoning, determine which rules should be active.",
    "editor": (
        "You are a design editor. Reconcile the upstream reasoning with "
        "the human's correction. The correction takes priority. "
        "Explain what changed and why."
    ),
}

# Default DSPy module per category
_CATEGORY_MODULES: dict[str, str] = {
    "planner": "ChainOfThought",
    "interpreter": "ChainOfThought",
    "critic": "ChainOfThought",
    "narrator": "ChainOfThought",
    "classifier": "Predict",
    "gate": "Predict",
    "editor": "ChainOfThought",
}


def _get_chirp_dspy_cache_dir() -> str | None:
    configured = os.environ.get("DSPY_CACHEDIR")
    if configured:
        return configured

    chirp_home = os.environ.get("CHIRP_HOME")
    if chirp_home:
        cache_dir = str(Path(chirp_home) / "data" / "dspy-cache")
        os.environ["DSPY_CACHEDIR"] = cache_dir
        return cache_dir

    rook_data_dir = os.environ.get("ROOK_DATA_DIR")
    if rook_data_dir:
        cache_dir = str(Path(rook_data_dir) / "chirp-dspy-cache")
        os.environ["DSPY_CACHEDIR"] = cache_dir
        return cache_dir

    return None


def configure_secure_dspy_cache() -> dict:
    cache_dir = _get_chirp_dspy_cache_dir()
    require_restricted_pickle = (
        os.environ.get("CHIRP_DSPY_RESTRICT_PICKLE") == "1"
        or os.environ.get("ROOK_MODE") == "release"
    )
    kwargs = {
        "enable_disk_cache": True,
        "enable_memory_cache": True,
        "restrict_pickle": True,
    }
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        kwargs["disk_cache_dir"] = cache_dir

    if not hasattr(dspy, "configure_cache"):
        raise RuntimeError("Installed DSPy does not support secure cache configuration")

    try:
        dspy.configure_cache(**kwargs)
    except TypeError as exc:
        if require_restricted_pickle:
            raise RuntimeError(
                "Installed DSPy does not support restrict_pickle cache configuration"
            ) from exc
        fallback_kwargs = dict(kwargs)
        fallback_kwargs.pop("restrict_pickle", None)
        dspy.configure_cache(**fallback_kwargs)
        kwargs["restrict_pickle"] = False

    if kwargs["restrict_pickle"]:
        os.environ["CHIRP_DSPY_RESTRICT_PICKLE"] = "1"
    else:
        os.environ.pop("CHIRP_DSPY_RESTRICT_PICKLE", None)
    return kwargs


def _load_providers() -> dict[str, dict]:
    """Load provider config from CHIRP_PROVIDERS env var.

    Format: JSON dict mapping model strings to provider config.
    Each value can have:
        api_base:    Base URL for the provider (e.g. "https://api.inceptionlabs.ai/v1")
        api_key_env: Name of the env var holding the API key (e.g. "INCEPTION_API_KEY")

    Example:
        CHIRP_PROVIDERS='{"openai/mercury-2": {"api_base": "https://api.inceptionlabs.ai/v1", "api_key_env": "INCEPTION_API_KEY"}}'
    """
    raw = os.environ.get("CHIRP_PROVIDERS", "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


class ChirpAdapter:
    """Bridge between typed schemas and LLM calls, using DSPy modules."""

    def __init__(self) -> None:
        configure_secure_dspy_cache()
        configured_model = os.environ.get("CHIRP_MODEL")
        self._default_model = configured_model or "anthropic/claude-opus-5"
        self._non_planner_default_model = (
            configured_model or "anthropic/claude-sonnet-5"
        )

        # Provider config: maps model strings to api_base + api_key_env.
        # Loaded from CHIRP_PROVIDERS env var (JSON), e.g.:
        # {"openai/mercury-2": {"api_base": "https://api.inceptionlabs.ai/v1", "api_key_env": "INCEPTION_API_KEY"}}
        self._providers = _load_providers()

        # Create default LM with provider config (so CHIRP_MODEL=openai/mercury-2
        # plus CHIRP_PROVIDERS picks up api_base/api_key on the default path too)
        self._lm = self._make_lm(self._default_model)
        dspy.configure(lm=self._lm)

        # Cache of LM instances keyed by model string (avoid re-init per call)
        self._lm_cache: dict[str, dspy.LM] = {self._default_model: self._lm}

        self._cache_enabled = os.environ.get("CHIRP_CACHE", "true").lower() == "true"
        self._cache: dict[str, dict] = {}

    def _make_lm(self, model: str) -> dspy.LM:
        """Create a dspy.LM with provider config resolved from CHIRP_PROVIDERS."""
        kwargs: dict = {}
        provider_cfg = self._providers.get(model)
        if provider_cfg:
            if "api_base" in provider_cfg:
                kwargs["api_base"] = provider_cfg["api_base"]
            api_key_env = provider_cfg.get("api_key_env")
            if api_key_env:
                api_key = os.environ.get(api_key_env)
                if api_key:
                    kwargs["api_key"] = api_key
        return dspy.LM(model, **kwargs)

    def _get_lm(self, model: str | None) -> dspy.LM | None:
        """Return a dspy.LM for the given model string, or None for default."""
        if not model or model == self._default_model:
            return None  # use default configured LM
        if model not in self._lm_cache:
            self._lm_cache[model] = self._make_lm(model)
        return self._lm_cache[model]

    def call(
        self,
        signature: str,
        inputs: dict,
        schema: dict[str, str],
        *,
        category: str | None = None,
        use_cache: bool | None = None,
        model: str | None = None,
    ) -> dict:
        """Call the LLM with a signature and inputs, return validated typed outputs.

        Args:
            signature: DSPy signature string, e.g. "surface_description, intent -> u_count, v_count"
            inputs: Input values keyed by signature input field names.
            schema: Output field types, e.g. {"u_count": "int", "v_count": "int"}
            category: Component category (planner, interpreter, etc.) — determines
                      DSPy module and prompt strategy.
            use_cache: Override cache behavior for this call.
            model: LiteLLM model string to override the default for this call.
                   E.g. "openai/mercury-2", "anthropic/claude-haiku-4-5-20251001".

        Returns:
            dict with keys:
                outputs: validated output dict matching schema types
                reasoning: LLM reasoning if available
                usage: token usage dict
                cached: whether this was a cache hit
                latency_ms: wall-clock time for the call
                model: the model used for this call
        """
        should_cache = use_cache if use_cache is not None else self._cache_enabled
        cat = (category or "").lower().strip()
        category_default = (
            self._non_planner_default_model
            if cat in _CATEGORY_MODULES and cat != "planner"
            else self._default_model
        )
        effective_model = model or category_default

        # Check cache (model is part of the key — different model = different result)
        if should_cache:
            cache_key = self._cache_key(signature, inputs, schema, effective_model)
            if cache_key in self._cache:
                cached = self._cache[cache_key].copy()
                cached["cached"] = True
                return cached

        start = time.perf_counter()

        # Handle correction — inject as an additional input field
        correction = inputs.pop("correction", None)
        correction_text = str(correction).strip() if correction else ""

        # Build category context — injected as system_context input
        prompt_prefix = _CATEGORY_PROMPTS.get(cat, "")

        # Compose system context from category prompt + correction
        context_parts = []
        if prompt_prefix:
            context_parts.append(prompt_prefix)
        if correction_text:
            context_parts.append(f"HUMAN CORRECTION (takes priority): {correction_text}")

        # If we have context, add it as an input field and extend the signature
        effective_sig = signature
        if context_parts:
            system_context = "\n\n".join(context_parts)
            inputs["system_context"] = system_context
            # Extend signature: add system_context as an input field
            parts = effective_sig.split("->")
            input_part = parts[0].strip()
            output_part = parts[1].strip() if len(parts) > 1 else ""
            effective_sig = f"system_context, {input_part} -> {output_part}"

        # Build typed signature with output types from schema
        typed_sig = self._build_signature(effective_sig, schema)

        # Select DSPy module based on category
        module_name = _CATEGORY_MODULES.get(cat, "ChainOfThought")
        module_cls = _MODULE_MAP.get(module_name, dspy.ChainOfThought)
        predict = module_cls(typed_sig)

        # Per-call model override via dspy.context
        override_lm = self._get_lm(effective_model)
        active_lm = override_lm or self._lm
        if override_lm is not None:
            with dspy.context(lm=override_lm):
                prediction = predict(**inputs)
        else:
            prediction = predict(**inputs)

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Extract and coerce outputs
        outputs = {}
        for field_name, type_str in schema.items():
            raw = getattr(prediction, field_name)
            outputs[field_name] = self._coerce(raw, type_str)

        # Build result
        result = {
            "outputs": outputs,
            "reasoning": getattr(prediction, "reasoning", None),
            "usage": self._get_usage(active_lm),
            "cached": False,
            "latency_ms": round(elapsed_ms, 1),
            "model": effective_model,
        }

        # Store in cache
        if should_cache:
            self._cache[cache_key] = result.copy()

        return result

    def _build_signature(self, signature: str, schema: dict[str, str]) -> str:
        """Build a DSPy signature string with typed output fields.

        Takes the user's signature (e.g. "description, intent -> u_count, v_count")
        and adds type annotations from the schema.
        """
        parts = signature.split("->")
        if len(parts) != 2:
            raise ValueError(f"Signature must contain exactly one '->': {signature!r}")

        input_part = parts[0].strip()
        output_fields = [f.strip() for f in parts[1].split(",")]

        # Add type annotations to output fields
        typed_outputs = []
        for field in output_fields:
            field_name = field.strip()
            if field_name in schema:
                py_type = resolve_type(schema[field_name])
                type_name = py_type.__name__ if hasattr(py_type, '__name__') else str(py_type)
                typed_outputs.append(f"{field_name}: {type_name}")
            else:
                typed_outputs.append(field_name)

        return f"{input_part} -> {', '.join(typed_outputs)}"

    def _coerce(self, value: object, type_str: str) -> object:
        """Coerce a raw LLM output to the target type."""
        target = resolve_type(type_str)
        # bool is a subclass of int in Python — don't let True slip through as an int
        if isinstance(value, target) and not (target is int and isinstance(value, bool)):
            return value
        try:
            if target is int:
                if isinstance(value, bool):
                    return int(value)
                return int(float(str(value)))  # handles "42.0" → 42
            if target is float:
                return float(str(value))
            if target is bool:
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes")
                return bool(value)
            if target is str:
                return str(value)
            # list types
            if hasattr(target, '__origin__') and target.__origin__ is list:
                if isinstance(value, str):
                    value = json.loads(value)
                return [self._coerce(v, type_str[5:-1]) for v in value]
            return target(value)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            raise ValueError(
                f"Cannot coerce {value!r} to {type_str}: {e}"
            ) from e

    def _cache_key(self, signature: str, inputs: dict, schema: dict, model: str) -> str:
        """Deterministic cache key from call parameters."""
        blob = json.dumps(
            {"signature": signature, "inputs": inputs, "schema": schema, "model": model},
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    def _get_usage(self, lm: dspy.LM | None = None) -> dict:
        """Extract token usage from the last LLM call on the given LM instance."""
        try:
            history = (lm or self._lm).history
            if history:
                last = history[-1]
                usage = last.get("usage", {})
                return {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                }
        except Exception:
            pass
        return {"input_tokens": 0, "output_tokens": 0}
