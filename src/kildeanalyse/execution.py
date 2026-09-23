"""One independent reader call per file; no implicit change of task or analysis method."""
import json
from dataclasses import replace


def settings(values):
    result = dict(values)
    removed = {'document_processing', 'max_chunks', 'priority_terms', 'priority_locations'} & result.keys()
    if removed:
        raise ValueError('Automatic chunk/synthesis processing has been removed: ' + ', '.join(sorted(removed)))
    budget = result.setdefault('input_budget_bytes', 60000)
    if type(budget) is not int or not 8000 <= budget <= 2000000:
        raise ValueError('input_budget_bytes must be an integer between 8000 and 2000000.')
    return result


def size(package):
    wire = package.api_foresporsel or {'system': package.systeminstruks, 'user': package.brukermelding,
                                     'schema': package.svarskjema}
    return len(json.dumps(wire, ensure_ascii=False).encode('utf-8'))


def prepare(plan, document, package):
    budget = plan.motorinnstillinger.get('input_budget_bytes', 60000)
    mode = 'inline'
    if size(package) > budget and package.kjoreparametre.get('file_tools'):
        # Keep the complete source and unit map in this call's workspace. The
        # same worker chooses how to read it; no lossy intermediate summaries.
        package = replace(package, brukermelding=(
            f'Source file: {document["navn"]} (ID {document["id"]}, SHA-256 {document["sha256"]}).\n'
            'Use SOURCE_GUIDE.md and the searchable plain-text source chunks in your working directory. '
            'Read the units needed for the agreed whole-file task; inspect all chunks when complete coverage is required. '
            'Use the original file for visual context when needed. Report only units actually read.'), api_foresporsel=None)
        mode = 'file'
    if size(package) > budget:
        raise ValueError('Input exceeds input_budget_bytes. Increase the agreed budget or use a file-capable CLI reader. '
                         'No task execution or automatic summarisation was performed.')
    return package, {'mode': mode, 'calls': 1, 'input_bytes': size(package), 'input_budget_bytes': budget}


def preview(plan, document, package):
    package, processing = prepare(plan, document, package)
    return {**package.til_dict(), 'processing': processing}


def execute(plan, document, package, adapter, stop, directory):
    package, _ = prepare(plan, document, package)
    return adapter.kjor(package, plan.modell, stop, str(directory))
