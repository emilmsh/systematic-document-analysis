"""Portable task results and provenance; presentation is not a classification table."""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from . import VERSJON
from .project_files import root_for, plan_text, write_index
from .task_results import current


def readable(value, depth=1):
    """A lossless JSON file accompanies this shape-independent reading copy."""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        if not value:
            return json.dumps(value)
        entries = value.items() if isinstance(value, dict) else enumerate(value, 1)
        return '\n\n'.join('#' * min(depth + 1, 6) + ' ' + str(key) + '\n\n' + readable(item, depth + 1)
                           for key, item in entries)
    return json.dumps(value, ensure_ascii=False)


def export(store, analysis_id, include_sources=True):
    from .tjeneste import vis_kjoring
    from .reader_files import copy_artifacts
    from .dokument import sha256_fil
    analysis = store.analyse(analysis_id)
    runs = store.kjoringer(analysis_id)
    if any(r['status'] == 'aktiv' for r in runs):
        raise ValueError('Wait for active runs to finish before exporting a consistent snapshot.')
    versions = store.planversjoner(analysis_id)
    root = root_for(store, analysis['prosjekt_id'])
    exports = root / 'exports'
    exports.mkdir(exist_ok=True)
    final = exports / f'{analysis_id}-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}'
    nb = versions[-1]['plan'].sprak == 'nb'
    entry = 'START_HER.md' if nb else 'START_HERE.md'
    counts, snapshot = {}, []
    with tempfile.TemporaryDirectory(prefix='.building-', dir=exports) as temporary:
        stage = Path(temporary)
        (stage / 'results').mkdir()
        (stage / 'audit').mkdir()
        (stage / 'Plan.md').write_text(plan_text(analysis, versions, 'nb' if nb else 'en'), encoding='utf-8')
        lines = [f'# {analysis["navn"]}', '',
                 ('Resultater per fil. Hver lenke viser selve leveransen og dens kjøringsstatus.' if nb else
                  'Results per file. Each link shows the actual deliverable and its run status.'), '',
                 '[Plan](Plan.md) · [Audit](audit/analysis.json)', '',
                 ('Automatiske kontroller er ikke faglig eller menneskelig godkjenning. Se validering og begrensninger per forsøk.' if nb else
                  'Automatic checks are not semantic validation or human approval. Inspect validation and limitations per attempt.'), '',
                 ('Dette er et øyeblikksbilde. Videre bearbeiding bør bevare kjørings- og forsøks-ID; endringer her oppdaterer ikke originalene.' if nb else
                  'This is a snapshot. Derived work should retain run and attempt IDs; editing it does not update originals.'), '']
        for run in runs:
            counts[run['status']] = counts.get(run['status'], 0) + 1
            detail = vis_kjoring(store, run['id'])
            document, attempts = detail['dokument'], store.forsok_for_kjoring(run['id'])
            chosen = next((a for a in attempts if a['id'] == run['gjeldende_forsok_id']), None)
            task = detail['planversjon']['plan'].is_task
            view = current(store, chosen) if chosen and task else None
            response = json.loads(chosen['svar_json']) if chosen and chosen.get('svar_json') else None
            payload = view['result'] if view else response
            aid = chosen['id'] if chosen else '—'
            review = view['review_status'] if view else 'See audit'
            simulated = bool(chosen and chosen['simulert'])
            header = [f'# {document["navn"]}', '',
                      f'Run: {run["id"]} · Attempt: {aid} · Plan: {run["planversjon_id"]}', '',
                      f'Status: {run["status"]} · Review: {review}' + (' · **SIMULATED**' if simulated else ''), '',
                      f'Source SHA-256: `{document["sha256"]}`', '',
                      f'[Result JSON]({run["id"]}.json) · [Full run and validation](../audit/{run["id"]}.json)', '']
            if chosen:
                header += [f'[Exact input](../audit/attempts/{aid}/input.json) · [Raw response](../audit/attempts/{aid}/raasvar.txt)', '']
                validation = view['result_validation'] if view else json.loads(chosen.get('validering_json') or '{}')
                header += ['```json', json.dumps({'validation': validation, 'limitations':
                    (view['response'] or {}).get('limitations', []) if view else [],
                    'error': chosen.get('feil')}, ensure_ascii=False, indent=2), '```', '']
            if include_sources:
                folder = stage / 'sources'
                folder.mkdir(exist_ok=True)
                source = Path(document['lagret_kopi'])
                if not source.is_file() or sha256_fil(source) != document['sha256']:
                    raise ValueError(f'Missing or changed preserved source: {document["id"]}.')
                name = f'{document["id"]}_{source.name}'
                shutil.copy2(source, folder / name)
                header += [f'[Source](../sources/{quote(name)})', '']
            header += ['---', '', readable(payload) if payload is not None else
                       ('Ingen resultatleveranse. ' if nb else 'No deliverable. ') + (run.get('merknad') or ''), '']
            (stage / 'results' / f'{run["id"]}.md').write_text('\n'.join(header), encoding='utf-8')
            (stage / 'results' / f'{run["id"]}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            # All attempts and reviews survive; the current result never replaces raw history.
            detail['planversjon']['plan'] = detail['planversjon']['plan'].til_dict()
            for attempt in attempts:
                origin = Path(attempt['input_sti'])
                target = stage / 'audit' / 'attempts' / attempt['id']
                target.mkdir(parents=True)
                for name in ('input.json', 'manifest.json', 'raasvar.txt', 'systeminstruks.txt',
                             'file-workspace.json', 'reader-helper.py'):
                    if (origin / name).is_file():
                        shutil.copy2(origin / name, target / name)
                for name in ('calls', 'workfiles'):
                    if (origin / name).is_dir():
                        copy_artifacts(origin / name, target / name, include_sources=include_sources)
            (stage / 'audit' / f'{run["id"]}.json').write_text(json.dumps(detail, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
            snapshot.append({'run': run, 'source_sha256': document['sha256'], 'result_path': f'results/{run["id"]}.json',
                             'audit_path': f'audit/{run["id"]}.json'})
            lines += [f'- [{document["navn"]} — {run["id"]}](results/{run["id"]}.md): {run["status"]}' +
                      (' · SIMULATED' if simulated else '')]
        (stage / 'audit' / 'analysis.json').write_text(json.dumps({'app_version': VERSJON, 'analysis': analysis,
            'plans': [{**v, 'plan': v['plan'].til_dict()} for v in versions], 'runs': snapshot,
            'exported': datetime.now().astimezone().isoformat()}, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        (stage / entry).write_text('\n'.join(lines) + '\n', encoding='utf-8')
        stage.rename(final)
    store.logg('eksportert', analyse_id=analysis_id, mappe=str(final), med_kilder=include_sources, format='task_results')
    write_index(store, analysis['prosjekt_id'])
    return {'mappe': str(final), 'entrypoint': str(final / entry), 'results_directory': str(final / 'results'),
            'project_directory': str(root), 'antall_kjoringer': len(runs), 'teller': counts,
            'filer': sorted(p.name for p in final.iterdir()), 'format': 'task_results'}
