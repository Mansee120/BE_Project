"""
DBT lookup agent (money-trace, Agent 2/7)
-----------------------------------------
Locates the government disbursement record(s) the complaint refers to, using the
UTR when supplied and otherwise the beneficiary + scheme. Returns the best match
plus any other candidates so downstream agents can reason about ambiguity.
"""
from .. import dbt


class DBTLookupAgent:
    def run(self, ctx: dict) -> dict:
        complaint = ctx["intake"]["complaint"]
        utr = complaint.get("utr")
        beneficiary_id = complaint.get("beneficiary_id")
        scheme_id = complaint.get("scheme_id")

        matched = None
        candidates = []
        method = None

        if utr:
            matched = dbt.find_by_utr(utr)
            method = "utr"
            if matched is None:
                # Fall back to beneficiary/scheme search and note the miss.
                candidates = dbt.find_for_beneficiary(beneficiary_id, scheme_id) \
                    if beneficiary_id else []
                return {"matched": None, "candidates": candidates,
                        "method": "utr", "utr_not_found": True}

        if matched is None and beneficiary_id:
            candidates = dbt.find_for_beneficiary(beneficiary_id, scheme_id)
            if candidates:
                matched = candidates[0]
                method = "beneficiary+scheme"

        return {
            "matched": matched,
            "candidates": candidates,
            "method": method,
            "utr_not_found": False,
        }
