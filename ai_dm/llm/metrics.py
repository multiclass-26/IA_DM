"""Coleta de métricas de chamadas LLM."""

from __future__ import annotations

import csv
import io
import time
from dataclasses import asdict, dataclass


@dataclass
class LLMMetric:
    ts: str
    provider: str
    model: str
    call_type: str
    elapsed_s: float
    success: bool
    prompt_chars: int
    response_chars: int
    error: str = ""


def record(
    metrics: list[dict],
    *,
    provider: str,
    model: str,
    call_type: str,
    elapsed_s: float,
    success: bool,
    prompt_chars: int = 0,
    response_chars: int = 0,
    error: str = "",
) -> None:
    """Acrescenta uma métrica à lista in-place."""
    m = LLMMetric(
        ts=time.strftime("%Y-%m-%d %H:%M:%S"),
        provider=provider,
        model=model,
        call_type=call_type,
        elapsed_s=round(float(elapsed_s), 3),
        success=bool(success),
        prompt_chars=int(prompt_chars),
        response_chars=int(response_chars),
        error=error or "",
    )
    metrics.append(asdict(m))


def to_csv(metrics: list[dict]) -> str:
    if not metrics:
        return ""
    out = io.StringIO()
    fieldnames = [
        "ts", "provider", "model", "call_type", "elapsed_s",
        "success", "prompt_chars", "response_chars", "error",
    ]
    writer = csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    for m in metrics:
        writer.writerow({k: m.get(k, "") for k in fieldnames})
    return out.getvalue()
