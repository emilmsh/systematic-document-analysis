"""Portable reading copies in a user-visible project directory; never the database."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4


def slug(value: str) -> str:
    return re.sub(r'[^\w-]+', '-', value, flags=re.UNICODE).strip('-')[:40] or 'project'


def validate_directory(directory: str, store) -> Path:
    path = Path(directory).expanduser()
    if not path.is_absolute():
        raise ValueError('Choose an absolute project directory outside the application data and plugin installation.')
    path = path.resolve()
    blocked = [store.mappe.resolve()]
    blocked += [(Path.home()/part).resolve() for part in
                ('.systematic-document-analysis/plugins', '.codex/plugins', '.claude/plugins')]
    for key in ('LOCALAPPDATA', 'APPDATA', 'CLAUDE_PLUGIN_ROOT'):
        if os.environ.get(key):
            blocked.append(Path(os.environ[key]).resolve())
    if any(path == root or path.is_relative_to(root) for root in blocked):
        raise ValueError('Choose a visible project directory, not AppData, the database directory or the plugin installation.')
    if path.exists() and not path.is_dir():
        raise ValueError('The project directory is an existing file.')
    return path


def set_directory(store, project_id: str, directory: str | None = None) -> dict:
    project = store.prosjekt(project_id)
    if directory is None and project.get('directory'):
        return project
    if directory is None:
        base = Path(os.environ.get('SDA_PROJECTS_ROOT', str(Path.home() / 'Documents' / 'Systematic Document Analysis')))
        directory = str(base / f'{slug(project["navn"])}-{uuid4().hex[:8]}')
    root = validate_directory(directory, store)
    marker = root / '.sda-project.json'
    identity = {'project_id': project_id, 'store': str(store.db.resolve())}
    if marker.exists():
        if json.loads(marker.read_text(encoding='utf-8')) != identity:
            raise ValueError('This directory belongs to another project or data store.')
    elif root.exists() and any(root.iterdir()):
        raise ValueError('Choose a new or empty project directory; existing files will not be overwritten.')
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding='utf-8')
    previous = project.get('directory')
    result = store.sett_prosjektmappe(project_id, str(root))
    store.logg('project_directory_set', project_id=project_id, directory=str(root), previous=previous)
    write_index(store, project_id)
    return result


def root_for(store, project_id: str) -> Path:
    project = set_directory(store, project_id)
    root = validate_directory(project['directory'], store)
    marker = root / '.sda-project.json'
    expected = {'project_id': project_id, 'store': str(store.db.resolve())}
    if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')) != expected:
        raise ValueError('Project directory marker missing or changed. Choose a new directory with set_project_directory.')
    return root


def plan_text(analysis: dict, versions: list[dict], language: str) -> str:
    from .prompt import bygg_systeminstruks
    from .parametre import fra_plan
    nb = language == 'nb'
    lines = [f'# {"Plan" if nb else "Analysis plan"}: {analysis["navn"]}', '',
             ('Lesekopi. Eksakte historiske instrukser og input finnes i dokumentasjonen per modellkall.' if nb else
              'Reading copy. Exact historical instructions and inputs are preserved per model call.'), '']
    for version in versions:
        plan = version['plan']
        lines += [f'## {"Versjon" if nb else "Version"} {version["versjon"]} ({version["status"]})', '',
                  f'{"Godkjent av" if nb else "Approved by"}: {version.get("godkjent_av") or "—"}',
                  f'{"Endring" if nb else "Change"}: {version.get("endringsnotat") or "—"}', '',
                  f'### {"Bestilling" if nb else "Request"}', '', version['oppgavetekst'], '',
                  f'### {"Leserinnstillinger" if nb else "Reader settings"}', '', '```json',
                  json.dumps(fra_plan(plan), ensure_ascii=False, indent=2), '```', '',
                  f'### {"Instruks" if nb else "Instructions"}', '',
                  '~~~~text', bygg_systeminstruks(plan), '~~~~', '']
        from .task_contract import schema
        from .task_dataset import plan_preview
        preview = plan_preview(plan)
        lines += [f'### {"Datasett" if nb else "Dataset"}', '',
                  ('Standard: én rad per kjøring, med synlig status. Eksporten kan begrenses til nyeste planlagte kjøring per dokument.' if nb else
                   'Default: one row per run, with visible status. Export can select the newest planned run per document.'), '',
                  ('Nested objekter utvides til kolonner. Gjentatte poster bevares i koblede detaljfaner.' if nb else
                   'Nested objects expand into columns. Repeated records have linked detail sheets.'), '']
        for table in preview['tables']:
            for variable in table['variables']:
                label = variable['label'] or variable['path'] or ('Resultat' if nb else 'Result')
                description = variable['description'] or ('Ikke beskrevet.' if nb else 'Not described.')
                lines.append(f'- {table["path"] or "/"} · {label}: {description}')
        if not preview['structured']:
            lines += ['', ('Planen gir fritekst i én resultatkolonne. Foreslå et output_schema før godkjenning når oppgaven skal generere flere analysevariabler.' if nb else
                           'This plan produces prose in one result column. Propose an output_schema before approval when the task should generate several analytical variables.')]
        lines.append('')
        lines += ['### Result contract', '', '```json', json.dumps(schema(plan), ensure_ascii=False, indent=2), '```', '']
    return '\n'.join(lines)


def save_plan(store, analysis_id: str) -> dict:
    analysis = store.analyse(analysis_id)
    project_id = analysis['prosjekt_id']
    root = root_for(store, project_id)
    version = store.planversjoner(analysis_id)[-1]
    directory = root / 'plans' / f'{version["id"]}-{version["status"]}'
    directory.mkdir(parents=True, exist_ok=True)
    # Separate draft/approved/version paths preserve earlier inspection copies.
    path = directory / 'Plan.md'
    if not path.exists():
        path.write_text(plan_text(analysis, [version], version['plan'].sprak), encoding='utf-8')
    contract = directory / 'task.json'
    if not contract.exists():
        contract.write_text(json.dumps({k: getattr(version['plan'], k) for k in
            ('task_instructions', 'output_schema', 'quote_checks')}, ensure_ascii=False, indent=2), encoding='utf-8')
    write_index(store, project_id)
    return {'project_directory': str(root), 'plan_path': str(path), 'task_path': str(contract)}


def save_input(store, run: dict, package: dict) -> str:
    analysis = store.analyse(run['analyse_id'])
    root = root_for(store, analysis['prosjekt_id'])
    text = json.dumps(package, ensure_ascii=False, indent=2)
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    folder = root / 'previews' / run['id']
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{digest[:24]}.json'
    if path.exists() and path.read_text(encoding='utf-8') != text:
        raise ValueError('A generated input preview has changed. Restore it or choose a new project directory.')
    if not path.exists():
        path.write_text(text, encoding='utf-8')
    write_index(store, analysis['prosjekt_id'])
    return str(path)


def write_index(store, project_id: str) -> None:
    project = store.prosjekt(project_id)
    if not project.get('directory'):
        return
    root = Path(project['directory'])
    analyses = store.analyser(project_id)
    language = store.gjeldende_planversjon(analyses[-1]['id'])['plan'].sprak if analyses and store.gjeldende_planversjon(analyses[-1]['id']) else 'nb'
    nb = language == 'nb'
    lines = [f'# {project["navn"]}', '',
             ('Start med planen før kjøring og resultatene etter eksport. Denne oversikten oppdateres av pluginen.' if nb else
              'Start with the plan before execution and the results after export. The plugin updates this index.'), '',
             ('Eksporter er øyeblikksbilder. Redigeringer blir ikke automatisk registrert som menneskelig kontroll.' if nb else
              'Exports are snapshots. Edits are not automatically recorded as human reviews.'), '']
    for analysis in analyses:
        runs = store.kjoringer(analysis['id'])
        counts = {status:sum(r['status'] == status for r in runs) for status in sorted({r['status'] for r in runs})}
        lines += [f'## {analysis["navn"]} ({analysis["id"]})', '',
                  f'Status: {json.dumps(counts, ensure_ascii=False)}', '']
        paths = sorted((root/'plans').glob(f'{analysis["id"]}.v*/Plan.md'))
        paths += sorted((root/'exports').glob(f'{analysis["id"]}-*/START*.md'), reverse=True)
        paths += sorted((root/'exports').glob(f'{analysis["id"]}-*/LESMEG.md'), reverse=True)
        for path in paths:
            lines.append(f'- [{path.parent.name} — {path.name}]({quote(path.relative_to(root).as_posix())})')
        lines.append('')
    previews = sorted((root/'previews').glob('*/*.json'))
    if previews:
        lines += [f'## {"Input til gjennomgang" if nb else "Inputs for inspection"}', '']
        for path in previews:
            lines.append(f'- [{path.parent.name}: {path.stem[:12]}]({quote(path.relative_to(root).as_posix())})')
    for path in sorted((root/'previews'/'sources').glob('*.md')):
        lines.append(f'- [{"Kildeuttrekk" if nb else "Extracted source"}: {path.stem}]({quote(path.relative_to(root).as_posix())})')
    (root/'START_HERE.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
