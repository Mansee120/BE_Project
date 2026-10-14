"""
Reconciliation agent (money-trace, Agent 4/7)
--------------------------------------------
Compares the amount the scheme sanctioned with the amount actually credited and
reports any shortfall (round-tripping / deductions / partial disbursement).
"""


class ReconciliationAgent:
    def run(self, ctx: dict) -> dict:
        txn = ctx["lookup"].get("matched") or {}
        complaint = ctx["intake"]["complaint"]

        sanctioned = txn.get("sanctioned_amount")
        credited = txn.get("credited_amount")
        if sanctioned is None:
            sanctioned = complaint.get("expected_amount")

        shortfall = None
        ratio = None
        if sanctioned is not None and credited is not None:
            shortfall = round(float(sanctioned) - float(credited), 2)
            if sanctioned:
                ratio = round(float(credited) / float(sanctioned), 4)

        rebuilt = complaint.get("expected_amount")
        amount_disputed = None
        if rebuilt is not None and sanctioned is not None:
            amount_disputed = abs(float(rebuilt) - float(sanctioned)) > 0.5

        return {
            "sanctioned_amount": sanctioned,
            "credited_amount": credited,
            "shortfall": shortfall,
            "credited_ratio": ratio,
            "partial": bool(shortfall and shortfall > 0),
            "amount_disputed_by_complainant": amount_disputed,
        }
