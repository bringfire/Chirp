"""Trace logging — JSONL file per call for observability."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


class TraceLogger:
    """Logs each adapter call as a JSONL line."""

    def __init__(self) -> None:
        trace_dir = os.environ.get("CHIRP_TRACE_DIR", "./traces")
        self._trace_dir = Path(trace_dir)
        self._trace_dir.mkdir(parents=True, exist_ok=True)
        self._file = self._trace_dir / f"chirp_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"

    def log(
        self,
        *,
        signature: str,
        inputs: dict,
        schema: dict,
        outputs: dict | None,
        error: str | None,
        latency_ms: float,
        usage: dict,
        cache_hit: bool,
        model: str | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signature": signature,
            "inputs": inputs,
            "schema": schema,
            "outputs": outputs,
            "error": error,
            "latency_ms": round(latency_ms, 1),
            "usage": usage,
            "cache_hit": cache_hit,
            "model": model,
        }
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
