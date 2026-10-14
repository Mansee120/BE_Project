"""
Credit-check agent (money-trace, Agent 3/7)
-------------------------------------------
Answers the core question of the module: *did the money land in the
beneficiary's own account?* It inspects the credited account/name on the ledger
record against the account/name registered for the beneficiary.
"""
import re


def _normalise_name(name: str) -> str:
    return " ".join(re.findall(r"[a-z]+", (name or "").lower()))


def _looks_like_entity(name: str) -> bool:
    if not name:
        return False
    tokens = _normalise_name(name)
    return any(word in tokens for word in
               ("enterprises", "pvt", "ltd", "limited", "agent", "traders",
                "agency", "corporate", "services", "collection"))


class CreditCheckAgent:
    def run(self, ctx: dict) -> dict:
        txn = ctx["lookup"].get("matched")
        beneficiary = ctx["intake"].get("beneficiary") or {}

        if not txn:
            return {
                "status": "no_record",
                "credited": False,
                "amount_reached_beneficiary": False,
                "to_expected_account": False,
                "name_matches": None,
                "credited_to_account_last4": None,
                "expected_account_last4": (beneficiary or {}).get("account_last4"),
                "credited_to_name": None,
                "flags": [],
            }

        expected_acct = txn.get("expected_account_last4") or beneficiary.get("account_last4")
        credited_acct = txn.get("credited_to_account_last4")
        credited_name = txn.get("credited_to_name")
        credited_amount = txn.get("credited_amount") or 0

        to_expected = bool(credited_acct) and str(credited_acct) == str(expected_acct)
        name_matches = (
            _normalise_name(credited_name) == _normalise_name(beneficiary.get("name"))
            if (credited_name and beneficiary.get("name")) else None
        )

        flags = []
        if credited_amount and not credited_acct:
            flags.append("credit_without_account")
        if credited_acct and not to_expected:
            flags.append("credited_to_unexpected_account")
        if name_matches is False:
            flags.append("beneficiary_name_mismatch")
        if _looks_like_entity(credited_name):
            flags.append("credited_to_business_entity")

        reached = bool(credited_amount) and to_expected and (name_matches is not False)

        if txn.get("status") == "not_credited" or not credited_amount:
            status = "not_credited"
        elif to_expected and (name_matches is not False):
            status = "credited"
        else:
            status = "diverted"

        return {
            "status": status,
            "credited": bool(credited_amount),
            "amount_reached_beneficiary": reached,
            "to_expected_account": to_expected,
            "name_matches": name_matches,
            "credited_to_account_last4": credited_acct,
            "expected_account_last4": str(expected_acct) if expected_acct else None,
            "credited_to_name": credited_name,
            "flags": flags,
        }
