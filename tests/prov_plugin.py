r"""Windows-integrasjon uten modellkall: ren plugin-kopi, bootstrap og MCP.

Kjør manuelt: .venv\Scripts\python.exe tests/prov_plugin.py
Bruker midlertidige mapper. Første oppstart installerer pakkene fra PyPI.
"""
from __future__ import annotations

import asyncio
import argparse
import json
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
               SDA_PYTHON=sys.executable, PYTHONUTF8="1", SDA_MAINTENANCE_DIR=str(data/'maintenance'),
               SDA_PROJECTS_ROOT=str(data/'visible-projects'))
    params = StdioServerParameters(command="cmd.exe", args=["/d", "/c", str(root / "bin" / "start_server.cmd")], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            assert initialized.server_info.version == VERSJON
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert len(names) == 19 and 'set_project_directory' in names and 'create_analysis' in names, names
            assert 'opprett_analyse' not in names
            async def call(name, arguments):
                result = await session.call_tool(name, arguments)
                body = "\n".join(c.text for c in result.content if hasattr(c, "text"))
                assert not result.is_error, body
                value = json.loads(body)
                assert 'error' not in value, value
                return body
            project = json.loads(await call('create_project', {'name':'Røykprøve æøå'}))
            project_id = project['id']
            assert project_id == ('pr2' if expected_project else 'pr1'), project
            created = json.loads(await call('create_analysis', {
                'project_id':project_id, 'name':'Parameter check', 'request':'Summarise each file.',
                'engine':'claude_cli', 'model':'sonnet', 'language':'nb', 'reasoning_effort':'medium'}))
            aid = created['analysis']['id']
            await call('new_plan_version', {'analysis_id':aid, 'change_note':'Different reader',
                'engine':'codex_cli', 'model':'gpt-5.6-terra', 'reasoning_effort':'high',
                'engine_settings':{'timeout_seconds':1200}})
            plan = await call('show_plan', {'analysis_id':aid})
            assert all(x in plan for x in ('sonnet','medium','gpt-5.6-terra','high','1200')), plan
            # API planning uses no credentials or provider calls.
            for engine, model in [('openai_api','gpt-6-astra'), ('anthropic_api','claude-sonnet-4-6'),
                                  ('openrouter_api','openai/gpt-6-astra'), ('kompatibel_api','chosen-model'),
                                  ('azure_foundry_api','my-deployment')]:
                settings = {'base_url':'https://example.org/v1'} if engine == 'kompatibel_api' else {}
                if engine == 'azure_foundry_api':
                    settings = {'base_url':'https://example.services.ai.azure.com', 'api_format':'chat_completions'}
                await call('new_plan_version', {'analysis_id':aid, 'change_note':'API plan without calls',
                    'engine':engine, 'model':model, 'reasoning_effort':'high', 'engine_settings':settings})
                plan = json.loads(await call('show_plan', {'analysis_id':aid}))
                assert plan['current']['plan']['engine'] == engine, plan
                assert plan['current']['plan']['model'] == model, plan
            await call('new_plan_version', {'analysis_id':aid, 'change_note':'English commentary', 'language':'en'})
            english = json.loads(await call('show_plan', {'analysis_id':aid}))
            assert english['current']['plan']['language'] == 'en', english
            assert english['versions'][0]['plan']['language'] == 'nb', english
            source_file = data/'source.txt'
            source_file.write_text('A comparable source with a documented policy.', encoding='utf-8')
            imported = json.loads(await call('import_documents', {'project_id':'pr2' if expected_project else 'pr1', 'paths':[str(source_file)]}))
            assert imported['results'][0]['document']['source_metadata']['format'] == 'txt', imported
            runs = json.loads(await call('add_runs', {'analysis_id':aid}))
            compact = json.loads(await call('show_status', {'analysis_id':aid}))
            detailed = json.loads(await call('show_status', {'analysis_id':aid, 'details':True}))
            assert compact['detail_level'] == 'compact' and detailed['detail_level'] == 'full'
            assert compact['teller'] == detailed['teller'] and compact['run_warnings'] == []
            assert 'sider' not in compact['rader'][0]['document']
            assert 'sider' in detailed['rader'][0]['document']
            preview = json.loads(await call('show_input_package', {'run_id':runs['new'][0]['id']}))
            assert preview['package']['source_units'][0]['location'] == 'Line 1', preview
            exported = json.loads(await call('export_results', {'analysis_id':aid}))
            assert Path(exported['documentation_archive']).is_file() and Path(exported['workbook']).is_file(), exported
            # General tasks have no criteria prerequisite and expose their actual deliverable.
            generic = json.loads(await call('create_analysis', {
                'project_id': 'pr2' if expected_project else 'pr1', 'name': 'Generic task smoke test',
                'request': 'Produce a readable summary of each file.', 'engine': 'simulert'}))
            task_id = generic['analysis']['id']
            task_runs = json.loads(await call('add_runs', {'analysis_id': task_id}))
            task_run = task_runs['new'][0]['id']
            task_input = json.loads(await call('show_input_package', {'run_id': task_run}))
            assert 'result' in task_input['package']['response_schema']['properties']
            assert 'vurderinger' not in task_input['package']['response_schema']['properties']
            await call('approve_plan', {'analysis_id': task_id, 'approved_by': 'Automated fixture only'})
            await call('start_runs', {'analysis_id': task_id})
            for _ in range(100):
                task_detail = json.loads(await call('show_run', {'run_id': task_run}))
                if task_detail['attempts'] and task_detail['attempts'][-1]['attempts']['status'] != 'aktiv':
                    break
                await asyncio.sleep(0.1)
            assert 'SIMULATED' in task_detail['attempts'][-1]['result'], task_detail
            task_export = json.loads(await call('export_results', {'analysis_id': task_id}))
            assert Path(task_export['entrypoint']).is_file() and Path(task_export['workbook']).is_file()
            import zipfile
            with zipfile.ZipFile(task_export['documentation_archive']) as archive:
                assert f'results/{task_run}.json' in archive.namelist()


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
        print(f"PASS: {'installed copy' if plugin_root else 'clean copy without .venv'}, MCP initialize, 19 tools, English/Norwegian plans, exports, restart and independent runtime.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, help="Prøv denne installerte kopien i stedet for å lage en ren kopi")
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(main(args.plugin_root), timeout=240))
