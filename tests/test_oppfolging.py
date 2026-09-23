"""Regresjoner funnet ved overtakelse: låsing, kontrollhistorikk og bootstrap."""
import importlib.util
import multiprocessing
import sys
from pathlib import Path

import pytest

from kildeanalyse import tjeneste
from kildeanalyse.kjoring import KoFeil, arbeiderlaas
from kildeanalyse.lager import Lager

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "syntetisk"
spec = importlib.util.spec_from_file_location("bootstrap", ROOT / "bin" / "start_server.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def _hold_lock(path, ready):
    with arbeiderlaas(Path(path)):
        ready.set()
        import time
        time.sleep(30)


def test_laas_avviser_annen_prosess_og_frigis_ved_krasj(tmp_path):
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    proc = ctx.Process(target=_hold_lock, args=(str(tmp_path), ready))
    proc.start()
    try:
        assert ready.wait(10)
        with pytest.raises(KoFeil, match="aktiv arbeider"):
            with arbeiderlaas(tmp_path):
                pytest.fail("En annen prosess holdt allerede låsen")
    finally:
        proc.terminate()
        proc.join(10)
    with arbeiderlaas(tmp_path):
        pass


def test_siste_kontroll_gjelder_etter_ti_registreringer(tmp_path):
    lager = Lager(tmp_path)
    pr = tjeneste.opprett_prosjekt(lager, "Test")
    tjeneste.importer_dokumenter(lager, pr["id"], [str(FIX / "fjordblikk_2025.pdf")])
    an = tjeneste.opprett_analyse(lager, pr["id"], "Test", "EKSEMPEL")
    aid = an["analyse"]["id"]
    kj = tjeneste.legg_til_kjoringer(lager, aid)["nye"][0]["id"]
    tjeneste.godkjenn_plan(lager, aid, "Test")
    tjeneste.start(lager, aid)
    fid = lager.forsok_for_kjoring(kj)[0]["id"]
    for _ in range(9):
        tjeneste.registrer_kontroll(lager, fid, "Test", "godkjent", "Test av rekkefølge")
    tjeneste.registrer_kontroll(lager, fid, "Test", "avvist", "Siste vurdering skal gjelde")
    view = tjeneste.vis_kjoring(Lager(tmp_path), kj)
    assert view["forsok"][0]["review_status"] == "avvist"
    assert len(view["forsok"][0]["kontroller"]) == 10


def test_bootstrap_avbrutt_installering_proves_igjen(tmp_path, monkeypatch):
    root = tmp_path / "plugin"
    (root / "src" / "kildeanalyse").mkdir(parents=True)
    (root / "pyproject.toml").write_text("test")
    data = tmp_path / "data"
    python = data / "venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()  # venv eksisterer, men første pip-installasjon ble avbrutt
    calls = []
    monkeypatch.setattr(bootstrap, "usable", lambda p, source=None: source is None)
    monkeypatch.setattr(bootstrap.subprocess, "run", lambda command, **kw: calls.append(command))
    assert bootstrap.prepare(root, data) == python
    assert len(calls) == 1 and "pip" in calls[0]
    bootstrap.prepare(root, data)
    assert len(calls) == 1
    (root / "src" / "kildeanalyse" / "__init__.py").write_text("# endret kode")
    bootstrap.prepare(root, data)
    assert len(calls) == 2


def test_editable_miljo_aksepteres_bare_for_riktig_kilde(tmp_path):
    assert bootstrap.usable(Path(sys.executable), ROOT / "src")
    assert not bootstrap.usable(Path(sys.executable), tmp_path / "kopiert-plugin" / "src")
