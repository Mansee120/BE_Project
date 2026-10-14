"""
document_gap_agent.py  (Agent 10/10)
------------------------------------
Analyses the *document* dimension of a case — the other place where YojanaBench
goes beyond a plain eligibility checker.

It answers three practical questions:
  * Which required documents are still missing?
  * Will submitting them actually change the verdict, or is the case going to
    fail on eligibility regardless?
  * Which additional *field values* are still unknown (driving needs_info)?

This turns the abstract "needs_info" verdict into a concrete, prioritised
to-do list for the applicant.
"""
from .counterfactual_agent import FIELD_META


class DocumentGapAgent:
    def __init__(self, corpus):
        self.corpus = corpus

    def _field_gaps(self, entitlement_result):
        """Fields whose value was unknown (None clause results)."""
        gaps = []
        for clause in entitlement_result.get("eligibility", {}).get("clauses", []):
            if clause.get("mandatory", True) and clause["result"] is None:
                gaps.append(clause.get("clause_id"))
        return gaps

    def _unknown_fields(self, scheme, entitlement_result):
        fields = set()
        clauses = {c["clause_id"]: c for c in
                   entitlement_result.get("eligibility", {}).get("clauses", [])}
        for clause in scheme["eligibility_clauses"]:
            det = clauses.get(clause.get("clause_id"))
            if det and det.get("mandatory", True) and det["result"] is None:
                # collect leaf fields
                stack = [clause]
                while stack:
                    c = stack.pop()
                    if c.get("operator") in ("and", "or") and "clauses" in c:
                        stack.extend(c["clauses"])
                    elif c.get("field"):
                        fields.add(FIELD_META.get(c["field"], {}).get("label", c["field"]))
        return sorted(fields)

    def run(self, case: dict, entitlement_result: dict, verification: dict = None) -> dict:
        scheme = self.corpus.get_scheme(case["scheme_id"])
        missing = case.get("missing_documents", []) or []
        assumed = case.get("documents_assumed_complete", False)
        underlying = entitlement_result["eligibility_decision"]
        unknown_fields = self._unknown_fields(scheme, entitlement_result)

        if assumed or not missing:
            resolution = ("All required documents are available."
                          if assumed else "No mandatory documents are missing.")
            if unknown_fields:
                resolution += (" Additional information still required: "
                               + ", ".join(unknown_fields) + ".")
            return {
                "has_gap": len(unknown_fields) > 0,
                "gate_blocking": False,
                "eligibility_without_docs": underlying,
                "missing_documents": [],
                "documents": [],
                "unknown_fields": unknown_fields,
                "verdict_if_docs_complete": underlying,
                "resolution": resolution,
            }

        documents = []
        for i, name in enumerate(missing):
            documents.append({
                "name": name,
                "priority": i + 1,
                "remaining_after": len(missing) - 1,
                "alone_unblocks": len(missing) == 1,
            })

        if underlying == "ineligible":
            verdict = "ineligible"
            resolution = ("Submitting documents will not change the outcome: the "
                          "mandatory eligibility criteria are not met.")
        elif underlying == "needs_info":
            verdict = "needs_info"
            resolution = ("Provide the missing documents and the missing field values "
                          "to reach a decision.")
        else:
            verdict = "eligible"
            resolution = (f"Submit all {len(missing)} missing mandatory document(s) "
                          f"to become eligible.")

        return {
            "has_gap": True,
            "gate_blocking": True,
            "eligibility_without_docs": underlying,
            "missing_documents": missing,
            "documents": documents,
            "unknown_fields": unknown_fields,
            "verdict_if_docs_complete": verdict,
            "resolution": resolution,
        }
