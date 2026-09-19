"""Motoradaptere. Kontrakt: sjekk_stotte, kjor, avbryt (se base.py)."""
from __future__ import annotations

from .base import Adapter, AdapterFeil
from .simulert import SimulertAdapter
from .claude_cli import ClaudeCliAdapter
from .codex_cli import CodexCliAdapter
from .api import OpenAiApiAdapter, AnthropicApiAdapter, OpenRouterApiAdapter, KompatibelApiAdapter

ADAPTERE: dict[str, type[Adapter]] = {
    SimulertAdapter.navn: SimulertAdapter,
    ClaudeCliAdapter.navn: ClaudeCliAdapter,
    CodexCliAdapter.navn: CodexCliAdapter,
    **{cls.navn: cls for cls in (OpenAiApiAdapter, AnthropicApiAdapter, OpenRouterApiAdapter, KompatibelApiAdapter)},
}


def lag_adapter(navn: str, innstillinger: dict | None = None) -> Adapter:
    try:
        klasse = ADAPTERE[navn]
    except KeyError:
        raise AdapterFeil(f"Ukjent motor «{navn}». Tilgjengelige: {', '.join(ADAPTERE)}.") from None
    return klasse(innstillinger or {})


__all__ = ["Adapter", "AdapterFeil", "SimulertAdapter", "ClaudeCliAdapter", "ADAPTERE", "lag_adapter"]
