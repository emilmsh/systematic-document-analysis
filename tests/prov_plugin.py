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
               SDA_DATA=str(data / "analyse"),
               SDA_PYTHON=sys.executable, PYTHONUTF8="1", SDA_MAINTENANCE_DIR=str(data/'maintenance'))
    params = StdioServerParameters(command="cmd.exe", args=["/d", "/c", str(root / "bin" / "start_server.cmd")], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            assert initialized.server_info.version == VERSJON
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert len(names) == 36 and 'create_analysis' in names and 'opprett_analyse' in names, names
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
            # Planlegging i den felles MCP-flaten krever ingen API-nøkkel eller modellkall.
            for engine, model in [('openai_api','gpt-6-astra'), ('anthropic_api','claude-sonnet-4-6'),
                                  ('openrouter_api','openai/gpt-6-astra'), ('kompatibel_api','chosen-model')]:
                settings = {'base_url':'https://example.org/v1'} if engine == 'kompatibel_api' else {}
                await call('ny_planversjon', {'analyse_id':aid, 'endringsnotat':'API-plan uten kall',
                                             'motor':engine, 'modell':model, 'tenkenivaa':'high',
                                             'motorinnstillinger_json':json.dumps(settings)})
                body = await call('vis_plan', {'analyse_id':aid})
                assert engine in body and model in body and 'separat betaling' in body
            await call('new_plan_version', {'analysis_id':aid, 'change_note':'English commentary', 'language':'en'})
            english = json.loads(await call('show_plan', {'analysis_id':aid}))
            assert english['current']['plan']['language'] == 'en', english
            assert english['versions'][0]['plan']['language'] == 'nb', english
            source_file = data/'source.txt'
            source_file.write_text('A comparable source with a documented policy.', encoding='utf-8')
            imported = json.loads(await call('import_documents', {'project_id':'pr2' if expected_project else 'pr1', 'paths':[str(source_file)]}))
            assert imported['results'][0]['document']['source_metadata']['format'] == 'txt', imported
            runs = json.loads(await call('add_runs', {'analysis_id':aid}))
            preview = json.loads(await call('show_input_package', {'run_id':runs['new'][0]['id']}))
            assert preview['package']['source_units'][0]['location'] == 'Line 1', preview
            exported = json.loads(await call('export_results', {'analysis_id':aid}))
            assert (Path(exported['directory'])/'plan-summary.md').is_file(), exported


async def main(plugin_root: Path | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix="sda-plugin-") as temp:
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
        print(f"PASS: {'installed copy' if plugin_root else 'clean copy without .venv'}, MCP initialize, 36 tools, English/Norwegian plans, exports, restart and independent runtime.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, help="Prøv denne installerte kopien i stedet for å lage en ren kopi")
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(main(args.plugin_root), timeout=240))
