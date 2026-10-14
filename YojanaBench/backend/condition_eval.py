"""
condition_eval.py
-----------------
A tiny deterministic rule evaluator used by the Entitlement and Verification
agents.

Every eligibility clause / entitlement `when` in the dataset is expressed as a
condition dictionary, e.g.:

    {"field": "age", "operator": "gte", "value": 60}

Conditions may be compounded with `{"operator": "and"|"or", "clauses": [...]}`.

`evaluate` returns a *tri-state* result:
    True  -> condition satisfied
    False -> condition violated
    None  -> field not present in the applicant ("unknown" -> needs_info)

Using deterministic code (rather than an LLM) for comparisons keeps the audit
maths hallucination-free, exactly as described in the project design.
"""

# Operators supported by the mini rule language
_COMPARATORS = {
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "contains": lambda a, b: b in a,
}


def evaluate(applicant: dict, condition: dict):
    """Evaluate a (possibly compound) condition against an applicant profile."""
    operator = condition.get("operator")

    # Compound conditions (and / or) -----------------------------------------
    if operator in ("and", "or"):
        results = [evaluate(applicant, c) for c in condition.get("clauses", [])]
        if operator == "and":
            if any(r is False for r in results):
                return False
            if any(r is None for r in results):
                return None
            return True
        else:  # or
            if any(r is True for r in results):
                return True
            if any(r is None for r in results):
                return None
            return False

    field = condition.get("field")

    # Missing field -> unknown (drives "needs_info") -------------------------
    if field is None or field not in applicant or applicant[field] is None:
        return None

    actual = applicant[field]

    # Boolean helpers ---------------------------------------------------------
    if operator == "is_true":
        return actual is True
    if operator == "is_false":
        return actual is False

    # Normalise string comparisons so "sc" == "SC" ---------------------------
    expected = condition.get("value")
    if isinstance(actual, str) and isinstance(expected, str):
        actual = actual.strip().lower()
        expected = expected.strip().lower()
    elif isinstance(actual, str) and isinstance(expected, list):
        actual = actual.strip().lower()
        expected = [str(e).strip().lower() for e in expected]
    elif isinstance(actual, list) and isinstance(expected, str):
        actual = [str(a).strip().lower() for a in actual]
        expected = expected.strip().lower()

    fn = _COMPARATORS.get(operator)
    if fn is None:
        return None
    try:
        return bool(fn(actual, expected))
    except TypeError:
        # Incompatible types -> treat as unknown rather than crashing the audit
        return None


def evaluate_all(applicant: dict, clauses: list):
    """Evaluate a list of clauses, returning per-clause results and a summary.

    Returns dict:
      clauses: [{clause_id, text, result, mandatory}]
      any_false: True if any mandatory clause is False
      any_unknown: True if any mandatory clause is None
      passed: True if all mandatory clauses are True
    """
    detailed = []
    any_false = False
    any_unknown = False
    for clause in clauses:
        result = evaluate(applicant, clause)
        mandatory = clause.get("mandatory", True)
        detailed.append({
            "clause_id": clause.get("clause_id"),
            "text": clause.get("text"),
            "result": result,
            "mandatory": mandatory,
        })
        if mandatory and result is False:
            any_false = True
        if mandatory and result is None:
            any_unknown = True
    return {
        "clauses": detailed,
        "any_false": any_false,
        "any_unknown": any_unknown,
        "passed": not any_false and not any_unknown,
    }
