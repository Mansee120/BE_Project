"""
policy_sandbox.py
-----------------
Policy what-if simulator ("Policy Sandbox") for officials.

Lets a policymaker change one eligibility rule of a scheme (e.g. raise the
income limit from 1.2L to 1.5L, or lower the pension age from 60 to 58) and
immediately see, over the whole benchmark cohort of that scheme:

  * how many verdicts flip (newly eligible / newly ineligible / ...),
  * the total budget impact (sum of computed entitlements before vs after),
  * a per-applicant breakdown of every change.

The simulation reuses the *exact* production rule engine
(`condition_eval`) and the *exact* deterministic entitlement maths
(`EntitlementAgent`) on an in-memory patched copy of the scheme — the
official corpus is never modified, and the maths is never duplicated.
"""
import copy
import json

from .condition_eval import evaluate_all
from .agents.entitlement_agent import EntitlementAgent
from .document_integrity import check_integrity, apply_tamper

# Comparators whose `value` a policy change is allowed to replace.
_PATCHABLE = {"lt", "lte", "gt", "gte", "eq", "ne"}

_DEC_ORDER = ("eligible", "ineligible", "needs_info")


class _SingleSchemeCorpus:
    """Minimal corpus shim so EntitlementAgent can score a patched scheme."""

    def __init__(self, scheme):
        self._scheme = scheme

    def get_scheme(self, scheme_id):
        return self._scheme


# --------------------------- patching helpers ------------------------------
def _coerce_value(sample, new_value):
    """Match the JSON type of the value being replaced (int/float/bool/str)."""
    if isinstance(sample, bool) or isinstance(new_value, bool):
        return bool(new_value) if isinstance(sample, bool) else new_value
    if isinstance(sample, (int, float)) and isinstance(new_value, str):
        try:
            num = float(new_value)
            return int(num) if num == int(num) and not isinstance(sample, float) else num
        except ValueError:
            return new_value
    return new_value


def _patch_condition(cond, field, new_value, location, changes):
    """Recursively replace `value` on every leaf that targets `field`."""
    if not isinstance(cond, dict):
        return
    if cond.get("operator") in ("and", "or"):
        for sub in cond.get("clauses", []):
            _patch_condition(sub, field, new_value, location, changes)
        return
    if cond.get("field") != field or cond.get("operator") not in _PATCHABLE:
        return
    old = cond.get("value")
    cond["value"] = _coerce_value(old, new_value)
    changes.append({
        "location": location,
        "field": field,
        "operator": cond.get("operator"),
        "old_value": old,
        "new_value": cond["value"],
    })


def patch_scheme(scheme: dict, field: str, new_value):
    """Return (patched_deep_copy, list_of_changes). Original is untouched."""
    patched = copy.deepcopy(scheme)
    changes = []

    for clause in patched.get("eligibility_clauses", []):
        _patch_condition(clause, field, new_value,
                         clause.get("clause_id", "?"), changes)

    for rule in patched.get("entitlement_rules", []):
        _patch_condition(rule.get("when"), field, new_value,
                         rule.get("rule_id", "?"), changes)
        for i, tier in enumerate(rule.get("tiers", []) or []):
            _patch_condition(tier.get("when"), field, new_value,
                             f"{rule.get('rule_id', '?')}-tier{i + 1}", changes)

    return patched, changes


# --------------------------- the simulator ---------------------------------
class PolicySandbox:
    def __init__(self, pipeline=None):
        # Lazy import avoids a circular dependency at module load time.
        if pipeline is None:
            from .pipeline import pipeline as _default
            pipeline = _default
        self.pipeline = pipeline
        self.corpus = pipeline.corpus

    # -- what can be changed -------------------------------------------------
    def fields(self, scheme_id: str) -> dict:
        """Numeric/leaf fields referenced by the scheme's rules, with current
        thresholds — used by the dashboard to populate the picker."""
        scheme = self.corpus.get_scheme(scheme_id)
        if scheme is None:
            raise ValueError(f"Unknown scheme_id: {scheme_id}")

        seen = {}

        def visit(cond):
            if not isinstance(cond, dict):
                return
            if cond.get("operator") in ("and", "or"):
                for sub in cond.get("clauses", []):
                    visit(sub)
                return
            f = cond.get("field")
            if not f or cond.get("operator") not in _PATCHABLE:
                return
            entry = seen.setdefault(f, {"field": f, "thresholds": []})
            entry["thresholds"].append({
                "operator": cond.get("operator"),
                "value": cond.get("value"),
            })

        for clause in scheme.get("eligibility_clauses", []):
            visit(clause)
        for rule in scheme.get("entitlement_rules", []):
            visit(rule.get("when"))
            for tier in rule.get("tiers", []) or []:
                visit(tier.get("when"))

        fields = sorted(seen.values(), key=lambda x: x["field"])
        for entry in fields:
            values = [t["value"] for t in entry["thresholds"]
                      if isinstance(t["value"], (int, float))
                      and not isinstance(t["value"], bool)]
            entry["current_value"] = values[0] if values else entry["thresholds"][0]["value"]
            entry["is_numeric"] = bool(values)
        return {"scheme_id": scheme_id, "scheme_name": scheme.get("name"),
                "fields": fields}

    # -- the cohort ----------------------------------------------------------
    def _cohort(self, scheme_id: str):
        """Unique applicant profiles from the QA benchmark for this scheme."""
        data = self.pipeline._load_benchmark()
        out, seen = [], set()
        for item in data.get("items", []):
            if item.get("scheme_id") != scheme_id or not item.get("applicant"):
                continue
            key = json.dumps(item["applicant"], sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            out.append({"item_id": item.get("id"),
                        "label": item.get("question", "")[:70],
                        "applicant": item["applicant"],
                        "submitted_documents": item.get("submitted_documents")})
        return out

    # -- one verdict + entitlement, using the production agents -------------
    def _judge(self, scheme, applicant):
        agent = EntitlementAgent(_SingleSchemeCorpus(scheme))
        result = agent.run({"scheme_id": scheme["scheme_id"],
                            "applicant": applicant})
        ent = result.get("entitlement") or {}
        return {
            "decision": result["eligibility_decision"],
            "entitlement": ent.get("computed_entitlement") or 0,
            "unit": ent.get("entitlement_unit"),
        }

    # -- document-tamper simulation (fake / omitted documents) ---------------
    def simulate_document(self, scheme_id: str, document: str, action: str) -> dict:
        """Simulate one forged or omitted document across the whole cohort.

        action="omit"  the document claimed on the form was never submitted
        action="forge" the document's certified facts are doctored so the
                       declarations contradict the rest of the application

        Reports how many members the integrity checker catches, which flag
        codes fire, and any verdict / budget movement caused by the tampered
        declarations.
        """
        scheme = self.corpus.get_scheme(scheme_id)
        if scheme is None:
            raise ValueError(f"Unknown scheme_id: {scheme_id}")
        if action not in ("omit", "forge"):
            raise ValueError(f"Unknown action '{action}' (use 'omit' or 'forge').")

        mandatory = [d["name"] for d in scheme.get("required_documents", [])
                     if d.get("mandatory", True)]
        all_docs = [d["name"] for d in scheme.get("required_documents", [])]
        if not document:
            raise ValueError("A document name is required for document mode.")
        if document not in all_docs and not any(
                document.lower() in k.lower() for k in all_docs):
            raise ValueError(
                f"'{document}' is not a required document of {scheme_id}.")
        if action == "omit" and not all_docs:
            raise ValueError(f"{scheme_id} has no documents to omit.")

        # Probe once so every member is tampered the same way and the response
        # can describe the transformation without depending on a member.
        _, _, probe_changes = apply_tamper({}, all_docs, document, action)
        strategy = next((c["new_value"] for c in probe_changes
                         if c["location"] == "strategy"), None)

        cohort = self._cohort(scheme_id)
        rows = []
        transitions = {}
        flags_detected = {}
        flagged_before = flagged_after = 0
        budget_before = budget_after = 0.0
        n_before_elig = n_after_elig = 0

        for member in cohort:
            applicant = member["applicant"]
            # Baseline submission: the applicant's own list if given, else a
            # complete mandatory checklist (a fully submitted application).
            base_docs = member.get("submitted_documents")
            if base_docs is None:
                base_docs = mandatory

            before_flags = check_integrity(applicant, scheme, base_docs,
                                           documents_assumed_complete=False,
                                           include_missing=False)
            try:
                tampered_app, tampered_docs, _ = apply_tamper(
                    applicant, base_docs, document, action)
            except ValueError:
                # e.g. omitting a document this member never submitted:
                # nothing changes for this member.
                tampered_app, tampered_docs = applicant, base_docs
            after_flags = check_integrity(tampered_app, scheme, tampered_docs,
                                          documents_assumed_complete=False,
                                          include_missing=(action == "omit"))

            before = self._judge(scheme, applicant)
            after = self._judge(scheme, tampered_app)

            b, a = before["decision"], after["decision"]
            transitions[f"{b}->{a}"] = transitions.get(f"{b}->{a}", 0) + 1
            if b == "eligible":
                n_before_elig += 1
                budget_before += float(before["entitlement"] or 0)
            if a == "eligible":
                n_after_elig += 1
                budget_after += float(after["entitlement"] or 0)

            before_codes = {f["code"] for f in before_flags}
            new_codes = [f["code"] for f in after_flags
                         if f["code"] not in before_codes]
            for code in new_codes:
                flags_detected[code] = flags_detected.get(code, 0) + 1
            if before_flags:
                flagged_before += 1
            if after_flags:
                flagged_after += 1

            changed = bool(new_codes) or b != a or \
                before["entitlement"] != after["entitlement"]
            rows.append({
                "item_id": member["item_id"],
                "label": member["label"],
                "before": b, "after": a,
                "entitlement_before": before["entitlement"],
                "entitlement_after": after["entitlement"],
                "unit": after["unit"] or before["unit"],
                "flags_before": len(before_flags),
                "flags_after": len(after_flags),
                "new_flags": new_codes,
                "changed": changed,
            })

        flips = {k: v for k, v in transitions.items()
                 if k.split("->")[0] != k.split("->")[1]}
        affected = [r for r in rows if r["changed"]]
        delta = budget_after - budget_before

        return {
            "mode": "document",
            "scheme_id": scheme_id,
            "scheme_name": scheme.get("name"),
            "document": document,
            "action": action,
            "strategy": strategy,
            "changes_applied": probe_changes,
            "cohort_size": len(cohort),
            "before": {"eligible": n_before_elig,
                       "budget_total": round(budget_before, 2),
                       "flagged": flagged_before},
            "after": {"eligible": n_after_elig,
                      "budget_total": round(budget_after, 2),
                      "flagged": flagged_after},
            "newly_eligible": transitions.get("ineligible->eligible", 0) + \
                              transitions.get("needs_info->eligible", 0),
            "newly_ineligible": transitions.get("eligible->ineligible", 0) + \
                                transitions.get("eligible->needs_info", 0),
            "budget_delta": round(delta, 2),
            "budget_delta_pct": (round(100.0 * delta / budget_before, 2)
                                 if budget_before else None),
            "flags_detected": flags_detected,
            "detected_count": sum(1 for r in rows if r["new_flags"]),
            "transitions": transitions,
            "flips": flips,
            "affected_count": len(affected),
            "affected": affected,
            "rows": rows,
        }
    def simulate(self, scheme_id: str, field: str, new_value) -> dict:
        scheme = self.corpus.get_scheme(scheme_id)
        if scheme is None:
            raise ValueError(f"Unknown scheme_id: {scheme_id}")

        patched, changes = patch_scheme(scheme, field, new_value)
        if not changes:
            raise ValueError(
                f"No rule of {scheme_id} compares the field '{field}'. "
                "Pick a field offered by GET /api/sandbox/fields.")

        cohort = self._cohort(scheme_id)
        rows = []
        transitions = {}
        budget_before = budget_after = 0.0
        n_before_elig = n_after_elig = 0

        for member in cohort:
            before = self._judge(scheme, member["applicant"])
            after = self._judge(patched, member["applicant"])

            b, a = before["decision"], after["decision"]
            transitions[f"{b}->{a}"] = transitions.get(f"{b}->{a}", 0) + 1
            if b == "eligible":
                n_before_elig += 1
                budget_before += float(before["entitlement"] or 0)
            if a == "eligible":
                n_after_elig += 1
                budget_after += float(after["entitlement"] or 0)

            rows.append({
                "item_id": member["item_id"],
                "label": member["label"],
                "before": b, "after": a,
                "entitlement_before": before["entitlement"],
                "entitlement_after": after["entitlement"],
                "unit": after["unit"] or before["unit"],
                "changed": (b != a) or (before["entitlement"] != after["entitlement"]),
            })

        flips = {k: v for k, v in transitions.items()
                 if k.split("->")[0] != k.split("->")[1]}
        affected = [r for r in rows if r["changed"]]

        delta = budget_after - budget_before
        return {
            "mode": "rule",
            "scheme_id": scheme_id,
            "scheme_name": scheme.get("name"),
            "field": field,
            "new_value": new_value,
            "changes_applied": changes,
            "cohort_size": len(cohort),
            "before": {"eligible": n_before_elig,
                       "budget_total": round(budget_before, 2)},
            "after": {"eligible": n_after_elig,
                      "budget_total": round(budget_after, 2)},
            "newly_eligible": transitions.get("ineligible->eligible", 0) + \
                              transitions.get("needs_info->eligible", 0),
            "newly_ineligible": transitions.get("eligible->ineligible", 0) + \
                                transitions.get("eligible->needs_info", 0),
            "budget_delta": round(delta, 2),
            "budget_delta_pct": (round(100.0 * delta / budget_before, 2)
                                 if budget_before else None),
            "transitions": transitions,
            "flips": flips,
            "affected_count": len(affected),
            "affected": affected,
            "rows": rows,
        }


# Shared singleton used by the FastAPI app.
sandbox = PolicySandbox()
