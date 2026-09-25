"""Samtidige kjøringer: godkjent tak, lavere valg ved start, stopp og lås per analyse."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from kildeanalyse import tjeneste
from kildeanalyse.adaptere.simulert import SimulertAdapter
from kildeanalyse.english_tools import register
from kildeanalyse.kjoring import Koer
from kildeanalyse.lager import FS_AVBRUTT, KJ_FULLFORT, KJ_PLANLAGT, KJ_STOPPET, Lager
from kildeanalyse.parametre import normaliser
from kildeanalyse.tjeneste import TjenesteFeil

FIX = Path(__file__).parent / "fixtures" / "syntetisk"
TRE = ("fjordblikk_2025.pdf", "nordlys_2025.pdf", "steinbukk_2025.pdf")


def _analyse(lager, prosjekt_id, motorinnstillinger=None):
    an = tjeneste.opprett_analyse(lager, prosjekt_id, "Samtidighet", "Vurder rapporten (EKSEMPEL).",
                                  motor="simulert", motorinnstillinger=motorinnstillinger)
    aid = an["analyse"]["id"]
    tjeneste.godkjenn_plan(lager, aid, "Testperson")
    return aid, tjeneste.legg_til_kjoringer(lager, aid)["nye"]


def _oppsett(tmp_path, motorinnstillinger=None):
    lager = Lager(tmp_path / "data")
    pr = tjeneste.opprett_prosjekt(lager, "Samtidighet")
    tjeneste.importer_dokumenter(lager, pr["id"], [str(FIX / d) for d in TRE])
    return (lager, pr["id"], *_analyse(lager, pr["id"], motorinnstillinger))


def _maal(monkeypatch, parter=0):
    """Tell samtidige leserkall. De første `parter` kallene må møtes, ellers feiler de."""
    original = SimulertAdapter.kjor
    laas = threading.Lock()
    tilstand = {"aktive": 0, "topp": 0, "kall": 0}
    barriere = threading.Barrier(parter, timeout=10) if parter else None

    def kjor(self, *args):
        with laas:
            tilstand["aktive"] += 1
            tilstand["topp"] = max(tilstand["topp"], tilstand["aktive"])
            nr = tilstand["kall"]
            tilstand["kall"] += 1
        try:
            if barriere and nr < parter:
                barriere.wait()
            else:
                time.sleep(0.05)
            return original(self, *args)
        finally:
            with laas:
                tilstand["aktive"] -= 1

    monkeypatch.setattr(SimulertAdapter, "kjor", kjor)
    return tilstand


def _vent_paa(betingelse, sekunder=10):
    slutt = time.monotonic() + sekunder
    while time.monotonic() < slutt:
        if betingelse():
            return True
        time.sleep(0.05)
    return False


def test_standard_er_en_kjoring_om_gangen(tmp_path, monkeypatch):
    lager, _, aid, kjoringer = _oppsett(tmp_path)
    assert lager.gjeldende_planversjon(aid)["plan"].motorinnstillinger["maks_samtidige"] == 1
    maaling = _maal(monkeypatch)
    rapport = tjeneste.start(lager, aid)
    assert maaling["topp"] == 1 and rapport["samtidige"] == 1
    assert list(rapport["utfall"]) == [k["id"] for k in kjoringer]


def test_godkjent_tak_kjorer_filer_samtidig(tmp_path, monkeypatch):
    lager, _, aid, kjoringer = _oppsett(tmp_path, {"maks_samtidige": 2})
    maaling = _maal(monkeypatch, parter=2)  # Går bare hvis to filer faktisk kjører samtidig.
    rapport = tjeneste.start(lager, aid)
    assert maaling["topp"] == 2 and maaling["kall"] == 3
    assert rapport["samtidige"] == 2 and rapport["run_issues"] == []
    assert list(rapport["utfall"]) == [k["id"] for k in kjoringer]
    assert all(lager.kjoring(k["id"])["status"] == KJ_FULLFORT for k in kjoringer)
    # Hver kjøring har ett eget forsøk; ingen fil ble sendt to ganger.
    assert [len(lager.forsok_for_kjoring(k["id"])) for k in kjoringer] == [1, 1, 1]


def test_start_kan_senke_men_ikke_heve_taket(tmp_path, monkeypatch):
    lager, _, aid, kjoringer = _oppsett(tmp_path, {"maks_samtidige": 2})
    maaling = _maal(monkeypatch)
    with pytest.raises(TjenesteFeil, match="approved maximum of 2"):
        tjeneste.start_i_bakgrunnen(lager, aid, samtidige=3)
    assert maaling["kall"] == 0
    assert Koer(lager).blokkering(aid)["code"] == "CONCURRENCY_NOT_APPROVED"
    rapport = tjeneste.start(lager, aid, samtidige=1)
    assert maaling["topp"] == 1 and rapport["samtidige"] == 1
    assert rapport["workflow_block"] is None
    assert all(lager.kjoring(k["id"])["status"] == KJ_FULLFORT for k in kjoringer)


@pytest.mark.parametrize("verdi", [0, 17, True, "2", 2.0])
def test_ugyldig_tak_avvises(verdi):
    with pytest.raises(ValueError, match="max_concurrent_runs"):
        normaliser("simulert", "", {"maks_samtidige": verdi})


def test_stopp_avbryter_alle_aktive_og_bevarer_resten(tmp_path):
    lager, _, aid, kjoringer = _oppsett(tmp_path, {"maks_samtidige": 2, "forsinkelse_sek": 5})
    resultat, feil = {}, []

    def kjor():
        try:
            resultat.update(tjeneste.start(lager, aid))
        except Exception as e:  # noqa: BLE001
            feil.append(e)

    t = threading.Thread(target=kjor)
    t.start()
    assert _vent_paa(lambda: len(lager.aktive_forsok(aid)) == 2)
    tjeneste.stopp(lager, aid)
    t.join(timeout=20)
    assert not feil and not t.is_alive()
    for kj in kjoringer[:2]:
        assert lager.kjoring(kj["id"])["status"] == KJ_STOPPET
        assert lager.forsok_for_kjoring(kj["id"])[-1]["status"] == FS_AVBRUTT
    assert resultat["stoppet_foer"] == [kjoringer[2]["id"]]
    assert lager.kjoring(kjoringer[2]["id"])["status"] == KJ_PLANLAGT
    assert lager.aktive_forsok(aid) == []


def test_ulike_analyser_kjorer_side_om_side(tmp_path):
    lager, prosjekt_id, treg, _ = _oppsett(tmp_path, {"forsinkelse_sek": 5})
    rask, raske = _analyse(lager, prosjekt_id)
    t = threading.Thread(target=lambda: tjeneste.start(lager, treg))
    t.start()
    try:
        assert _vent_paa(lambda: Koer(lager).aktiv_arbeider(treg) is not None)
        with pytest.raises(TjenesteFeil, match="aktiv arbeider"):
            tjeneste.start(lager, treg)  # Samme analyse kan fortsatt ikke startes to ganger.
        rapport = tjeneste.start(lager, rask)
        assert set(rapport["utfall"].values()) == {KJ_FULLFORT}
        assert Koer(lager).aktiv_arbeider(treg) is not None
    finally:
        tjeneste.stopp(lager, treg)
        t.join(timeout=20)
    assert not t.is_alive()
    assert all(lager.kjoring(k["id"])["status"] == KJ_FULLFORT for k in raske)


def test_engelske_verktoy_viser_tak_og_valg(tmp_path):
    store = Lager(tmp_path / "data")
    functions = {}

    class Server:
        def tool(self, **kwargs):
            def decorator(fn):
                functions[fn.__name__] = fn
                return fn
            return decorator

    register(Server(), lambda: store)

    def call(tool, **kwargs):
        return json.loads(functions[tool](**kwargs))

    project = call("create_project", name="Concurrency")
    call("import_documents", project_id=project["id"], paths=[str(FIX / d) for d in TRE])
    aid = call("create_analysis", project_id=project["id"], name="Concurrency", request="Read the report",
               engine="simulert", language="en", engine_settings={"max_concurrent_runs": 3})["analysis"]["id"]
    plan = call("show_plan", analysis_id=aid)
    assert plan["versions"][0]["plan"]["engine_settings"]["max_concurrent_runs"] == 3
    call("approve_plan", analysis_id=aid, approved_by="Reader")
    call("add_runs", analysis_id=aid)
    assert "approved maximum of 3" in call("start_runs", analysis_id=aid, concurrent_runs=4)["details"]
    started = call("start_runs", analysis_id=aid, concurrent_runs=2)
    assert started["concurrent_runs"] == 2 and started["max_concurrent_runs"] == 3
    tjeneste._traader[aid].join(timeout=20)
    status = call("show_status", analysis_id=aid)
    assert status["gjeldende_plan"]["reader_settings"]["max_concurrent_runs"] == 3
    assert status["teller"] == {KJ_FULLFORT: 3}
    assert status["bakgrunnsresultat"]["concurrent_runs"] == 2 and "error" not in status["bakgrunnsresultat"]
