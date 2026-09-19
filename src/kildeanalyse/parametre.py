"""Eksplisitte kjørevalg. Gamle planer endres aldri når de leses."""
from __future__ import annotations

import math

MODELLER = {"claude_cli": "sonnet", "codex_cli": "gpt-5.6-terra"}
TENKENIVAA = {
    "claude_cli": ("low", "medium", "high", "xhigh", "max"),
    "codex_cli": ("low", "medium", "high", "xhigh", "max", "ultra"),
}
STANDARD_TENKENIVAA = "high"


def normaliser(motor, modell, innstillinger=None, tenkenivaa=None):
    """Brukes bare ved oppretting av ny planversjon, før godkjenning."""
    if innstillinger is not None and not isinstance(innstillinger, dict):
        raise ValueError("Motorinnstillinger må være et JSON-objekt.")
    valg = dict(innstillinger or {})
    if motor == "simulert":
        if tenkenivaa or valg.get("tenkenivaa"):
            raise ValueError("Simulert motor har ikke tenkenivå. Velg en ekte lesemotor.")
        return modell or "simulert", valg
    if motor not in MODELLER:
        raise ValueError("Velg lesemotor: claude_cli eller codex_cli. Simulert brukes bare ved uttrykkelig ønske.")
    modell = (modell or MODELLER[motor]).strip()
    if not modell or any(c.isspace() for c in modell) or modell.startswith("-"):
        raise ValueError("Modell må være et modellnavn eller en modell-ID uten mellomrom.")
    nivaa = tenkenivaa if tenkenivaa is not None else valg.get("tenkenivaa", STANDARD_TENKENIVAA)
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
    return {
        "motor": plan.motor,
        "modell": plan.modell or MODELLER.get(plan.motor, "simulert"),
        "tenkenivaa": plan.motorinnstillinger.get("tenkenivaa") or
            ("low" if plan.motor == "codex_cli" else "ikke fastsatt (eldre plan)" if plan.motor == "claude_cli" else "ikke relevant"),
        "tidsavbrudd_sek": plan.motorinnstillinger.get("tidsavbrudd_sek", 600),
    }
