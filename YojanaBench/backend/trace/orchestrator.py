"""
Trace orchestrator (money-trace, Agent 6/7)
-------------------------------------------
Fuses the intake, lookup, credit, reconciliation and fraud findings into one
human-readable trace result with a verdict, a confidence and a recommended
action. This is the object the UI renders and the complaint stores.
"""

# verdict -> (headline, recommended action)
_PLAYBOOK = {
    "received": (
        "Money reached the beneficiary account",
        "No action needed. The credit is present in the beneficiary's own "
        "account for the matching UTR."),
    "not_credited": (
        "Government marked it paid, but no credit reached the account",
        "Raise a bank credit-advice request and escalate to the scheme nodal "
        "officer with the UTR; the amount must be re-credited or traced."),
    "partial": (
        "Only part of the sanctioned amount was credited",
        "Ask the bank for the deduction details and escalate the shortfall to "
        "the scheme authority for re-credit."),
    "diverted": (
        "Money was credited to the wrong account - suspected diversion",
        "Freeze/flag the receiving account, register a fraud complaint with the "
        "bank and the district grievance cell, and seek re-credit to the "
        "beneficiary's own account."),
    "failed": (
        "The credit failed and reverted to the scheme",
        "Correct the bank account / KYC details and request re-issue of the "
        "payment."),
    "multiple": (
        "More than one payment matches this complaint",
        "Confirm the exact UTR or period with the beneficiary before acting."),
    "not_found": (
        "No government disbursement record found",
        "Verify the scheme, UTR and beneficiary details; if the scheme shows a "
        "sanction, obtain the payment file from the disbursing authority."),
    "needs_info": (
        "Not enough information to trace the money",
        "Collect the missing details (scheme, UTR or beneficiary id)."),
}


class TraceOrchestrator:
    def run(self, ctx: dict) -> dict:
        lookup = ctx["lookup"]
        credit = ctx["credit"]
        recon = ctx["reconcile"]
        fraud = ctx["fraud"]
        intake = ctx["intake"]

        if not intake["valid"]:
            verdict = "needs_info"
        elif not lookup.get("matched"):
            verdict = "not_found"
        elif len(lookup.get("candidates", [])) > 1 and not intake["complaint"].get("utr"):
            verdict = "multiple"
        elif credit["status"] == "not_credited":
            # Distinguish a returned/failed credit from a silent non-credit.
            txn = lookup["matched"]
            verdict = "failed" if txn.get("status") == "failed" else "not_credited"
        elif credit["status"] == "diverted":
            verdict = "diverted"
        elif recon.get("partial"):
            verdict = "partial"
        else:
            verdict = "received"

        headline, action = _PLAYBOOK[verdict]

        # Confidence: start high, drop for ambiguity and missing detail.
        confidence = 0.95
        if verdict == "multiple":
            confidence = 0.55
        if verdict == "not_found":
            confidence = 0.5
        if verdict == "needs_info":
            confidence = 0.3
        if verdict in ("diverted", "not_credited") and not lookup["matched"].get("utr"):
            confidence -= 0.1
        confidence = round(max(0.1, min(confidence, 0.99)), 2)

        money_reached = verdict == "received"

        return {
            "verdict": verdict,
            "headline": headline,
            "confidence": confidence,
            "money_reached_beneficiary": money_reached,
            "recommended_action": action,
            "sanctioned_amount": recon.get("sanctioned_amount"),
            "credited_amount": recon.get("credited_amount"),
            "shortfall": recon.get("shortfall"),
            "credited_to_account_last4": credit.get("credited_to_account_last4"),
            "expected_account_last4": credit.get("expected_account_last4"),
            "credited_to_name": credit.get("credited_to_name"),
            "diversion": fraud.get("diversion"),
            "mule_ring": fraud.get("mule_ring"),
            "severity": fraud.get("severity"),
            "flags": fraud.get("flags", []) + credit.get("flags", []),
        }
