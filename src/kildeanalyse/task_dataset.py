"""Deterministic, relational views of task results. Never infer new findings."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field


def pointer(parts):
    return ''.join('/' + str(p).replace('~', '~0').replace('/', '~1') for p in parts)


@dataclass
class Column:
    path: tuple
    role: str = 'value'
    schema: dict = field(default_factory=dict)

    @property
    def key(self):
        return self.path, self.role


@dataclass
class Table:
    path: tuple
    schema: dict = field(default_factory=dict)
    repeated: bool = False
    columns: dict = field(default_factory=OrderedDict)
    rows: list = field(default_factory=list)

    def column(self, path, spec=None, role='value'):
        key = path, role
        self.columns.setdefault(key, Column(path, role, spec or {}))
        return key


def describe(output_schema):
    """Plan-time table/variable preview, including empty collections."""
    tables = OrderedDict()

    def table(path, spec, repeated=False):
        if path not in tables:
            tables[path] = Table(path, spec or {}, repeated)
        return tables[path]

    def fields(target, spec, path=()):
        if not isinstance(spec, dict):
            return
        kind = spec.get('type')
        types = kind if isinstance(kind, list) else [kind]
        if 'object' in types:
            for name, child in spec.get('properties', {}).items():
                fields(target, child, path + (name,))
        elif 'array' in types:
            target.column(path, spec, 'count')
            child = table(target.path + path + ('*',), spec, True)
            fields(child, spec.get('items', {}))
        else:
            target.column(path, spec)

    spec = output_schema or {'type': 'string', 'description': 'Prose result; no variables inferred from its text.'}
    kind = spec.get('type')
    if kind == 'array' or (isinstance(kind, list) and 'array' in kind):
        main = table((), spec, True)
        fields(main, spec.get('items', {}))
    else:
        fields(table((), spec), spec)
    return tables


def plan_preview(plan):
    return {
        'workbook': 'Resultater.xlsx' if plan.sprak == 'nb' else 'Results.xlsx',
        'structured': plan.output_schema is not None,
        'row_unit': 'One row per run in Results, including failures; row_scope=documents selects the newest planned run per document.',
        'tables': [{'path': pointer(t.path), 'name': t.schema.get('title'),
                    'row_unit': t.schema.get('description') or ('One result item per file' if t.repeated else 'One result per file'),
                    'variables': [{'path': pointer(c.path), 'role': c.role,
                                   'label': c.schema.get('title'), 'type': c.schema.get('type'),
                                   'description': c.schema.get('description', '')}
                                  for c in t.columns.values()]} for t in describe(plan.output_schema).values()],
        'notes': ['Choose task-specific variables, types, units/scales and missing-value rules before approval.',
                  'Repeated records default to linked detail sheets; list_layout=inline also shows them in the main row.',
                  'Repeated collections never multiply the rows in Results or create a Cartesian product.',
                  'Prose-only results remain text; exports do not invent analytical variables.'],
    }


def add_result(tables, value, context):
    """Append one accepted result. Each source array has its own parent-linked rows."""
    root = tables[()]
    sequence = 0

    def emit(target, item, parent='', ordinal=1, location=()):
        nonlocal sequence
        sequence += 1
        record = {**context, 'record_id': f'{context["attempt_id"]}:{sequence}',
                  'parent_id': parent, 'ordinal': ordinal, 'result_path': pointer(location),
                  'values': {}, 'nulls': [], 'present': set()}
        target.rows.append(record)

        def visit(node, path=()):
            if isinstance(node, dict):
                for key, child in node.items():
                    visit(child, path + (key,))
            elif isinstance(node, list):
                key = target.column(path, role='count')
                record['values'][key] = len(node)
                record['present'].add(key)
                child_path = target.path + path + ('*',)
                child = tables.setdefault(child_path, Table(child_path, repeated=True))
                for i, entry in enumerate(node):
                    emit(child, entry, record['record_id'], i + 1, location + path + (i,))
            else:
                key = (path, 'count') if node is None and (path, 'count') in target.columns else target.column(path)
                record['values'][key] = node
                record['present'].add(key)
                if node is None:
                    record['nulls'].append(pointer(path) or '/')

        visit(item)

    if isinstance(value, list):
        root.repeated = True
        for i, item in enumerate(value):
            emit(root, item, ordinal=i + 1, location=(i,))
    elif value is not None or not root.repeated:
        emit(root, value)


def source_locations(table, row, plan, document):
    """Resolve only unit fields declared by quote_checks; never guess integer meaning."""
    locations = []
    units = {u['nr']: u.get('source', {}).get('location') or f'Page {u["nr"]}' for u in document['sider']}
    table_pointer = pointer(table.path[:-1]) if table.path and table.path[-1] == '*' else pointer(table.path)
    for rule in plan.quote_checks:
        if rule['path'] != table_pointer:
            continue
        unit = row['values'].get(((rule['unit_field'],), 'value'))
        if type(unit) is int and unit in units:
            locations.append(units[unit])
    return '\n'.join(dict.fromkeys(locations))
