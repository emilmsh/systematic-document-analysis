"""Validering av motorsvar mot plan og bevart dokumenttekst.

Appen kontrollerer at svaret følger skjemaet, at svarene er tillatte, at belegg finnes der
det kreves, og at hvert sitat faktisk står på oppgitt kildeenhet. Mennesket vurderer om
sitatet støtter konklusjonen.
"""
from __future__ import annotations

from typing import Any

from .dokument import finn_sitat_side, sitat_finnes, belegg_finnes, sider_uten_tekst
from .modell import Plan
from .source_formats import metadata

MIN_SITATLENGDE = 10


def valider(plan: Plan, dokument: dict[str, Any], svar: Any, sider_sendt: list[int]) -> dict[str, Any]:
    if plan.is_task:
        from .task_contract import validate
        return validate(plan, dokument, svar, sider_sendt)
    feil: list[dict[str, Any]] = []
    advarsler: list[dict[str, Any]] = []
    if metadata(dokument)['format'] != 'pdf':
        advarsler.append({'type':'extraction_scope', 'melding':'Coverage refers to extracted source units only. Inspect source_metadata for omitted content and missing/stale formula values.'})
    per_kriterium: dict[str, dict[str, Any]] = {k.id: {"gyldig": True, "feil": []} for k in plan.kriterier}

    def legg_feil(kriterium_id: str | None, type: str, melding: str) -> None:
        feil.append({"kriterium_id": kriterium_id, "type": type, "melding": melding})
        if kriterium_id in per_kriterium:
            per_kriterium[kriterium_id]["gyldig"] = False
            per_kriterium[kriterium_id]["feil"].append(melding)

    sidetekst = {s["nr"]: s["tekst"] for s in dokument["sider"]}
    enheter = {s['nr']:s for s in dokument['sider']}
    alle_sider = [s["nr"] for s in dokument["sider"]]

    if not isinstance(svar, dict):
        legg_feil(None, "skjema", "Svaret er ikke et JSON-objekt.")
        return _resultat(False, feil, advarsler, per_kriterium, sider_sendt, [], alle_sider)

    vurderinger = svar.get("vurderinger")
    if not isinstance(vurderinger, list):
        legg_feil(None, "skjema", "Feltet «vurderinger» mangler eller er ikke en liste.")
        vurderinger = []

    sider_lest = svar.get("sider_lest")
    if not isinstance(sider_lest, list) or not all(isinstance(n, int) for n in sider_lest):
        legg_feil(None, "skjema", "Feltet «sider_lest» mangler eller inneholder ikke bare heltall.")
        sider_lest = []
    lesedekning_fullstendig = set(sider_lest) == set(sider_sendt) == set(alle_sider) and not sider_uten_tekst(dokument)

    sett: dict[str, int] = {}
    for v in vurderinger:
        if not isinstance(v, dict):
            legg_feil(None, "skjema", "En vurdering er ikke et objekt.")
            continue
        kid = str(v.get("kriterium_id", ""))
        sett[kid] = sett.get(kid, 0) + 1
        krit = plan.kriterium(kid)
        if krit is None:
            legg_feil(None, "skjema", f"Ukjent kriterium «{kid}» i svaret.")
            continue
        svaret = str(v.get("svar", "")).strip()
        if not krit.svar_er_tillatt(svaret):
            legg_feil(kid, "svar", f"Svaret «{svaret}» er ikke blant tillatte svar ({', '.join(krit.tillatte_svar)}).")
        belegg = v.get("belegg")
        if not isinstance(belegg, list):
            legg_feil(kid, "skjema", "Feltet «belegg» er ikke en liste.")
            belegg = []
        if krit.krever_belegg(svaret) and not belegg:
            legg_feil(kid, "belegg", f"Svaret «{svaret}» krever minst ett sitat med side.")
        if svaret in ("ikke_omtalt", "ikke_oppgitt", "not_mentioned", "not_reported") and not lesedekning_fullstendig:
            legg_feil(kid, "lesedekning", f"Svaret «{svaret}» krever fullstendig lesedekning; sider_lest dekker ikke alle sendte sider.")
        for b in belegg:
            if not isinstance(b, dict):
                legg_feil(kid, "belegg", "Et belegg er ikke et objekt med side og sitat.")
                continue
            side = b.get("side")
            sitat = str(b.get("sitat", "")).strip()
            if not isinstance(side, int) or side not in sidetekst:
                legg_feil(kid, "belegg", f"Ugyldig kildeenhet «{side}»; dokumentet har sidene {alle_sider[0]}–{alle_sider[-1]}.")
                continue
            minimum = 1 if enheter[side].get('source') else MIN_SITATLENGDE
            if len(sitat) < minimum:
                legg_feil(kid, "belegg", f"Sitatet «{sitat}» er for kort til å kontrolleres (minst {MIN_SITATLENGDE} tegn).")
                continue
            if not belegg_finnes(sitat, enheter[side]):
                annen = finn_sitat_side(sitat, dokument["sider"])
                if annen is not None:
                    legg_feil(kid, "belegg", f"Sitatet «{sitat[:60]}…» finnes ikke på kildeenhet {side}, men på side {annen}.")
                else:
                    legg_feil(kid, "belegg", f"Sitatet «{sitat[:60]}…» finnes ikke i dokumentteksten.")
    for k in plan.kriterier:
        if sett.get(k.id, 0) == 0:
            legg_feil(k.id, "skjema", f"Kriterium {k.id} er ikke besvart.")
        elif sett[k.id] > 1:
            legg_feil(k.id, "skjema", f"Kriterium {k.id} er besvart {sett[k.id]} ganger.")
    if not lesedekning_fullstendig:
        advarsler.append({"type": "lesedekning", "melding": "Lesedekningen er ikke fullstendig."})
    merknader = svar.get("merknader")
    if isinstance(merknader, list) and merknader:
        advarsler.append({"type": "merknader", "melding": "Motoren la ved merknader: " + " | ".join(str(m) for m in merknader)})

    result = _resultat(not feil, feil, advarsler, per_kriterium, sider_sendt, sider_lest, alle_sider)
    result['lesedekning']['fullstendig'] = lesedekning_fullstendig
    return result


def _resultat(gyldig: bool, feil: list, advarsler: list, per_kriterium: dict, sider_sendt: list[int],
              sider_lest: list[int], alle_sider: list[int]) -> dict[str, Any]:
    return {
        "gyldig": gyldig,
        "feil": feil,
        "advarsler": advarsler,
        "per_kriterium": per_kriterium,
        "lesedekning": {
            "sider_i_dokument": alle_sider,
            "sider_sendt": sider_sendt,
            "sider_lest_oppgitt": sorted(set(sider_lest)),
            "fullstendig": set(sider_lest) >= set(sider_sendt) and set(sider_sendt) >= set(alle_sider),
        },
    }
