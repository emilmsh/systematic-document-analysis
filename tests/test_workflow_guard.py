"""A failed prerequisite pauses the workflow without silently replacing it."""
import json
from pathlib import Path

import pytest

from kildeanalyse import kjoring, tjeneste
from kildeanalyse.lager import Lager
from kildeanalyse.modell import Stotte
from kildeanalyse.visning import md_status
from test_flyt import KRIT, _oppsett


def draft(store, criteria=None, purpose='Read the sources'):
    project = tjeneste.opprett_prosjekt(store, 'Workflow guard')
    result = tjeneste.opprett_analyse(store, project['id'], 'Test', purpose)
    return result['analyse']['id']


def paused(store, aid, code):
    # A restarted process and the displayed status must expose the same pause.
    status = tjeneste.vis_status(Lager(store.mappe), aid)
    block = status['workflow_block']
    assert block['status'] == 'paused' and block['code'] == code
    assert block['reason'] and block['next_action']
    assert block['automatic_fallback_allowed'] is False
    assert status['stopp_forespurt'] and status['aktiv_arbeider'] is None
    assert block['reason'] in md_status(status)
    return block





@pytest.mark.parametrize('background', [False, True])
@pytest.mark.parametrize('approved', [False, True])
def test_missing_approval_or_source_selection_never_starts_reader(tmp_path, monkeypatch, background, approved):
    store = Lager(tmp_path / 'data')
    aid = draft(store)
    if approved:
        tjeneste.godkjenn_plan(store, aid, 'Test user')
    monkeypatch.setattr(kjoring, 'lag_adapter', lambda *a: pytest.fail('No reader may be created'))
    with pytest.raises(tjeneste.TjenesteFeil):
        (tjeneste.start_i_bakgrunnen if background else tjeneste.start)(store, aid)
    paused(store, aid, 'NO_RUNS_PLANNED' if approved else 'PLAN_APPROVAL_REQUIRED')


@pytest.mark.parametrize('background', [False, True])
@pytest.mark.parametrize('selection', [{'kjoring_ider': []}, {'kjoring_ider': ['unknown-run']}, {'maks': 0}, {'maks': -1}])
def test_bad_scope_is_not_silently_ignored(tmp_path, monkeypatch, background, selection):
    store = Lager(tmp_path / 'data')
    _, aid, runs = _oppsett(store)
    monkeypatch.setattr(kjoring, 'lag_adapter', lambda *a: pytest.fail('No reader may be created'))
    with pytest.raises(tjeneste.TjenesteFeil):
        (tjeneste.start_i_bakgrunnen if background else tjeneste.start)(store, aid, **selection)
    paused(store, aid, 'INVALID_RUN_SCOPE')
    assert all(not store.forsok_for_kjoring(run['id']) for run in runs)


@pytest.mark.parametrize('failure', ['unsupported', 'exception'])
def test_reader_unavailable_preserves_pause_on_failed_resume(tmp_path, monkeypatch, failure):
    store = Lager(tmp_path / 'data')
    _, aid, runs = _oppsett(store)
    original = kjoring.lag_adapter

    class Unavailable:
        def sjekk_stotte(self):
            if failure == 'exception': raise OSError('Unavailable')
            return Stotte(False, ['Reader is not configured'])

    monkeypatch.setattr(kjoring, 'lag_adapter', lambda *a: Unavailable())
    for start in [tjeneste.start, tjeneste.gjenoppta]:
        with pytest.raises(tjeneste.TjenesteFeil): start(store, aid)
        paused(store, aid, 'READER_UNAVAILABLE')
    assert all(not store.forsok_for_kjoring(run['id']) for run in runs)
    monkeypatch.setattr(kjoring, 'lag_adapter', original)
    report = tjeneste.gjenoppta(store, aid)
    assert len(report['startet']) == 3 and report['workflow_block'] is None


@pytest.mark.parametrize('failure', ['missing', 'modified'])
def test_source_integrity_failure_does_not_block_other_sources(tmp_path, monkeypatch, failure):
    store = Lager(tmp_path / 'data')
    _, aid, runs = _oppsett(store)
    source = Path(store.dokument(runs[0]['dokument_id'])['lagret_kopi'])
    if failure == 'missing': source.unlink()
    else: source.write_bytes(b'Changed after import')
    report = tjeneste.start(store, aid)
    assert report['workflow_block'] is None
    assert report['run_issues'][0]['run_id'] == runs[0]['id']
    assert not store.forsok_for_kjoring(runs[0]['id'])
    assert store.kjoring(runs[0]['id'])['status'] == 'feilet'
    assert all(store.kjoring(run['id'])['status'] == 'fullført' for run in runs[1:])


@pytest.mark.parametrize('failure,code', [('krasj', 'READER_FAILED'), ('timeout', 'READER_FAILED'), ('ugyldig_svar', 'READER_FAILED'),
                                        ('invalid_result', 'VALIDATION_FAILED')])
def test_failure_mid_queue_reports_error_and_finishes_other_work(tmp_path, failure, code):
    store = Lager(tmp_path / 'data')
    _, aid, runs = _oppsett(store, {'scenarier': {'nordlys_2025.pdf': failure}})
    report = tjeneste.start(store, aid)
    assert report['startet'] == [r['id'] for r in runs]
    assert report['stoppet_foer'] == []
    assert store.kjoring(runs[0]['id'])['status'] == 'fullført'
    assert store.kjoring(runs[2]['id'])['status'] == 'fullført'
    assert report['workflow_block'] is None
    assert [(issue['run_id'], issue['code']) for issue in report['run_issues']] == [(runs[1]['id'], code)]
    assert store.forsok_for_kjoring(runs[0]['id'])[0]['svar_json']
    status = tjeneste.vis_status(Lager(store.mappe), aid)
    assert [issue['run_id'] for issue in status['run_issues']] == [runs[1]['id']]
    assert status['workflow_block'] is None and not status['stopp_forespurt']
    assert 'trenger oppfølging' in md_status(status)


def test_input_audit_write_failure_prevents_model_call(tmp_path, monkeypatch):
    store = Lager(tmp_path / 'data')
    _, aid, runs = _oppsett(store)
    original = Path.write_text

    def write(path, *args, **kwargs):
        if path.name == 'input.json' and path.parent.name == runs[0]['id'] + '.f1':
            raise OSError('Audit storage unavailable')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', write)
    report = tjeneste.start(store, aid)
    assert report['workflow_block'] is None
    assert not store.forsok_for_kjoring(runs[0]['id'])
    assert 'Audit storage' in report['run_issues'][0]['reason']
    assert all(store.kjoring(run['id'])['status'] == 'fullført' for run in runs[1:])


def test_new_draft_blocks_old_approved_plan(tmp_path):
    store = Lager(tmp_path / 'data')
    _, aid, runs = _oppsett(store)
    tjeneste.ny_planversjon(store, aid, 'Clarify scope', tilleggsinstruks='Count only this year.')
    with pytest.raises(tjeneste.TjenesteFeil):
        tjeneste.start(store, aid)
    paused(store, aid, 'PLAN_APPROVAL_REQUIRED')
    assert all(not store.forsok_for_kjoring(run['id']) for run in runs)
    tjeneste.godkjenn_plan(store, aid, 'Test user')
    tjeneste.legg_til_kjoringer(store, aid)
    with pytest.raises(tjeneste.TjenesteFeil):
        tjeneste.start(store, aid, [runs[0]['id']])
    paused(store, aid, 'INVALID_RUN_SCOPE')
    report = tjeneste.start(store, aid)
    assert len(report['startet']) == 3 and report['workflow_block'] is None


def test_failed_final_audit_preserves_raw_answer_and_finishes_other_runs(tmp_path, monkeypatch):
    store = Lager(tmp_path / 'data')
    _, aid, runs = _oppsett(store)
    original = Path.write_text
    writes = []

    def write(path, *args, **kwargs):
        if path.name == 'manifest.json':
            writes.append(path)
            if len(writes) == 2: raise OSError('Final audit write failed')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', write)
    report = tjeneste.start(store, aid)
    assert report['workflow_block'] is None
    assert report['run_issues'][0]['code'] == 'RUN_UNRESOLVED'
    attempt, = store.forsok_for_kjoring(runs[0]['id'])
    assert attempt['status'] == 'uavklart'
    assert (Path(attempt['input_sti']) / 'raasvar.txt').read_text(encoding='utf-8')
    assert all(store.kjoring(run['id'])['status'] == 'fullført' for run in runs[1:])
    assert tjeneste.gjenoppta(store, aid)['startet'] == []
    assert len(store.forsok_for_kjoring(runs[0]['id'])) == 1  # no automatic retry


def test_error_flag_rejects_even_a_structurally_valid_answer(tmp_path, monkeypatch):
    from kildeanalyse import execution
    store = Lager(tmp_path / 'data')
    _, aid, runs = _oppsett(store)
    original = execution.execute

    def reply(*args):
        result = original(*args)
        result.feil = 'Reader reported an error alongside its answer'
        return result

    monkeypatch.setattr(execution, 'execute', reply)
    report = tjeneste.start(store, aid)
    assert report['workflow_block'] is None and len(report['run_issues']) == 3
    attempt, = store.forsok_for_kjoring(runs[0]['id'])
    assert attempt['raasvar'] and not attempt['svar_json']
    assert not tjeneste.vis_kjoring(store, runs[0]['id'])['forsok'][0]['result']
    assert all(store.kjoring(run['id'])['status'] == 'feilet' for run in runs)


def test_queue_audit_failure_releases_worker_and_dispatches_nothing(tmp_path, monkeypatch):
    store = Lager(tmp_path / 'data')
    _, aid, runs = _oppsett(store)
    original = store.logg

    def log(event, **kwargs):
        if event == 'ko_startet': raise OSError('Cannot log queue start')
        return original(event, **kwargs)

    monkeypatch.setattr(store, 'logg', log)
    with pytest.raises(OSError, match='queue start'):
        tjeneste.start(store, aid)
    paused(store, aid, 'WORKFLOW_ERROR')
    assert all(not store.forsok_for_kjoring(run['id']) for run in runs)
