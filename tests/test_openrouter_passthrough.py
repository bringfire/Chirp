import chirp.adapter as adapter_mod


class _StubLM:
    def __init__(self, model, **kwargs):
        self.model = model
        self.kwargs = kwargs


def test_openrouter_model_passes_through(monkeypatch):
    monkeypatch.setattr(adapter_mod.dspy, "LM", _StubLM)
    monkeypatch.setattr(adapter_mod.dspy, "configure", lambda **kw: None)
    monkeypatch.setenv("CHIRP_MODEL", "openrouter/anthropic/claude-3.7-sonnet")
    monkeypatch.delenv("CHIRP_PROVIDERS", raising=False)

    adapter = adapter_mod.ChirpAdapter()

    # The model string passes through verbatim; no api_key is injected — LiteLLM
    # resolves OPENROUTER_API_KEY itself, and there is no Anthropic-key demand.
    assert adapter._lm.model == "openrouter/anthropic/claude-3.7-sonnet"
    assert "api_key" not in adapter._lm.kwargs
