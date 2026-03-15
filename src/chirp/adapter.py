"""Core Chirp adapter — format → LLM call → parse → validate."""

from __future__ import annotations

import hashlib
import json
import os
import time

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


class ChirpAdapter:
    """Bridge between typed schemas and LLM calls, using DSPy modules."""

    def __init__(self) -> None:
        model = os.environ.get("CHIRP_MODEL", "anthropic/claude-sonnet-4-20250514")
        self._lm = dspy.LM(model)
        dspy.configure(lm=self._lm)

        self._cache_enabled = os.environ.get("CHIRP_CACHE", "true").lower() == "true"
        self._cache: dict[str, dict] = {}

    def call(
        self,
        signature: str,
        inputs: dict,
        schema: dict[str, str],
        *,
        category: str | None = None,
        use_cache: bool | None = None,
    ) -> dict:
        """Call the LLM with a signature and inputs, return validated typed outputs.

        Args:
            signature: DSPy signature string, e.g. "surface_description, intent -> u_count, v_count"
            inputs: Input values keyed by signature input field names.
            schema: Output field types, e.g. {"u_count": "int", "v_count": "int"}
            category: Component category (planner, interpreter, etc.) — determines
                      DSPy module and prompt strategy.
            use_cache: Override cache behavior for this call.

        Returns:
            dict with keys:
                outputs: validated output dict matching schema types
                reasoning: LLM reasoning if available
                usage: token usage dict
                cached: whether this was a cache hit
                latency_ms: wall-clock time for the call
        """
        should_cache = use_cache if use_cache is not None else self._cache_enabled

        # Check cache
        if should_cache:
            cache_key = self._cache_key(signature, inputs, schema)
            if cache_key in self._cache:
                cached = self._cache[cache_key].copy()
                cached["cached"] = True
                return cached

        start = time.perf_counter()

        # Handle correction — inject as an additional input field
        correction = inputs.pop("correction", None)
        correction_text = str(correction).strip() if correction else ""

        # Build category context — injected as system_context input
        cat = (category or "").lower().strip()
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
            "usage": self._get_usage(),
            "cached": False,
            "latency_ms": round(elapsed_ms, 1),
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

    def _cache_key(self, signature: str, inputs: dict, schema: dict) -> str:
        """Deterministic cache key from call parameters."""
        blob = json.dumps(
            {"signature": signature, "inputs": inputs, "schema": schema},
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    def _get_usage(self) -> dict:
        """Extract token usage from the last LLM call."""
        try:
            history = self._lm.history
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
