"""
orchestrator.py  (Agent 6/8)
----------------------------
Merges every agent output into a single Verdict: decision + explanation +
evidence + confidence. Enforces the human-approval gate whenever confidence is
low or the verification cross-check disagreed. Optionally asks the local LLM to
polish the explanation; otherwise a deterministic template is used.
"""
from .. import config
from ..llm import llm_client


class Orchestrator:
    def __init__(self, corpus):
        self.corpus = corpus

    # -- explanation ----------------------------------------------------------
    def _template_explanation(self, case, decision, eligibility, entitlement,
                              verification) -> str:
        scheme = self.corpus.get_scheme(case["scheme_id"])
        lines = [f"Scheme: {scheme['name']} ({scheme['scheme_id']})."]

        if decision == "eligible":
            lines.append("Verdict: ELIGIBLE - all mandatory eligibility criteria are satisfied.")
            if entitlement:
                lines.append(f"Computed entitlement: {entitlement['formula']}.")
        elif decision == "ineligible":
            violated = [c for c in eligibility["clauses"]
                        if c["mandatory"] and c["result"] is False]
            lines.append("Verdict: INELIGIBLE - mandatory criteria not satisfied:")
            for c in violated:
                lines.append(f"  - [{c['clause_id']}] {c['text']}")
        else:  # needs_info
            lines.append("Verdict: NEEDS INFORMATION - the case cannot be decided yet.")
            if verification["missing_documents"]:
                lines.append(f"  - Missing documents: {', '.join(verification['missing_documents'])}")
            unknown = [c for c in eligibility["clauses"]
                       if c["mandatory"] and c["result"] is None]
            for c in unknown:
                lines.append(f"  - Unverified criterion [{c['clause_id']}]: {c['text']}")
            if not verification["cross_check_agree"]:
                lines.append("  - Agent disagreement requires human review.")
        return "\n".join(lines)

    def _llm_explanation(self, case, decision, eligibility, entitlement):
        scheme = self.corpus.get_scheme(case["scheme_id"])
        prompt = (
            "You are a welfare-scheme audit assistant. Write a concise, neutral "
            "3-4 sentence explanation for the decision below, citing clause IDs.\n\n"
            f"Scheme: {scheme['name']}\nApplicant: {case['applicant']}\n"
            f"Decision: {decision}\n"
            f"Clauses: {[c['clause_id'] for c in eligibility['clauses']]}\n"
        )
        return llm_client.generate(prompt)

    # -- confidence -----------------------------------------------------------
    @staticmethod
    def _confidence(evidence, entitlement_result, verification, decision, docs_explicit):
        conf = 0.5
        if evidence:
            conf += 0.2
        if verification["cross_check_agree"]:
            conf += 0.15
        if decision == "ineligible":
            violated = [c for c in entitlement_result["eligibility"]["clauses"]
                        if c["mandatory"] and c["result"] is False]
            if violated:
                conf += 0.15
        if decision == "eligible" and entitlement_result.get("entitlement"):
            conf += 0.1
        if docs_explicit and verification["documents_ok"]:
            conf += 0.05
        if not verification["cross_check_agree"]:
            conf -= 0.2
        conf = max(0.05, min(0.98, conf))
        return round(conf, 2)

    # -- public ---------------------------------------------------------------
    def run(self, case, evidence, entitlement_result, verification,
            use_llm: bool = False) -> dict:
        primary = entitlement_result["eligibility_decision"]

        if primary == "ineligible":
            decision = "ineligible"
        elif verification["missing_documents"]:
            decision = "needs_info"
        elif not verification["cross_check_agree"]:
            decision = "needs_info"
        elif primary == "needs_info":
            decision = "needs_info"
        else:
            decision = "eligible"

        explanation = self._template_explanation(
            case, decision, entitlement_result["eligibility"],
            entitlement_result.get("entitlement"), verification)

        if use_llm:
            llm_text = self._llm_explanation(
                case, decision, entitlement_result["eligibility"],
                entitlement_result.get("entitlement"))
            if llm_text:
                explanation = llm_text

        evidence_ids = [e["doc_id"] for e in evidence]
        docs_explicit = not case.get("documents_assumed_complete", False)
        confidence = self._confidence(
            evidence, entitlement_result, verification, decision, docs_explicit)

        entitlement = entitlement_result.get("entitlement")
        answer = self._compose_answer(decision, entitlement, verification)

        return {
            "decision": decision,
            "explanation": explanation,
            "evidence_clause_ids": evidence_ids,
            "computed_entitlement": entitlement["computed_entitlement"] if entitlement else None,
            "entitlement_unit": entitlement["entitlement_unit"] if entitlement else None,
            "entitlement_formula": entitlement["formula"] if entitlement else None,
            "confidence": confidence,
            "missing_documents": verification["missing_documents"],
            "human_approval_required": (confidence < config.CONFIDENCE_THRESHOLD
                                        or not verification["cross_check_agree"]),
            "agents_agree": verification["cross_check_agree"],
            "answer": answer,
        }

    @staticmethod
    def _compose_answer(decision, entitlement, verification):
        """A short natural-language answer used by the benchmark scorer (EM/F1)."""
        if decision == "eligible" and entitlement:
            return (f"Eligible. Entitlement: {entitlement['computed_entitlement']} "
                    f"{entitlement['entitlement_unit']}. {entitlement['formula']}")
        if decision == "ineligible":
            return "Ineligible. One or more mandatory eligibility criteria are not satisfied."
        if decision == "needs_info":
            if verification["missing_documents"]:
                return ("Needs information. Missing documents: "
                        + ", ".join(verification["missing_documents"]))
            return "Needs information. Some eligibility criteria could not be verified."
        return decision
