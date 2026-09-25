"""Varig lagring i SQLite. Én fil per datamappe.

Alle skriveoperasjoner skjer i eksplisitte transaksjoner (BEGIN IMMEDIATE), slik at
resultat, validering og status lagres samlet. Én tilkobling per operasjon; WAL-modus
gjør at flere prosesser (MCP-server, terminal) kan lese samtidig.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from .modell import Plan

SKJEMA = """
CREATE TABLE IF NOT EXISTS prosjekt (
  id TEXT PRIMARY KEY, navn TEXT NOT NULL, opprettet TEXT NOT NULL, directory TEXT
);
CREATE TABLE IF NOT EXISTS dokument (
  id TEXT PRIMARY KEY, prosjekt_id TEXT NOT NULL REFERENCES prosjekt(id),
  navn TEXT NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL, antall_sider INTEGER NOT NULL,
  lesbarhet TEXT NOT NULL, sider_json TEXT NOT NULL, kilde_opphav TEXT NOT NULL,
  importert TEXT NOT NULL, uttrekk_metode TEXT NOT NULL, lagret_kopi TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS analyse (
  id TEXT PRIMARY KEY, prosjekt_id TEXT NOT NULL REFERENCES prosjekt(id),
  navn TEXT NOT NULL, opprettet TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS planversjon (
  id TEXT PRIMARY KEY, analyse_id TEXT NOT NULL REFERENCES analyse(id), versjon INTEGER NOT NULL,
  opprettet TEXT NOT NULL, oppgavetekst TEXT NOT NULL, plan_json TEXT NOT NULL,
  status TEXT NOT NULL, godkjent_av TEXT, godkjent TEXT, endringsnotat TEXT
);
CREATE TABLE IF NOT EXISTS kjoring (
  id TEXT PRIMARY KEY, analyse_id TEXT NOT NULL REFERENCES analyse(id),
  planversjon_id TEXT NOT NULL REFERENCES planversjon(id), dokument_id TEXT NOT NULL REFERENCES dokument(id),
  status TEXT NOT NULL, opprettet TEXT NOT NULL, gjeldende_forsok_id TEXT, merknad TEXT
);
CREATE TABLE IF NOT EXISTS forsok (
  id TEXT PRIMARY KEY, kjoring_id TEXT NOT NULL REFERENCES kjoring(id), nr INTEGER NOT NULL,
  status TEXT NOT NULL, startet TEXT NOT NULL, avsluttet TEXT, arbeider_pid INTEGER,
  motor TEXT NOT NULL, simulert INTEGER NOT NULL, modell_onsket TEXT, modell_rapportert TEXT, sesjon_id TEXT,
  input_hash TEXT NOT NULL, input_sti TEXT NOT NULL, raasvar TEXT, svar_json TEXT, validering_json TEXT,
  feil TEXT, forbruk_json TEXT, manifest_json TEXT
);
CREATE TABLE IF NOT EXISTS kontroll (
  id TEXT PRIMARY KEY, forsok_id TEXT NOT NULL REFERENCES forsok(id), tid TEXT NOT NULL,
  ansvarlig TEXT NOT NULL, handling TEXT NOT NULL,
  opprinnelig_json TEXT, nytt_json TEXT, begrunnelse TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hendelse (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tid TEXT NOT NULL, type TEXT NOT NULL,
  analyse_id TEXT, kjoring_id TEXT, forsok_id TEXT, detaljer_json TEXT
);
CREATE TABLE IF NOT EXISTS tilstand (nokkel TEXT PRIMARY KEY, verdi TEXT);
CREATE TABLE IF NOT EXISTS teller (navn TEXT PRIMARY KEY, verdi INTEGER NOT NULL);
"""

# Statusverdier (holdes her så alle moduler bruker samme ord)
PLAN_UTKAST, PLAN_GODKJENT, PLAN_ERSTATTET = "utkast", "godkjent", "erstattet"
KJ_PLANLAGT, KJ_AKTIV, KJ_FULLFORT, KJ_VALIDERINGSFEIL = "planlagt", "aktiv", "fullført", "valideringsfeil"
KJ_FEILET, KJ_STOPPET, KJ_UAVKLART, KJ_ULESELIG = "feilet", "stoppet", "uavklart", "stoppet_uleselig"
FS_AKTIV, FS_FULLFORT, FS_VALIDERINGSFEIL = "aktiv", "fullført", "valideringsfeil"
FS_FEILET, FS_AVBRUTT, FS_UAVKLART = "feilet", "avbrutt", "uavklart"
KONTROLL_GODKJENT, KONTROLL_RETTET, KONTROLL_AVVIST = "godkjent", "rettet", "avvist"


def naa() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _rad(rad: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(rad) if rad is not None else None


def _rader(rader: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rader]


class LagerFeil(Exception):
    pass


class Lager:
    def __init__(self, mappe: Path):
        self.mappe = Path(mappe)
        self.mappe.mkdir(parents=True, exist_ok=True)
        self.db = self.mappe / "kildeanalyse.sqlite"
        con = self._con()
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(SKJEMA)
            con.commit()
        finally:
            con.close()

    # --- grunnleggende -------------------------------------------------------------

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db, timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @contextmanager
    def transaksjon(self) -> Iterator[sqlite3.Connection]:
        con = self._con()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    @contextmanager
    def lesing(self) -> Iterator[sqlite3.Connection]:
        con = self._con()
        try:
            yield con
        finally:
            con.close()

    def neste_id(self, con: sqlite3.Connection, prefiks: str) -> str:
        con.execute("INSERT INTO teller(navn, verdi) VALUES (?, 0) ON CONFLICT(navn) DO NOTHING", (prefiks,))
        con.execute("UPDATE teller SET verdi = verdi + 1 WHERE navn = ?", (prefiks,))
        verdi = con.execute("SELECT verdi FROM teller WHERE navn = ?", (prefiks,)).fetchone()[0]
        return f"{prefiks}{verdi}"

    def _hent(self, tabell: str, id: str) -> dict[str, Any]:
        with self.lesing() as con:
            rad = _rad(con.execute(f"SELECT * FROM {tabell} WHERE id = ?", (id,)).fetchone())
        if rad is None:
            raise LagerFeil(f"Fant ingen {tabell} med ID «{id}».")
        return rad

    def _oppdater(self, con: sqlite3.Connection, tabell: str, id: str, **felter: Any) -> None:
        if not felter:
            return
        sett = ", ".join(f"{k} = ?" for k in felter)
        con.execute(f"UPDATE {tabell} SET {sett} WHERE id = ?", (*felter.values(), id))

    # --- prosjekt og dokument -------------------------------------------------------

    def opprett_prosjekt(self, navn: str) -> dict[str, Any]:
        with self.transaksjon() as con:
            id = self.neste_id(con, "pr")
            con.execute("INSERT INTO prosjekt(id, navn, opprettet) VALUES (?, ?, ?)", (id, navn, naa()))
        return self.prosjekt(id)

    def sett_prosjektmappe(self, id: str, directory: str) -> dict[str, Any]:
        self.prosjekt(id)
        with self.transaksjon() as con:
            self._oppdater(con, 'prosjekt', id, directory=directory)
        return self.prosjekt(id)

    def prosjekt(self, id: str) -> dict[str, Any]:
        return self._hent("prosjekt", id)

    def prosjekter(self) -> list[dict[str, Any]]:
        with self.lesing() as con:
            return _rader(con.execute("SELECT * FROM prosjekt ORDER BY opprettet").fetchall())

    def finn_dokument_sha(self, prosjekt_id: str, sha256: str, suffix: str | None = None) -> dict[str, Any] | None:
        with self.lesing() as con:
            rows = _rader(con.execute("SELECT * FROM dokument WHERE prosjekt_id = ? AND sha256 = ?", (prosjekt_id, sha256)).fetchall())
            return next((row for row in rows if suffix is None or Path(row['lagret_kopi']).suffix.lower() == suffix.lower()), None)

    def legg_til_dokument(self, prosjekt_id: str, **felter: Any) -> dict[str, Any]:
        self.prosjekt(prosjekt_id)
        with self.transaksjon() as con:
            id = self.neste_id(con, "dok")
            con.execute(
                "INSERT INTO dokument(id, prosjekt_id, navn, sha256, bytes, antall_sider, lesbarhet, sider_json,"
                " kilde_opphav, importert, uttrekk_metode, lagret_kopi, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    id, prosjekt_id, felter["navn"], felter["sha256"], felter["bytes"], felter["antall_sider"],
                    felter["lesbarhet"], json.dumps(felter["sider"], ensure_ascii=False), felter["kilde_opphav"],
                    naa(), felter["uttrekk_metode"], felter["lagret_kopi"], json.dumps(felter.get('source_metadata', {}), ensure_ascii=False),
                ),
            )
        return self.dokument(id)

    def dokument(self, id: str) -> dict[str, Any]:
        d = self._hent("dokument", id)
        d["sider"] = json.loads(d.pop("sider_json"))
        d['source_metadata'] = json.loads(d.pop('metadata_json', '{}'))
        return d

    def dokumenter(self, prosjekt_id: str) -> list[dict[str, Any]]:
        with self.lesing() as con:
            rader = _rader(con.execute("SELECT * FROM dokument WHERE prosjekt_id = ? ORDER BY id", (prosjekt_id,)).fetchall())
        for d in rader:
            d["sider"] = json.loads(d.pop("sider_json"))
            d['source_metadata'] = json.loads(d.pop('metadata_json', '{}'))
        return rader

    def oppdater_dokumentmetadata(self, id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        self.dokument(id)
        with self.transaksjon() as con:
            self._oppdater(con, 'dokument', id, metadata_json=json.dumps(metadata, ensure_ascii=False))
        return self.dokument(id)

    # --- analyse og plan -----------------------------------------------------------

    def opprett_analyse(self, prosjekt_id: str, navn: str) -> dict[str, Any]:
        self.prosjekt(prosjekt_id)
        with self.transaksjon() as con:
            id = self.neste_id(con, "an")
            con.execute("INSERT INTO analyse VALUES (?, ?, ?, ?)", (id, prosjekt_id, navn, naa()))
        return self.analyse(id)

    def analyse(self, id: str) -> dict[str, Any]:
        return self._hent("analyse", id)

    def analyser(self, prosjekt_id: str | None = None) -> list[dict[str, Any]]:
        with self.lesing() as con:
            if prosjekt_id:
                return _rader(con.execute("SELECT * FROM analyse WHERE prosjekt_id = ? ORDER BY id", (prosjekt_id,)).fetchall())
            return _rader(con.execute("SELECT * FROM analyse ORDER BY id").fetchall())

    def opprett_planversjon(self, analyse_id: str, oppgavetekst: str, plan: Plan, endringsnotat: str = "") -> dict[str, Any]:
        self.analyse(analyse_id)
        with self.transaksjon() as con:
            forrige = con.execute("SELECT MAX(versjon) FROM planversjon WHERE analyse_id = ?", (analyse_id,)).fetchone()[0]
            versjon = (forrige or 0) + 1
            id = f"{analyse_id}.v{versjon}"
            con.execute(
                "INSERT INTO planversjon(id, analyse_id, versjon, opprettet, oppgavetekst, plan_json, status, endringsnotat)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (id, analyse_id, versjon, naa(), oppgavetekst, json.dumps(plan.til_dict(), ensure_ascii=False), PLAN_UTKAST, endringsnotat),
            )
        return self.planversjon(id)

    def planversjon(self, id: str) -> dict[str, Any]:
        p = self._hent("planversjon", id)
        p["plan"] = Plan.fra_dict(json.loads(p["plan_json"]))
        return p

    def planversjoner(self, analyse_id: str) -> list[dict[str, Any]]:
        with self.lesing() as con:
            rader = _rader(con.execute("SELECT * FROM planversjon WHERE analyse_id = ? ORDER BY versjon", (analyse_id,)).fetchall())
        for p in rader:
            p["plan"] = Plan.fra_dict(json.loads(p["plan_json"]))
        return rader

    def gjeldende_planversjon(self, analyse_id: str) -> dict[str, Any] | None:
        versjoner = self.planversjoner(analyse_id)
        godkjente = [p for p in versjoner if p["status"] == PLAN_GODKJENT]
        if godkjente:
            return godkjente[-1]
        return versjoner[-1] if versjoner else None

    def godkjenn_planversjon(self, id: str, ansvarlig: str) -> dict[str, Any]:
        p = self.planversjon(id)
        if p["status"] != PLAN_UTKAST:
            raise LagerFeil(f"Planversjon {id} har status «{p['status']}» og kan ikke godkjennes.")
        with self.transaksjon() as con:
            con.execute(
                "UPDATE planversjon SET status = ? WHERE analyse_id = ? AND status = ?",
                (PLAN_ERSTATTET, p["analyse_id"], PLAN_GODKJENT),
            )
            self._oppdater(con, "planversjon", id, status=PLAN_GODKJENT, godkjent_av=ansvarlig, godkjent=naa())
        return self.planversjon(id)

    # --- kjøring og forsøk ---------------------------------------------------------

    def opprett_kjoring(self, analyse_id: str, planversjon_id: str, dokument_id: str) -> dict[str, Any]:
        with self.transaksjon() as con:
            id = self.neste_id(con, "kj")
            con.execute(
                "INSERT INTO kjoring(id, analyse_id, planversjon_id, dokument_id, status, opprettet) VALUES (?,?,?,?,?,?)",
                (id, analyse_id, planversjon_id, dokument_id, KJ_PLANLAGT, naa()),
            )
        return self.kjoring(id)

    def kjoring(self, id: str) -> dict[str, Any]:
        return self._hent("kjoring", id)

    def kjoringer(self, analyse_id: str) -> list[dict[str, Any]]:
        with self.lesing() as con:
            return _rader(con.execute("SELECT * FROM kjoring WHERE analyse_id = ? ORDER BY id", (analyse_id,)).fetchall())

    def oppdater_kjoring(self, id: str, **felter: Any) -> None:
        with self.transaksjon() as con:
            self._oppdater(con, "kjoring", id, **felter)

    def opprett_forsok(self, kjoring_id: str, *, motor: str, simulert: bool, modell_onsket: str, input_hash: str,
                       input_sti: str, arbeider_pid: int, manifest: dict[str, Any]) -> dict[str, Any]:
        """Registrerer forsøket som aktivt FØR motorkallet, og setter kjøringen aktiv i samme transaksjon."""
        with self.transaksjon() as con:
            kj = _rad(con.execute("SELECT * FROM kjoring WHERE id = ?", (kjoring_id,)).fetchone())
            if kj is None:
                raise LagerFeil(f"Fant ingen kjøring «{kjoring_id}».")
            aktiv = con.execute("SELECT id FROM forsok WHERE kjoring_id = ? AND status = ?", (kjoring_id, FS_AKTIV)).fetchone()
            if aktiv is not None:
                raise LagerFeil(f"Kjøring {kjoring_id} har allerede et aktivt forsøk ({aktiv[0]}).")
            nr = (con.execute("SELECT MAX(nr) FROM forsok WHERE kjoring_id = ?", (kjoring_id,)).fetchone()[0] or 0) + 1
            id = f"{kjoring_id}.f{nr}"
            con.execute(
                "INSERT INTO forsok(id, kjoring_id, nr, status, startet, arbeider_pid, motor, simulert, modell_onsket,"
                " input_hash, input_sti, manifest_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (id, kjoring_id, nr, FS_AKTIV, naa(), arbeider_pid, motor, int(simulert), modell_onsket, input_hash,
                 input_sti, json.dumps(manifest, ensure_ascii=False)),
            )
            self._oppdater(con, "kjoring", kjoring_id, status=KJ_AKTIV, gjeldende_forsok_id=id)
        return self.forsok(id)

    def forsok(self, id: str) -> dict[str, Any]:
        f = self._hent("forsok", id)
        f["simulert"] = bool(f["simulert"])
        return f

    def forsok_for_kjoring(self, kjoring_id: str) -> list[dict[str, Any]]:
        with self.lesing() as con:
            rader = _rader(con.execute("SELECT * FROM forsok WHERE kjoring_id = ? ORDER BY nr", (kjoring_id,)).fetchall())
        for f in rader:
            f["simulert"] = bool(f["simulert"])
        return rader

    def aktive_forsok(self, analyse_id: str | None = None) -> list[dict[str, Any]]:
        with self.lesing() as con:
            if analyse_id:
                rader = con.execute(
                    "SELECT f.* FROM forsok f JOIN kjoring k ON k.id = f.kjoring_id WHERE f.status = ? AND k.analyse_id = ?",
                    (FS_AKTIV, analyse_id),
                ).fetchall()
            else:
                rader = con.execute("SELECT * FROM forsok WHERE status = ?", (FS_AKTIV,)).fetchall()
        return _rader(rader)

    def avslutt_forsok(self, id: str, *, status: str, kjoring_status: str, **felter: Any) -> dict[str, Any]:
        """Lagrer råsvar, svar, validering, feil og sluttstatus samlet (atomisk)."""
        f = self.forsok(id)
        for nokkel in ("svar_json", "validering_json", "forbruk_json", "manifest_json"):
            if nokkel in felter and not isinstance(felter[nokkel], (str, type(None))):
                felter[nokkel] = json.dumps(felter[nokkel], ensure_ascii=False)
        with self.transaksjon() as con:
            self._oppdater(con, "forsok", id, status=status, avsluttet=naa(), **felter)
            self._oppdater(con, "kjoring", f["kjoring_id"], status=kjoring_status, gjeldende_forsok_id=id)
        return self.forsok(id)

    # --- kontroll ----------------------------------------------------------------

    def registrer_kontroll(self, forsok_id: str, *, ansvarlig: str, handling: str, begrunnelse: str,
                           opprinnelig: Any = None, nytt: Any = None) -> dict[str, Any]:
        self.forsok(forsok_id)
        with self.transaksjon() as con:
            id = self.neste_id(con, "ko")
            con.execute(
                "INSERT INTO kontroll(id, forsok_id, tid, ansvarlig, handling, opprinnelig_json, nytt_json, begrunnelse)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (id, forsok_id, naa(), ansvarlig, handling,
                 json.dumps(opprinnelig, ensure_ascii=False) if opprinnelig is not None else None,
                 json.dumps(nytt, ensure_ascii=False) if nytt is not None else None, begrunnelse),
            )
        return self._hent("kontroll", id)

    def kontroller(self, forsok_id: str) -> list[dict[str, Any]]:
        with self.lesing() as con:
            rader = _rader(con.execute("SELECT * FROM kontroll WHERE forsok_id = ? ORDER BY rowid", (forsok_id,)).fetchall())
        for k in rader:
            k["opprinnelig"] = json.loads(k["opprinnelig_json"]) if k["opprinnelig_json"] else None
            k["nytt"] = json.loads(k["nytt_json"]) if k["nytt_json"] else None
        return rader

    # --- hendelser og tilstand ------------------------------------------------------

    def logg(self, type: str, *, analyse_id: str | None = None, kjoring_id: str | None = None,
             forsok_id: str | None = None, **detaljer: Any) -> None:
        with self.transaksjon() as con:
            con.execute(
                "INSERT INTO hendelse(tid, type, analyse_id, kjoring_id, forsok_id, detaljer_json) VALUES (?,?,?,?,?,?)",
                (naa(), type, analyse_id, kjoring_id, forsok_id, json.dumps(detaljer, ensure_ascii=False) if detaljer else None),
            )

    def hendelser(self, *, analyse_id: str | None = None, kjoring_id: str | None = None, antall: int = 50) -> list[dict[str, Any]]:
        with self.lesing() as con:
            if kjoring_id:
                rader = con.execute("SELECT * FROM hendelse WHERE kjoring_id = ? ORDER BY id DESC LIMIT ?", (kjoring_id, antall)).fetchall()
            elif analyse_id:
                rader = con.execute("SELECT * FROM hendelse WHERE analyse_id = ? ORDER BY id DESC LIMIT ?", (analyse_id, antall)).fetchall()
            else:
                rader = con.execute("SELECT * FROM hendelse ORDER BY id DESC LIMIT ?", (antall,)).fetchall()
        ut = _rader(rader)
        for h in ut:
            h["detaljer"] = json.loads(h["detaljer_json"]) if h["detaljer_json"] else {}
        return list(reversed(ut))

    def sett_tilstand(self, nokkel: str, verdi: Any) -> None:
        with self.transaksjon() as con:
            con.execute(
                "INSERT INTO tilstand(nokkel, verdi) VALUES (?, ?) ON CONFLICT(nokkel) DO UPDATE SET verdi = excluded.verdi",
                (nokkel, json.dumps(verdi, ensure_ascii=False)),
            )

    def tilstand(self, nokkel: str) -> Any:
        with self.lesing() as con:
            rad = con.execute("SELECT verdi FROM tilstand WHERE nokkel = ?", (nokkel,)).fetchone()
        return json.loads(rad[0]) if rad else None

    def slett_tilstand(self, nokkel: str) -> None:
        with self.transaksjon() as con:
            con.execute("DELETE FROM tilstand WHERE nokkel = ?", (nokkel,))
