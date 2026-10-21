"""
verification_agent.py  (Agent 5/8)
----------------------------------
Independent cross-check agent.

It re-derives the eligibility decision from the raw clauses using its own logic
(so it is a genuine second opinion, not a copy of the entitlement agent), checks
the document checklist, and reports whether the two agents agree. A disagreement
forces the Orchestrator to raise the human-approval gate.

It also runs the document-integrity checker (fake/tampered-document detection:
impossible values, cross-field contradictions, claims without backing evidence).
High-severity integrity flags raise the human-approval gate in the Orchestrator.
"""
from ..condition_eval import evaluate
from ..document_integrity import check_integrity


class VerificationAgent:
    def __init__(self, corpus):
        self.corpus = corpus

    def _independent_decision(self, scheme, applicant):
        """A deliberately separate implementation of the eligibility check."""
        verdict = "eligible"
        for clause in scheme["eligibility_clauses"]:
            if not clause.get("mandatory", True):
                continue
            res = evaluate(applicant, clause)
            if res is False:
                return "ineligible"
            if res is None:
                verdict = "needs_info"
        return verdict

    def run(self, case: dict, entitlement_result: dict) -> dict:
        scheme = self.corpus.get_scheme(case["scheme_id"])
        applicant = case["applicant"]

        independent = self._independent_decision(scheme, applicant)
        primary = entitlement_result["eligibility_decision"]
        agree = independent == primary

        missing_docs = case.get("missing_documents", [])
        docs_ok = len(missing_docs) == 0

        integrity = check_integrity(
            applicant, scheme,
            submitted_documents=case.get("submitted_documents"),
            documents_assumed_complete=case.get("documents_assumed_complete", True),
            include_missing=False,  # intake already reports missing documents
        )

        flags = []
        if not docs_ok:
            flags.append(f"Missing mandatory documents: {', '.join(missing_docs)}")
        if not agree:
            flags.append(
                f"Cross-check disagreement: entitlement agent says '{primary}', "
                f"verification agent says '{independent}'"
            )
        for item in integrity:
            flags.append(f"[{item['severity']}] {item['detail']}")

        return {
            "independent_decision": independent,
            "entitlement_decision": primary,
            "cross_check_agree": agree,
            "documents_ok": docs_ok,
            "missing_documents": missing_docs,
            "integrity_flags": integrity,
            "flags": flags,
        }
