"""
Fraud / leakage agent (money-trace, Agent 5/7)
----------------------------------------------
Reasons about *how* money went missing when the credit did not reach the
beneficiary:

  * diversion            - credited to an account/name that is not the
                           beneficiary's (third-person theft / identity misuse).
  * mule ring            - the same receiving account collects benefits for many
                           different beneficiaries (organised siphoning).
  * duplicate reference  - the same UTR appears more than once.
  * entity payee         - money routed to a company/agent rather than a person.
"""
from .. import dbt

MULE_THRESHOLD = 3  # an account used >= N times across beneficiaries is a ring


class FraudAgent:
    def run(self, ctx: dict) -> dict:
        txn = ctx["lookup"].get("matched") or {}
        credit = ctx["credit"]

        flags = []
        diversion = False
        mule_ring = False
        ring_accounts = []
        ring_beneficiaries = []

        credited_acct = credit.get("credited_to_account_last4")
        if credit["status"] == "diverted":
            diversion = True
            flags.append("funds_diverted_from_beneficiary")
        if "credited_to_business_entity" in credit.get("flags", []):
            flags.append("beneficiary_funds_paid_to_entity")

        # Mule-ring detection: how many distinct beneficiaries share the account?
        if credited_acct and not credit.get("to_expected_account"):
            usage = dbt.account_usage(credited_acct)
            bene_ids = sorted({t.get("beneficiary_id") for t in usage})
            if len(bene_ids) >= MULE_THRESHOLD:
                mule_ring = True
                ring_accounts = [credited_acct]
                ring_beneficiaries = bene_ids
                flags.append("shared_receiving_account")

        # Duplicate UTR references across the ledger.
        duplicated_utr = False
        if txn.get("utr"):
            same = dbt.search(utr=txn["utr"])
            if len(same) > 1:
                duplicated_utr = True
                flags.append("duplicate_utr")

        severity = "none"
        if mule_ring or diversion:
            severity = "high"
        elif flags:
            severity = "medium"

        return {
            "diversion": diversion,
            "mule_ring": mule_ring,
            "ring_accounts": ring_accounts,
            "ring_beneficiaries": ring_beneficiaries,
            "duplicate_utr": duplicated_utr,
            "flags": flags,
            "severity": severity,
        }
