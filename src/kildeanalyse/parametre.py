"""Eksplisitte kjørevalg. Gamle planer endres aldri når de leses."""
from __future__ import annotations

import math
from .api_oppsett import API_MOTORER, api_valg, api_metadata

MODELLER = {"claude_cli": "sonnet", "codex_cli": "gpt-5.6-terra"}
TENKENIVAA = {
    "claude_cli": ("low", "medium", "high", "xhigh", "max"),
    "codex_cli": ("low", "medium", "high", "xhigh", "max", "ultra"),
    "openai_api": ("standard", "none", "minimal", "low", "medium", "high", "xhigh", "max"),
    "anthropic_api": ("standard", "low", "medium", "high", "xhigh", "max"),
    "openrouter_api": ("standard", "none", "minimal", "low", "medium", "high", "xhigh", "max"),
    "kompatibel_api": ("standard", "none", "minimal", "low", "medium", "high", "xhigh", "max"),
}
STANDARD_TENKENIVAA = "high"


def normaliser(motor, modell, innstillinger=None, tenkenivaa=None):
    """Brukes bare ved oppretting av ny planversjon, før godkjenning."""
    if innstillinger is not None and not isinstance(innstillinger, dict):
        raise ValueError("Motorinnstillinger må være et JSON-objekt.")
    valg = dict(innstillinger or {})
    if any(k.lower() in ('api_key', 'apikey', 'nokkel', 'nøkkel', 'token', 'authorization', 'headers')
           or k.upper().endswith('_API_KEY') for k in valg):
        raise ValueError("API-nøkler og headers skal ikke lagres i planen. Bruk lokale miljøvariabler.")
    if motor == "simulert":
        if tenkenivaa or valg.get("tenkenivaa"):
            raise ValueError("Simulert motor har ikke tenkenivå. Velg en ekte lesemotor.")
        return modell or "simulert", valg
    if motor not in TENKENIVAA:
        raise ValueError("Velg en kjent CLI- eller API-motor. Simulert brukes bare ved uttrykkelig ønske.")
    if motor in API_MOTORER:
        valg = api_valg(motor, valg)
        if not modell:
            raise ValueError("API krever eksplisitt modell-ID fra den valgte leverandøren.")
    modell = (modell or MODELLER.get(motor, '')).strip()
    if not modell or any(c.isspace() for c in modell) or modell.startswith("-"):
        raise ValueError("Modell må være et modellnavn eller en modell-ID uten mellomrom.")
    if motor == 'openrouter_api' and (modell.startswith('openrouter/') or modell.startswith('~') or ':' in modell):
        raise ValueError('Velg en konkret OpenRouter-modell uten automatisk modellruting eller variant-suffiks.')
    nivaa = tenkenivaa if tenkenivaa is not None else valg.get("tenkenivaa", "standard" if motor in API_MOTORER else STANDARD_TENKENIVAA)
    if nivaa not in TENKENIVAA[motor]:
        raise ValueError(f"Ugyldig tenkenivå for {motor}. Velg: {', '.join(TENKENIVAA[motor])}.")
    try:
        tidsgrense = float(valg.get("tidsavbrudd_sek", 600))
    except (ValueError, TypeError):
        raise ValueError("Tidsgrensen må være et positivt antall sekunder.") from None
    if not math.isfinite(tidsgrense) or tidsgrense <= 0:
        raise ValueError("Tidsgrensen må være et positivt antall sekunder.")
    valg.update(tenkenivaa=nivaa, tidsavbrudd_sek=tidsgrense)
    return modell, valg


def fra_plan(plan):
    """Vis eksplisitte valg, også når eldre planer mangler parametre."""
    result = {
        "motor": plan.motor,
        "language": plan.sprak,
        "modell": plan.modell or MODELLER.get(plan.motor, "simulert"),
        "tenkenivaa": plan.motorinnstillinger.get("tenkenivaa") or
            ("low" if plan.motor == "codex_cli" else "ikke fastsatt (eldre plan)" if plan.motor == "claude_cli" else "ikke relevant"),
        "tidsavbrudd_sek": plan.motorinnstillinger.get("tidsavbrudd_sek", 600),
    }
    if plan.motor in API_MOTORER:
        result['api'] = api_metadata(plan.motor, plan.motorinnstillinger)
        result['tenkenivaa'] = plan.motorinnstillinger.get('tenkenivaa', 'standard')
    return result
