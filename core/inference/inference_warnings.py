"""Per-request inference warnings collected during provider calls."""

from __future__ import annotations

from contextvars import ContextVar

_inference_warnings: ContextVar[list[str]] = ContextVar("inference_warnings", default=[])
_skip_context_enricher: ContextVar[bool] = ContextVar("skip_context_enricher", default=False)


def clear_inference_warnings() -> None:
    _inference_warnings.set([])
    _skip_context_enricher.set(False)


def append_inference_warnings(codes: list[str]) -> None:
    current = list(_inference_warnings.get())
    for code in codes:
        if code not in current:
            current.append(code)
    _inference_warnings.set(current)


def consume_inference_warnings() -> list[str]:
    warnings = list(_inference_warnings.get())
    _inference_warnings.set([])
    _skip_context_enricher.set(False)
    return warnings


def should_skip_context_enricher() -> bool:
    return _skip_context_enricher.get()


def mark_skip_context_enricher() -> None:
    _skip_context_enricher.set(True)
