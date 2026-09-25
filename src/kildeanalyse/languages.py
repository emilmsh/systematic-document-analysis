"""English public keys; task output and raw payloads remain verbatim."""
import dataclasses


def language_code(value):
    codes = {'en':'en', 'english':'en', 'nb':'nb', 'no':'nb', 'norsk':'nb', 'norwegian':'nb'}
    if not isinstance(value, str) or value.lower() not in codes:
        raise ValueError('Supported languages: en (English), nb (Norwegian Bokmål).')
    return codes[value.lower()]


FIELD_NAMES = {
    'analyse':'analysis', 'prosjekt':'project', 'planversjon':'plan_version', 'planversjoner':'plan_versions',
    'versjoner':'versions', 'gjeldende':'current', 'kjoringer':'runs', 'kjoring':'run', 'forsok':'attempts',
    'navn':'name', 'versjon':'version', 'formaal':'purpose', 'sprak':'language', 'motor':'engine', 'modell':'model',
    'tenkenivaa':'reasoning_effort', 'motorinnstillinger':'engine_settings', 'tidsavbrudd_sek':'timeout_seconds',
    'maks_samtidige':'max_concurrent_runs', 'samtidige':'concurrent_runs',
    'oppgavetekst':'request', 'endringsnotat':'change_note', 'opprettet':'created', 'godkjent':'approved',
    'godkjent_av':'approved_by', 'dokument':'document', 'dokumenter':'documents',
    'feil':'error', 'melding':'message', 'meldinger':'messages', 'advarsler':'warnings', 'gyldig':'valid',
    'sider_lest':'pages_read', 'lesedekning':'reading_coverage', 'fullstendig':'complete', 'simulert':'simulated',
    'datamappe':'data_directory', 'database':'database', 'motorer':'engines', 'beskrivelse':'description',
    'egenskaper':'properties', 'prosjekter':'projects', 'resultater':'results', 'nye':'new', 'sti':'path',
    'filer':'files', 'mappe':'directory', 'antall_sider':'page_count', 'lesbarhet':'readability',
    'kontrollert_av_totalt':'reviewed_out_of_total', 'kontroller':'reviews', 'kontroll':'review',
    'handling':'action', 'ansvarlig':'reviewer', 'begrunnelse':'reason', 'forbruk':'usage', 'kilde':'source',
    'kjoring_id':'run_id', 'forsok_id':'attempt_id', 'dokument_id':'document_id', 'analyse_id':'analysis_id',
    'prosjekt_id':'project_id', 'planversjon_id':'plan_version_id',
    'pakke':'package', 'kjoreparametre':'run_parameters', 'api_foresporsel':'api_request',
    'systeminstruks':'system_instruction', 'brukermelding':'user_message', 'svarskjema':'response_schema',
}


def public_result(value):
    """Translate structural keys only. User labels, evidence and raw wire payloads stay verbatim."""
    if dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            if k in ('api_foresporsel', 'svarskjema', 'raasvar', 'svar_json', 'forbruk',
                     'svarskjema_sendt', 'manifest', 'motorinfo', 'hendelser',
                     'api_request', 'response_schema', 'result', 'response', 'output_schema', 'quote_checks',
                     'replacement_response', 'opprinnelig', 'nytt'):
                translated = v
            elif k in ('teller', 'motorer') and isinstance(v, dict):
                translated = {identifier: public_result(item) for identifier, item in v.items()}
            else:
                translated = public_result(v)
            result[FIELD_NAMES.get(k, k)] = translated
        return result
    if isinstance(value, (tuple, list)):
        return [public_result(v) for v in value]
    return value
