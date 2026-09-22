"""Requirements for running a structured plan; uncertainty in sources is not a failure."""

from .modell import Plan


def plan_problem(plan: Plan) -> str | None:
    if not plan.formaal.strip():
        return 'The analysis purpose is missing.'
    if plan.is_task:
        from .task_contract import problem
        return problem(plan)
    if not plan.kriterier:
        return 'At least one criterion is required.'
    ids = [criterion.id.strip() for criterion in plan.kriterier]
    if not all(ids) or len(ids) != len(set(ids)):
        return 'Criterion IDs must be nonempty and unique.'
    for criterion in plan.kriterier:
        if not criterion.sporsmal.strip():
            return f'Criterion {criterion.id} has no question.'
        labels = criterion.tillatte_svar
        if not labels or not all(label.strip() for label in labels) or len(labels) != len(set(labels)):
            return f'Criterion {criterion.id} needs nonempty, unique allowed answers.'
        if not set(criterion.krever_belegg_ved).issubset(labels):
            return f'Criterion {criterion.id} requires evidence for an answer that is not allowed.'
    return None
