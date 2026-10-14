"""
entitlement_agent.py  (Agent 4/8)
---------------------------------
Computes (a) the eligibility decision and (b) the exact monetary/quantity
entitlement for a case.

Eligibility is decided by evaluating the scheme's mandatory clauses with the
tri-state rule engine. Entitlement is computed by deterministic Python
arithmetic - never by an LLM - which is precisely how the design avoids
hallucinated maths.
"""
from ..condition_eval import evaluate, evaluate_all


class EntitlementAgent:
    def __init__(self, corpus):
        self.corpus = corpus

    # -- eligibility ----------------------------------------------------------
    def _decide_eligibility(self, scheme, applicant):
        result = evaluate_all(applicant, scheme["eligibility_clauses"])
        if result["any_false"]:
            decision = "ineligible"
        elif result["any_unknown"]:
            decision = "needs_info"
        else:
            decision = "eligible"
        return decision, result

    # -- entitlement arithmetic ----------------------------------------------
    @staticmethod
    def _compute_rule(rule, applicant):
        """Return (value, formula_text) for one entitlement rule using code maths."""
        compute = rule["compute"]
        kind = compute["type"]

        if kind == "fixed_amount":
            value = compute["value"]
            formula = f"{value} {compute['unit']} (fixed entitlement)"
            return value, formula

        if kind == "per_member":
            members = applicant.get("family_size", 1)
            value = compute["value"] * members
            formula = (f"{compute['value']} x {members} members = {value} {compute['unit']}"
                       f" (per-member entitlement)")
            return value, formula

        if kind == "wage_days":
            days = compute.get("days", 100)
            wage = compute["value"]
            value = wage * days
            formula = f"{wage} {compute['unit']} x {days} days = {value} INR/year"
            return value, formula

        if kind == "coverage":
            value = compute["value"]
            formula = f"{value} {compute['unit']} (insurance coverage)"
            return value, formula

        if kind == "tiered":
            for tier in compute.get("tiers", []):
                cond = tier.get("when")
                if cond is None or evaluate(applicant, cond) is True:
                    value = tier["value"]
                    return value, f"{value} {tier.get('unit', '')} (tiered entitlement)"
            return 0, "no matching tier"

        return 0, "unknown computation type"

    def _compute_entitlement(self, scheme, applicant):
        for rule in scheme["entitlement_rules"]:
            cond = rule.get("when")
            matched = True if cond is None else evaluate(applicant, cond)
            if matched is True:
                value, formula = self._compute_rule(rule, applicant)
                return {
                    "rule_id": rule["rule_id"],
                    "computed_entitlement": value,
                    "entitlement_unit": rule["compute"].get("unit"),
                    "per_period": rule["compute"].get("per_period"),
                    "formula": formula,
                    "clause_ids": rule.get("clause_ids", [rule["rule_id"]]),
                    "text": rule["text"],
                }
        return {
            "rule_id": None,
            "computed_entitlement": 0,
            "entitlement_unit": None,
            "per_period": None,
            "formula": "no entitlement rule matched the applicant profile",
            "clause_ids": [],
            "text": "",
        }

    def _compute_naive(self, scheme, applicant):
        """Proxy for "LLM-only maths" used in the ablation study.

        Instead of applying the correct formula (tier selection, per-member
        multiplication, wage x days), it blindly takes the nominal value of the
        first entitlement rule. This mimics an LLM reading a clause and grabbing
        the headline number without doing the conditional arithmetic - which is
        exactly the failure mode the deterministic Entitlement agent prevents.
        """
        if not scheme["entitlement_rules"]:
            return None
        rule = scheme["entitlement_rules"][0]
        value = rule["compute"].get("value")
        return {
            "rule_id": rule["rule_id"] + " (naive)",
            "computed_entitlement": value,
            "entitlement_unit": rule["compute"].get("unit"),
            "per_period": rule["compute"].get("per_period"),
            "formula": f"naive estimate: took the first clause value {value} "
                       f"(no conditional/per-member maths)",
            "clause_ids": rule.get("clause_ids", [rule["rule_id"]]),
            "text": rule["text"],
            "naive": True,
        }

    # -- public ---------------------------------------------------------------
    def run(self, case: dict, naive: bool = False) -> dict:
        scheme = self.corpus.get_scheme(case["scheme_id"])
        applicant = case["applicant"]

        decision, eligibility = self._decide_eligibility(scheme, applicant)

        entitlement = None
        if decision == "eligible":
            entitlement = (self._compute_naive(scheme, applicant) if naive
                           else self._compute_entitlement(scheme, applicant))

        return {
            "eligibility_decision": decision,
            "eligibility": eligibility,
            "entitlement": entitlement,
        }
