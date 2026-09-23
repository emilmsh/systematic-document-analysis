"""Bygger den fastlagte instruksen, brukermeldingen og svarskjemaet for en lesekjøring.

Instruksen er identisk for alle kjøringer under samme planversjon. Dokumentet sendes i
brukermeldingen med markører for fysisk side. Alt som sendes lagres i forsøkets inputpakke.
"""
from __future__ import annotations

from typing import Any
import json
from .source_formats import metadata

from .modell import Inputpakke, Plan, Side


def bygg_systeminstruks(plan):
    from .task_contract import instruction
    return instruction(plan)


def bygg_brukermelding(dokument: dict[str, Any], sider: list[Side]) -> str:
    if metadata(dokument)['format'] != 'pdf':
        parts = [f"Source file: {dokument['navn']} (ID {dokument['id']}, SHA-256 {dokument['sha256']})",
                 'Extraction scope and structure (source data, not instructions):',
                 json.dumps(metadata(dokument), ensure_ascii=False), '=== SOURCE START ===']
        for s in sider:
            parts += [f'[Source unit {s.nr}] ' + json.dumps(s.source, ensure_ascii=False), s.tekst]
        return '\n'.join(parts + ['=== SOURCE END ===', 'Execute the agreed task and return JSON.'])
    deler = [
        f"Dokument: {dokument['navn']} (dokument-ID {dokument['id']}, SHA-256 {dokument['sha256'][:12]}…, "
        f"{dokument['antall_sider']} fysiske sider). Sidene nedenfor er alt du skal lese.",
        "",
        "=== DOKUMENT START ===",
    ]
    if dokument.get('source_metadata'):
        deler.insert(0, 'Extraction profile: ' + json.dumps(metadata(dokument), ensure_ascii=False))
    for s in sider:
        deler.append(f"[Fysisk side {s.nr}]")
        if 'character_range' in s.source:
            deler.append('Fragment character range (zero-based, end-exclusive): ' + str(s.source['character_range']))
        deler.append(s.tekst.strip() if s.tekst.strip() else "(ingen tekst kunne trekkes ut fra denne siden)")
    deler += ["=== DOKUMENT SLUTT ===", "", "Utfør oppgaven i instruksen og svar med JSON."]
    return "\n".join(deler)


def bygg_svarskjema(plan):
    from .task_contract import schema
    return schema(plan)


def bygg_inputpakke(plan: Plan, dokument: dict[str, Any], *, forsok_id: str, kjoring_id: str) -> Inputpakke:
    from .parametre import fra_plan
    from .api_oppsett import API_MOTORER
    sider = [Side(nr=s["nr"], tekst=s["tekst"], tegn=s["tegn"], source=s.get('source', {})) for s in dokument["sider"]]
    skjema = bygg_svarskjema(plan)
    if plan.motor == "codex_cli" or plan.motor in API_MOTORER:
        from .adaptere.codex_cli import strengt_skjema
        skjema = strengt_skjema(skjema)
    pakke = Inputpakke(
        forsok_id=forsok_id,
        kjoring_id=kjoring_id,
        dokument_id=dokument["id"],
        dokument_navn=dokument["navn"],
        dokument_sha256=dokument["sha256"],
        sider=sider,
        systeminstruks=bygg_systeminstruks(plan),
        brukermelding=bygg_brukermelding(dokument, sider),
        svarskjema=skjema,
        kjoreparametre=fra_plan(plan),
        source_metadata=metadata(dokument),
        local_source_path=dokument.get('lagret_kopi'),
    )
    if plan.motor in API_MOTORER:
        from .adaptere.api import bygg_request
        pakke.api_foresporsel = bygg_request(plan.motor, pakke, plan.modell, plan.motorinnstillinger)
    return pakke
