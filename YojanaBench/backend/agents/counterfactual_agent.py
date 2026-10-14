"""
counterfactual_agent.py  (Agent 9/10)
-------------------------------------
The "how do I qualify?" advisor — the feature that distinguishes YojanaBench
from existing scheme finders (myScheme etc.), which only return a pass/fail.

Given an ineligible or needs_info case, it:

  1. isolates every *violated* or *unknown* mandatory eligibility clause,
  2. turns each into an actionable, human-readable suggestion
     (e.g. "reduce annual income by Rs. 15,000"),
  3. **verifies** the suggestion by re-running the deterministic rule engine on
     a counterfactual applicant profile, so the advice is proven, not guessed,
  4. flags changes that are impossible (e.g. social category) so the applicant is
     told honestly when no change can help.

Everything is computed with the same rule engine used for the verdict, so the
advice can never contradict the decision.
"""
from ..condition_eval import evaluate_all

# Metadata drives the wording of suggestions (labels, units, mutability).
FIELD_META = {
    "age": {"label": "age", "kind": "num", "unit": "years"},
    "annual_income": {"label": "annual income", "kind": "num", "format": "money"},
    "family_size": {"label": "family size", "kind": "num"},
    "disability_percent": {"label": "disability percentage", "kind": "num", "unit": "%"},
    "class_level": {"label": "class level", "kind": "num"},
    "category": {"label": "social category", "kind": "cat", "changeable": False},
    "gender": {"label": "gender", "kind": "cat", "changeable": False},
    "region": {"label": "region", "kind": "cat"},
    "state": {"label": "state", "kind": "cat"},
    "card_type": {"label": "ration card type", "kind": "cat"},
    "house_type": {"label": "house type", "kind": "cat"},
    "education_level": {"label": "education level", "kind": "cat"},
    "bpl": {"label": "BPL household status", "kind": "bool", "changeable": False},
    "is_widow": {"label": "widow status", "kind": "bool", "changeable": False},
    "is_farmer": {"label": "farmer status", "kind": "bool"},
    "is_income_tax_payer": {"label": "income-tax payer status", "kind": "bool",
                            "changeable": False},
    "is_institutional_landholder": {"label": "institutional landholder status",
                                    "kind": "bool", "changeable": False},
    "hosteller": {"label": "hosteller status", "kind": "bool"},
    "owns_pucca_house": {"label": "pucca house ownership", "kind": "bool"},
    "secc_listed": {"label": "SECC listing", "kind": "bool", "changeable": False},
}


class CounterfactualAgent:
    def __init__(self, corpus):
        self.corpus = corpus

    # -- helpers --------------------------------------------------------------
    def _leaves(self, condition: dict):
        """Flatten a compound condition into its leaf comparisons."""
        if condition.get("operator") in ("and", "or") and "clauses" in condition:
            out = []
            for c in condition["clauses"]:
                out.extend(self._leaves(c))
            return out
        return [condition]

    @staticmethod
    def _required_value(clause):
        """Smallest field value that would satisfy the clause, plus direction."""
        op, val = clause.get("operator"), clause.get("value")
        try:
            if op == "gte":
                return val, "increase"
            if op == "gt":
                return (val + 1 if isinstance(val, (int, float)) else val), "increase"
            if op == "lte":
                return val, "decrease"
            if op == "lt":
                return (val - 1 if isinstance(val, (int, float)) else val), "decrease"
            if op == "eq":
                return val, "set"
            if op == "ne":
                if isinstance(val, bool):
                    return (not val), "set"
                if isinstance(val, (int, float)):
                    return val + 1, "set"
                return None, "set"
            if op == "in":
                return (val[0] if isinstance(val, list) and val else None), "set"
            if op == "is_true":
                return True, "set"
            if op == "is_false":
                return False, "set"
        except Exception:
            return None, "set"
        return None, "set"

    @staticmethod
    def _fmt_value(field, value):
        if isinstance(value, bool):
            return "yes" if value else "no"
        meta = FIELD_META.get(field, {})
        if isinstance(value, (int, float)) and meta.get("format") == "money":
            return f"Rs. {value:,.0f}"
        unit = meta.get("unit")
        return f"{value}{(' ' + unit) if unit else ''}"

    def _action_text(self, field, current, required, direction):
        meta = FIELD_META.get(field, {})
        label = meta.get("label", field)
        numeric = (isinstance(current, (int, float)) and isinstance(required, (int, float))
                   and not isinstance(current, bool) and not isinstance(required, bool))
        if numeric and current != required:
            diff = required - current
            if field == "age" and diff > 0:
                return (f"wait until age {int(required)} (currently {int(current)}, "
                        f"+{int(diff)} years)")
            verb = "reduce" if diff < 0 else "increase"
            if meta.get("format") == "money":
                amount = f"Rs. {abs(diff):,.0f}"
            else:
                unit = meta.get("unit")
                amount = f"{abs(diff)}{(' ' + unit) if unit else ''}"
            return (f"{verb} {label} from {self._fmt_value(field, current)} to "
                    f"{self._fmt_value(field, required)} ({verb} by {amount})")
        return f"set {label} to {self._fmt_value(field, required)}"

    def _suggestion(self, applicant, clause, leaf):
        field = leaf.get("field")
        current = applicant.get(field)
        required, direction = self._required_value(leaf)
        meta = FIELD_META.get(field, {})
        changeable = meta.get("changeable", True)
        # Age can only move forward in time.
        if field == "age" and direction == "decrease":
            changeable = False
        action = (f"provide a value for {meta.get('label', field)}"
                  if current is None
                  else self._action_text(field, current, required, direction))
        return {
            "clause_id": clause.get("clause_id"),
            "text": clause.get("text"),
            "field": field,
            "operator": leaf.get("operator"),
            "current": current,
            "required": required,
            "changeable": changeable,
            "action": action,
            "alone_sufficient": False,
        }

    # -- public ---------------------------------------------------------------
    def run(self, case: dict, entitlement_result: dict) -> dict:
        scheme = self.corpus.get_scheme(case["scheme_id"])
        applicant = case["applicant"]
        clauses = scheme["eligibility_clauses"]
        detail = entitlement_result["eligibility"]
        current = entitlement_result["eligibility_decision"]

        if current == "eligible":
            return {
                "current_decision": "eligible",
                "feasible": True,
                "min_changes": 0,
                "can_flip_alone": [],
                "suggestions": [],
                "applied_changes": {},
                "missing_info_fields": [],
                "blockers": [],
                "summary": "The applicant already satisfies all mandatory criteria.",
            }

        suggestions = []
        unknown_fields = set()
        blockers = []
        changes = {}

        for clause, det in zip(clauses, detail["clauses"]):
            if not det.get("mandatory", True) or det["result"] is True:
                continue
            if det["result"] is None:          # unknown -> need more information
                for leaf in self._leaves(clause):
                    field = leaf.get("field")
                    if not field:
                        continue
                    unknown_fields.add(field)
                    meta = FIELD_META.get(field, {})
                    suggestions.append({
                        "clause_id": clause.get("clause_id"),
                        "text": clause.get("text"),
                        "field": field,
                        "operator": leaf.get("operator"),
                        "current": applicant.get(field),
                        "required": None,
                        "changeable": True,
                        "kind": "missing_info",
                        "action": f"provide a value for {meta.get('label', field)}",
                        "alone_sufficient": False,
                    })
                continue
            # result is False -> violated clause(s)
            for leaf in self._leaves(clause):
                sug = self._suggestion(applicant, clause, leaf)
                if not sug["clause_id"]:
                    sug["clause_id"] = clause.get("clause_id")
                if not sug["changeable"]:
                    blockers.append(sug)
                elif sug["required"] is not None:
                    changes[sug["field"]] = sug["required"]
                suggestions.append(sug)

        # -- verify: apply every actionable change and re-evaluate --------------
        # Unknown fields are treated as "information to provide", so feasibility
        # only depends on eliminating all *known* violations (no False results).
        trial = dict(applicant)
        trial.update(changes)
        verified = evaluate_all(trial, clauses)
        scenario_ok = not verified["any_false"]

        # -- which single change clears the known violations on its own? --------
        can_flip_alone = []
        for sug in suggestions:
            if sug.get("kind") == "missing_info" or not sug["changeable"] \
                    or sug["required"] is None:
                continue
            probe = dict(applicant)
            probe[sug["field"]] = sug["required"]
            r = evaluate_all(probe, clauses)
            if not r["any_false"]:
                sug["alone_sufficient"] = True
                can_flip_alone.append(sug["field"])

        feasible = not blockers and scenario_ok

        # -- human summary ------------------------------------------------------
        if feasible:
            parts = [s["action"] for s in suggestions
                     if s.get("kind") != "missing_info"
                     and s["changeable"] and s["required"] is not None]
            if parts:
                summary = "To become eligible: " + "; ".join(parts) + "."
                if unknown_fields:
                    labels = ", ".join(FIELD_META.get(f, {}).get("label", f)
                                       for f in sorted(unknown_fields))
                    summary += f" Also provide: {labels}."
            elif unknown_fields:
                labels = ", ".join(FIELD_META.get(f, {}).get("label", f)
                                   for f in sorted(unknown_fields))
                summary = f"Provide these details to reach a decision: {labels}."
            else:
                summary = "All eligibility criteria are met; no profile change is needed."
        elif blockers:
            fields = ", ".join(FIELD_META.get(b["field"], {}).get("label", b["field"])
                               for b in blockers)
            summary = (f"Cannot qualify by changing inputs: {fields} "
                       f"cannot be modified.")
        else:
            summary = ("Provide additional information to determine whether a change "
                       "would help.")

        return {
            "current_decision": current,
            "feasible": feasible,
            "min_changes": len(changes),
            "can_flip_alone": can_flip_alone,
            "suggestions": suggestions,
            "applied_changes": changes,
            "missing_info_fields": sorted(unknown_fields),
            "blockers": [b["text"] for b in blockers],
            "summary": summary,
        }
