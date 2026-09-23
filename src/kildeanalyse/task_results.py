"""Read and review arbitrary results without translating or flattening their contents."""
import json


def current(store, attempt):
    response = json.loads(attempt['svar_json']) if attempt.get('svar_json') else None
    reviews = store.kontroller(attempt['id'])
    for item in reviews:
        if item['handling'] == 'rettet':
            response = item['nytt']
    validation = json.loads(attempt.get('validering_json') or 'null')
    if any(r['handling'] == 'rettet' for r in reviews):
        from .task_contract import validate
        run = store.kjoring(attempt['kjoring_id'])
        plan = store.planversjon(run['planversjon_id'])['plan']
        document = store.dokument(run['dokument_id'])
        manifest = json.loads(attempt.get('manifest_json') or '{}')
        validation = validate(plan, document, response, manifest.get('sider_sendt', []))
    return {'result': response.get('result') if isinstance(response, dict) else None,
            'response': response, 'review_status': reviews[-1]['handling'] if reviews else 'ikke kontrollert',
            'result_validation': validation,
            'result_origin': 'human_correction' if any(r['handling'] == 'rettet' for r in reviews) else 'worker'}


def review(store, attempt, plan, reviewer, action, reason, replacement):
    from .tjeneste import TjenesteFeil
    from .task_contract import validate
    run = store.kjoring(attempt['kjoring_id'])
    original = current(store, attempt)['response']
    if action != 'rettet' and replacement is not None:
        raise TjenesteFeil('replacement_response requires action=corrected.')
    candidate = replacement if action == 'rettet' else original
    if action in ('godkjent', 'rettet'):
        document = store.dokument(run['dokument_id'])
        manifest = json.loads(attempt.get('manifest_json') or '{}')
        validation = validate(plan, document, candidate, manifest.get('sider_sendt', []))
        if not validation['gyldig']:
            raise TjenesteFeil('Cannot approve/correct an invalid result: ' + str(validation['feil']))
    item = store.registrer_kontroll(attempt['id'], ansvarlig=reviewer.strip(), handling=action,
        begrunnelse=reason.strip(), opprinnelig=original,
        nytt=replacement if action == 'rettet' else None)
    store.logg('kontroll_registrert', analyse_id=run['analyse_id'], kjoring_id=run['id'],
               forsok_id=attempt['id'], handling=action, ansvarlig=reviewer)
    return {'kontroll': item, **current(store, attempt)}
