"""
Intake agent (money-trace, Agent 1/7)
-------------------------------------
Turns a raw grievance ("my pension money never came") into a validated trace
request: it normalises the fields, resolves the beneficiary from the registry
and works out which scheme/UTR the complaint is about.
"""
from .. import dbt

# Scheme-agnostic aliases a citizen form might submit.
_ALIASES = {
    "amount": "expected_amount",
    "amount_expected": "expected_amount",
    "reference": "utr",
    "transaction_id": "utr",
    "aadhaar": "aadhaar_last4",
    "scheme": "scheme_id",
}


class TraceIntakeAgent:
    def run(self, complaint: dict, user: dict = None) -> dict:
        raw = dict(complaint or {})
        clean = {}
        for key, value in raw.items():
            key = _ALIASES.get(key, key)
            if value is None or value == "":
                continue
            clean[key] = value

        # Attach the logged-in beneficiary when the complaint does not name one.
        if not clean.get("beneficiary_id") and user and user.get("beneficiary_id"):
            clean["beneficiary_id"] = user["beneficiary_id"]

        if clean.get("utr"):
            clean["utr"] = str(clean["utr"]).strip().upper()
        if clean.get("aadhaar_last4") is not None:
            clean["aadhaar_last4"] = str(clean["aadhaar_last4"]).strip()

        expected = clean.get("expected_amount")
        if expected is not None:
            try:
                clean["expected_amount"] = float(expected)
            except (TypeError, ValueError):
                clean.pop("expected_amount", None)

        beneficiary = None
        if clean.get("beneficiary_id"):
            beneficiary = dbt.get_beneficiary(clean["beneficiary_id"])

        missing = []
        if not clean.get("scheme_id"):
            missing.append("scheme_id")
        if not (clean.get("utr") or clean.get("beneficiary_id")):
            missing.append("utr or beneficiary_id")

        return {
            "complaint": clean,
            "beneficiary": beneficiary,
            "missing": missing,
            "valid": not missing,
        }
