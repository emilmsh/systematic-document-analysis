r"""Windows-integrasjon uten modellkall: ren plugin-kopi, bootstrap og MCP.

Kjør manuelt: .venv\Scripts\python.exe tests/prov_plugin.py
Bruker midlertidige mapper. Første oppstart installerer pakkene fra PyPI.
"""
from __future__ import annotations

import asyncio
import argparse
import json
import re
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from kildeanalyse import VERSJON

ROOT = Path(__file__).resolve().parents[1]


async def probe(root: Path, data: Path, *, expected_project: bool = False) -> None:
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(data / "runtime"),
               OE_KILDEANALYSE_DATA=str(data / "analyse"),
               OE_KILDEANALYSE_PYTHON=sys.executable, PYTHONUTF8="1")
    params = StdioServerParameters(command="cmd.exe", args=["/d", "/c", str(root / "bin" / "start_server.cmd")], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            assert initialized.server_info.version == VERSJON
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert len(names) == 17, names
            # Ingen vis_oppsett her: testen trenger verken innlogging eller leverandørkontakt.
            result = await session.call_tool("opprett_prosjekt", {"navn": "Røykprøve æøå"})
            text = "\n".join(c.text for c in result.content if hasattr(c, "text"))
            assert not result.is_error and "Røykprøve æøå" in text, text
            assert ("pr2" if expected_project else "pr1") in text, text
            async def call(name, arguments):
                result = await session.call_tool(name, arguments)
                body = "\n".join(c.text for c in result.content if hasattr(c, "text"))
                assert not result.is_error and not body.startswith("Feil:"), body
                return body
            criteria = data / "kriterier.json"
            criteria.write_text(json.dumps({"kriterier":[{"id":"k1", "spørsmål":"Er tiltak omtalt?",
                                                         "tillatte_svar":["ja","nei"]}]}), encoding="utf-8")
            created = await call("opprett_analyse", {
                "prosjekt_id": "pr2" if expected_project else "pr1", "navn":"Parameterkontroll",
                "oppgavetekst":"Lokal MCP-kontroll uten modellkall", "kriteriefil":str(criteria),
                "motor":"claude_cli", "modell":"sonnet", "tenkenivaa":"medium"})
            aid = re.search(r"Analyse (\S+)", created).group(1)
            plan = await call("vis_plan", {"analyse_id":aid})
            assert "sonnet" in plan and "medium" in plan, plan
            await call("ny_planversjon", {"analyse_id":aid, "endringsnotat":"Annen motor og nivå",
                                         "motor":"codex_cli", "modell":"gpt-5.6-terra", "tenkenivaa":"high",
                                         "motorinnstillinger_json":'{"tidsavbrudd_sek":1200}'})
            plan = await call("vis_plan", {"analyse_id":aid})
            assert all(x in plan for x in ("sonnet", "medium", "gpt-5.6-terra", "high", "1200")), plan


async def main(plugin_root: Path | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix="oe-plugin-") as temp:
        base = Path(temp)
        clean = plugin_root or base / "ren plugin æøå"
        if plugin_root is None:
            clean.mkdir()
            for name in ("bin", "src"):
                shutil.copytree(ROOT / name, clean / name, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
            shutil.copy2(ROOT / "pyproject.toml", clean)
        data = base / "plugin data æøå"
        await probe(clean, data)
        marker = data / "runtime" / "venv" / "kildeanalyse-source.sha256"
        before = marker.stat().st_mtime_ns
        await probe(clean, data, expected_project=True)
        assert marker.stat().st_mtime_ns == before, "Andre start skal ikke reinstallere"
        python = data / "runtime" / "venv" / "Scripts" / "python.exe"
        origin = subprocess.check_output([str(python), "-I", "-X", "utf8", "-c", "import kildeanalyse; print(kildeanalyse.__file__)"], encoding="utf-8")
        assert str(ROOT) not in origin and "site-packages" in origin, origin
        print(f"BESTÅTT: {'installert kopi' if plugin_root else 'ren kopi uten .venv'}, MCP initialize, 17 verktøy, norske tegn, parametervalg, planhistorikk, omstart og uavhengig installasjon.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, help="Prøv denne installerte kopien i stedet for å lage en ren kopi")
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(main(args.plugin_root), timeout=240))
