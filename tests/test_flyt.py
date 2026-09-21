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
    an = tjeneste.opprett_analyse(lager, pr["id"], "Eksempelanalyse", "Vurder inkluderingsarbeid i årsrapportene (EKSEMPEL).", KRIT,
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


def test_tre_dokumenter_gjennom_hele_flyten(lager: Lager):
    pr, aid, kjoringer = _oppsett(lager)
    assert len(kjoringer) == 3
    rapport = tjeneste.start(lager, aid)
    assert rapport["simulert"] is True and len(rapport["startet"]) == 3
    status = tjeneste.vis_status(lager, aid)
    assert status["teller"] == {KJ_FULLFORT: 3}
    assert status["aktiv_arbeider"] is None

    fj = _kjoring_for(lager, aid, "fjordblikk_2025.pdf")
    vis = tjeneste.vis_kjoring(lager, fj["kjoring"]["id"])
    f = vis["forsok"][-1]
    assert f["forsok"]["simulert"] is True and f["forsok"]["status"] == "fullført"
    vurd = f["vurderinger"]
    assert (vurd["K1"]["svar"], vurd["K2"]["svar"], vurd["K3"]["svar"]) == ("ja", "5", "ja")
    assert vurd["K2"]["belegg"][0]["side"] == 2  # fysisk side, ikke trykt «Side 4»
    assert all(v["kontrollstatus"] == "ikke kontrollert" for v in vurd.values())
    assert f["validering"]["gyldig"] and f["validering"]["lesedekning"]["fullstendig"]
    assert f["manifest"]["input_hash"] == f["forsok"]["input_hash"]

    st = _kjoring_for(lager, aid, "steinbukk_2025.pdf")
    vurd_st = tjeneste.vis_kjoring(lager, st["kjoring"]["id"])["forsok"][-1]["vurderinger"]
    assert vurd_st["K1"]["svar"] == "ikke_omtalt" and vurd_st["K2"]["svar"] == "ikke_oppgitt"

    # Registrert kontekst: inputpakken inneholder bare eget dokument, og norske tegn er intakte.
    for r in status["rader"]:
        pakke = tjeneste.vis_inputpakke(lager, r["kjoring"]["id"])["pakke"]
        eget = r["dokument"]["navn"].split("_")[0].capitalize()
        for annet in {"Fjordblikk", "Nordlys", "Steinbukk"} - {eget}:
            assert annet not in pakke["brukermelding"]
        assert "[Fysisk side 1]" in pakke["brukermelding"]
        lagret = json.loads((Path(r["siste_forsok"]["input_sti"]) / "input.json").read_text(encoding="utf-8"))
        assert lagret["brukermelding"] == pakke["brukermelding"]
    fj_pakke = tjeneste.vis_inputpakke(lager, fj["kjoring"]["id"])["pakke"]
    assert "ønsker å være" in fj_pakke["brukermelding"]

    eks = tjeneste.eksporter(lager, aid, legacy_format=True)
    mappe = Path(eks["mappe"])
    for navn in ("resultater.csv", "belegg.csv", "forsok.csv", "kontroll.csv", "LESMEG.md", "plan.md", "resultater.json"):
        assert (mappe / navn).is_file(), navn
    assert "SIMULERTE" in (mappe / "LESMEG.md").read_text(encoding="utf-8")
    assert eks["kontrollert_av_totalt"] == "0/9"
    with open(mappe / "resultater.csv", encoding="utf-8-sig", newline="") as fh:
        rader = list(csv.DictReader(fh, delimiter=";"))
    assert len(rader) == 3 and all(r["simulert"] == "JA" for r in rader)
    assert all(r["K1_kontroll"] == "ikke kontrollert" for r in rader)
    assert (mappe / "forsok" / f["forsok"]["id"] / "input.json").is_file()


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


def test_valideringsfeil_og_ugyldig_svar(lager: Lager):
    scen = {"scenarier": {"fjordblikk_2025.pdf": "oppdiktet_sitat", "nordlys_2025.pdf": "feil_side", "steinbukk_2025.pdf": "ugyldig_svar"}}
    pr, aid, _ = _oppsett(lager, motorinnstillinger=scen)
    tjeneste.start(lager, aid)
    fj = _kjoring_for(lager, aid, "fjordblikk_2025.pdf")
    assert fj["kjoring"]["status"] == KJ_VALIDERINGSFEIL
    val = tjeneste.vis_kjoring(lager, fj["kjoring"]["id"])["forsok"][-1]["validering"]
    assert any("finnes ikke i dokumentteksten" in e["melding"] for e in val["feil"])
    no = _kjoring_for(lager, aid, "nordlys_2025.pdf")
    assert no["kjoring"]["status"] == KJ_VALIDERINGSFEIL
    val_no = tjeneste.vis_kjoring(lager, no["kjoring"]["id"])["forsok"][-1]["validering"]
    assert any("men på side" in e["melding"] for e in val_no["feil"])
    st = _kjoring_for(lager, aid, "steinbukk_2025.pdf")
    assert st["kjoring"]["status"] == KJ_FEILET
    assert st["siste_forsok"]["raasvar"].startswith("Dette er ikke JSON")  # råsvar bevart
    # Svar med valideringsfeil kan ikke godkjennes uendret.
    fid = fj["siste_forsok"]["id"]
    with pytest.raises(TjenesteFeil, match="Kan ikke godkjennes uendret"):
        tjeneste.registrer_kontroll(lager, fid, "Testperson", "godkjent", "ser riktig ut")
    # Rettelse med ekte sitat godtas; deretter kan forsøket godkjennes.
    tjeneste.registrer_kontroll(lager, fid, "Testperson", "rettet", "erstatter oppdiktet sitat", kriterium_id="K1", nytt_svar="ja",
                                nytt_belegg=[{"side": 2, "sitat": "I 2025 hadde vi fem personer i arbeidstrening gjennom et samarbeid med NAV Vestland."}])
    tjeneste.registrer_kontroll(lager, fid, "Testperson", "rettet", "erstatter oppdiktet sitat", kriterium_id="K2", nytt_svar="5",
                                nytt_belegg=[{"side": 2, "sitat": "fem personer i arbeidstrening"}])
    tjeneste.registrer_kontroll(lager, fid, "Testperson", "rettet", "erstatter oppdiktet sitat", kriterium_id="K3", nytt_svar="ja",
                                nytt_belegg=[{"side": 2, "sitat": "samarbeid med NAV Vestland"}])
    r = tjeneste.registrer_kontroll(lager, fid, "Testperson", "godkjent", "kontrollert mot kilden")
    assert all(v["kontrollstatus"] == "godkjent" and v["kilde"] == "rettet" for v in r["vurderinger"].values())
    # Nytt forsøk for det feilede: gammelt forsøk beholdes, nytt får ny ID.
    tjeneste.nytt_forsok(lager, st["kjoring"]["id"], "prøver igjen etter motorfeil")
    tjeneste.start(lager, aid)  # steinbukk feiler igjen (samme scenario) men får forsøk nr 2
    forsok = lager.forsok_for_kjoring(st["kjoring"]["id"])
    assert [f["nr"] for f in forsok] == [1, 2] and forsok[0]["status"] == "feilet"


def test_rettelse_bevarer_original_og_overlever_omstart(lager: Lager, tmp_path: Path):
    pr, aid, _ = _oppsett(lager)
    tjeneste.start(lager, aid)
    fj = _kjoring_for(lager, aid, "fjordblikk_2025.pdf")
    fid = fj["siste_forsok"]["id"]
    with pytest.raises(TjenesteFeil, match="finnes ikke på kildeenhet"):
        tjeneste.registrer_kontroll(lager, fid, "Testperson", "rettet", "test", kriterium_id="K2", nytt_svar="4",
                                    nytt_belegg=[{"side": 2, "sitat": "Dette sitatet er oppdiktet av testen."}])
    with pytest.raises(TjenesteFeil, match="krever belegg"):
        tjeneste.registrer_kontroll(lager, fid, "Testperson", "rettet", "test", kriterium_id="K2", nytt_svar="4")
    r = tjeneste.registrer_kontroll(lager, fid, "Testperson", "rettet", "to ble ansatt, teller bare disse (test)", kriterium_id="K2",
                                    nytt_svar="2", nytt_belegg=[{"side": 2, "sitat": "To av dem ble ansatt i faste stillinger etter endt periode."}])
    assert r["vurderinger"]["K2"]["svar"] == "2" and r["vurderinger"]["K2"]["kilde"] == "rettet"
    assert r["vurderinger"]["K1"]["kontrollstatus"] == "ikke kontrollert"
    # Originalen er bevart i forsøket og i kontrollposten.
    lager2 = Lager(lager.mappe)  # «omstart»
    forsok = lager2.forsok(fid)
    original = json.loads(forsok["svar_json"])
    assert next(v for v in original["vurderinger"] if v["kriterium_id"] == "K2")["svar"] == "5"
    ko = lager2.kontroller(fid)[0]
    assert ko["opprinnelig"]["svar"] == "5" and ko["nytt"]["svar"] == "2" and ko["ansvarlig"] == "Testperson"
    # Nytt forsøk arver ikke godkjenning/rettelse.
    tjeneste.registrer_kontroll(lager2, fid, "Testperson", "godkjent", "resten stemmer")
    tjeneste.nytt_forsok(lager2, fj["kjoring"]["id"], "teknisk gjentakelse")
    tjeneste.start(lager2, aid)
    nytt = lager2.forsok_for_kjoring(fj["kjoring"]["id"])[-1]
    assert nytt["id"].endswith(".f2")
    vurd = tjeneste.vis_kjoring(lager2, fj["kjoring"]["id"])["forsok"][-1]["vurderinger"]
    assert all(v["kontrollstatus"] == "ikke kontrollert" for v in vurd.values())
    eks = tjeneste.eksporter(lager2, aid, legacy_format=True)
    assert eks["kontrollert_av_totalt"] == "0/9"  # gjeldende forsøk er det nye, ukontrollerte


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
    eks = tjeneste.eksporter(lager, aid, legacy_format=True)
    assert eks["antall_kjoringer"] == 6
    assert "blandede versjoner" in (Path(eks["mappe"]) / "LESMEG.md").read_text(encoding="utf-8")


def test_instruksjonsforsok_i_kilde_paavirker_ikke_simulert(lager: Lager):
    pr, aid, _ = _oppsett(lager, dokumenter=("granitt_2025.pdf",))
    tjeneste.start(lager, aid)
    gr = _kjoring_for(lager, aid, "granitt_2025.pdf")
    vurd = tjeneste.vis_kjoring(lager, gr["kjoring"]["id"])["forsok"][-1]["vurderinger"]
    assert vurd["K2"]["svar"] == "2"
    raa = gr["siste_forsok"]["raasvar"]
    assert "999" not in raa and "KANARI-DOK-7712" not in raa
