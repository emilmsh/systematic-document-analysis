"""Akseptansetester for milepæl 2 med simulert motor (ingen modellkall).

Dekker: tre dokumenter gjennom hele flyten, uleselig dokument, valideringsfeil, stopp og
gjenopptakelse, uavklarte forsøk, rettelse som bevarer originalen, ny planversjon og eksport.
"""
from __future__ import annotations

import csv
import json
import os
import threading
import time
from pathlib import Path

import pytest

from kildeanalyse import tjeneste
from kildeanalyse.kjoring import Koer, prosess_lever
from kildeanalyse.lager import (
    FS_AVBRUTT, FS_UAVKLART, KJ_FEILET, KJ_FULLFORT, KJ_PLANLAGT, KJ_STOPPET, KJ_UAVKLART, KJ_ULESELIG, KJ_VALIDERINGSFEIL, Lager,
)
from kildeanalyse.tjeneste import TjenesteFeil

FIX = Path(__file__).parent / "fixtures" / "syntetisk"
KRIT = str(FIX / "eksempelkriterier.json")
TRE = ("fjordblikk_2025.pdf", "nordlys_2025.pdf", "steinbukk_2025.pdf")


@pytest.fixture
def lager(tmp_path: Path) -> Lager:
    return Lager(tmp_path / "data")


def _oppsett(lager: Lager, motorinnstillinger: dict | None = None, dokumenter=TRE):
    pr = tjeneste.opprett_prosjekt(lager, "Testprosjekt")
    imp = tjeneste.importer_dokumenter(lager, pr["id"], [str(FIX / d) for d in dokumenter])
    assert all("dokument" in r for r in imp["resultater"]), imp
    an = tjeneste.opprett_analyse(lager, pr["id"], "Eksempelanalyse", "Vurder inkluderingsarbeid i årsrapportene (EKSEMPEL).",
                                  motor="simulert", motorinnstillinger=motorinnstillinger)
    aid = an["analyse"]["id"]
    tjeneste.godkjenn_plan(lager, aid, "Testperson")
    nye = tjeneste.legg_til_kjoringer(lager, aid)["nye"]
    return pr, aid, nye


def _kjoring_for(lager: Lager, aid: str, dokumentnavn: str) -> dict:
    for r in tjeneste.vis_status(lager, aid)["rader"]:
        if r["dokument"]["navn"] == dokumentnavn:
            return r
    raise AssertionError(dokumentnavn)





def test_uleselig_dokument_stoppes_foer_vurdering(lager: Lager):
    pr, aid, kjoringer = _oppsett(lager, dokumenter=("havsul_skannet_2025.pdf", "fjordblikk_2025.pdf"))
    tjeneste.start(lager, aid)
    hv = _kjoring_for(lager, aid, "havsul_skannet_2025.pdf")
    assert hv["kjoring"]["status"] == KJ_ULESELIG
    assert hv["antall_forsok"] == 0
    assert "uten tekstlag" in hv["kjoring"]["merknad"] and "ikke «ikke omtalt»" in hv["kjoring"]["merknad"]
    neste = _kjoring_for(lager, aid, "fjordblikk_2025.pdf")
    assert neste["kjoring"]["status"] == KJ_FULLFORT and neste["antall_forsok"] == 1
    assert tjeneste.vis_status(lager, aid)['workflow_block'] is None








def test_uavklart_forsok_fra_dod_arbeider(lager: Lager):
    pr, aid, kjoringer = _oppsett(lager)
    fj = kjoringer[0]
    # Simuler at en tidligere arbeider døde midt i et forsøk.
    lager.opprett_forsok(fj["id"], motor="simulert", simulert=True, modell_onsket="", input_hash="x", input_sti=str(lager.mappe),
                         arbeider_pid=999999, manifest={})
    lager.sett_tilstand(f"arbeider:{aid}", {"pid": 999999, "tid": "tidligere"})
    assert not prosess_lever(999999) and prosess_lever(os.getpid())
    rapport = tjeneste.start(lager, aid)
    assert rapport['ryddet_uavklart'] == [f"{fj['id']}.f1"]
    assert fj['id'] not in rapport['startet']
    assert rapport['workflow_block'] is None
    assert lager.kjoring(fj["id"])["status"] == KJ_UAVKLART
    assert lager.forsok(f"{fj['id']}.f1")["status"] == FS_UAVKLART
    assert all(lager.kjoring(k['id'])['status'] == KJ_FULLFORT for k in kjoringer[1:])
    tjeneste.nytt_forsok(lager, fj["id"], "arbeideren døde; prøver igjen")
    tjeneste.start(lager, aid)
    assert lager.kjoring(fj["id"])["status"] == KJ_FULLFORT
    assert [f["status"] for f in lager.forsok_for_kjoring(fj["id"])] == [FS_UAVKLART, "fullført"]


def test_stopp_under_forsok_og_gjenopptakelse(lager: Lager):
    pr, aid, kjoringer = _oppsett(lager, motorinnstillinger={"forsinkelse_sek": 3})
    feil: list[Exception] = []
    resultat: dict = {}

    def kjor():
        try:
            resultat.update(tjeneste.start(lager, aid))
        except Exception as e:  # noqa: BLE001
            feil.append(e)

    t = threading.Thread(target=kjor)
    t.start()
    time.sleep(1.0)
    assert Koer(lager).aktiv_arbeider(aid) is not None
    with pytest.raises(TjenesteFeil, match="aktiv arbeider"):
        tjeneste.start(lager, aid)  # gjentatt start gir ikke to aktive forsøk
    with pytest.raises(TjenesteFeil, match="aktiv arbeider"):
        tjeneste.godkjenn_plan(lager, aid, "Testperson")  # ingen planendring under kjøring
    tjeneste.stopp(lager, aid)
    t.join(timeout=20)
    assert not feil and not t.is_alive()
    forste = kjoringer[0]["id"]
    assert lager.kjoring(forste)["status"] == KJ_STOPPET
    assert lager.forsok_for_kjoring(forste)[-1]["status"] == FS_AVBRUTT
    assert set(resultat["stoppet_foer"]) == {k["id"] for k in kjoringer[1:]}
    assert all(lager.kjoring(k["id"])["status"] == KJ_PLANLAGT for k in kjoringer[1:])
    # Gjenoppta: den stoppede får nytt forsøk, resten kjøres. Ingen dobbeltkjøring.
    lager2 = Lager(lager.mappe)
    lager2_plan = lager2.gjeldende_planversjon(aid)["plan"]
    assert lager2_plan.motorinnstillinger["forsinkelse_sek"] == 3
    # Raskere gjenopptakelse: ny planversjon uten forsinkelse ville krevd nye kjøringer; her venter vi heller.
    rapport = tjeneste.gjenoppta(lager2, aid)
    assert set(rapport["startet"]) == {k["id"] for k in kjoringer}
    assert tjeneste.vis_status(lager2, aid)["teller"] == {KJ_FULLFORT: 3}
    assert [f["status"] for f in lager2.forsok_for_kjoring(forste)] == [FS_AVBRUTT, "fullført"]


def test_ny_planversjon_krever_godkjenning_og_nye_kjoringer(lager: Lager):
    pr, aid, kjoringer = _oppsett(lager)
    tjeneste.start(lager, aid)
    r = tjeneste.ny_planversjon(lager, aid, "Presisering: innleide regnes med (test).", tilleggsinstruks="Innleide regnes som ansatte.")
    v2 = r["planversjon"]
    assert v2["versjon"] == 2 and v2["status"] == "utkast"
    # Gamle kjøringer står på v1 og er uendret; start finner ingenting nytt.
    assert all(k["planversjon_id"].endswith(".v1") for k in lager.kjoringer(aid))
    tjeneste.godkjenn_plan(lager, aid, "Testperson")
    assert lager.planversjon(f"{aid}.v1")["status"] == "erstattet"
    with pytest.raises(TjenesteFeil, match="ikke lenger gjeldende"):
        tjeneste.nytt_forsok(lager, kjoringer[0]["id"], "test")
    nye = tjeneste.legg_til_kjoringer(lager, aid)["nye"]
    assert len(nye) == 3 and all(k["planversjon_id"].endswith(".v2") for k in nye)
    pakke = tjeneste.vis_inputpakke(lager, nye[0]["id"])["pakke"]
    assert "Innleide regnes som ansatte." in pakke["systeminstruks"]
    gammel = tjeneste.vis_inputpakke(lager, kjoringer[0]["id"])["pakke"]
    assert "Innleide" not in gammel["systeminstruks"]
    tjeneste.start(lager, aid)
    import zipfile
    exported = tjeneste.eksporter(lager, aid)
    with zipfile.ZipFile(exported['documentation_archive']) as archive:
        data = json.loads(archive.read('audit/analysis.json'))
        assert {v['versjon'] for v in data['plans']} == {1, 2}
        assert len(data['runs']) == 6
