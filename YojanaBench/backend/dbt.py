"""
dbt.py
------
Loader and query helpers for the Direct Benefit Transfer (DBT) ledger and the
beneficiary registry. The money-trace agents use these to answer "did the
government actually credit this person's account?".

Both datasets are plain JSON under ``data/`` so the module stays fully offline
and reproducible.
"""
import json
import os

from . import config


def load_beneficiaries() -> dict:
    """Return ``{beneficiary_id: record}``."""
    if not os.path.exists(config.BENEFICIARIES_PATH):
        return {}
    with open(config.BENEFICIARIES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {b["beneficiary_id"]: b for b in data.get("beneficiaries", [])}


def get_beneficiary(beneficiary_id: str):
    return load_beneficiaries().get(beneficiary_id)


def load_transactions() -> list:
    if not os.path.exists(config.DBT_TRANSACTIONS_PATH):
        return []
    with open(config.DBT_TRANSACTIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("transactions", [])


def find_by_utr(utr: str):
    utr = (utr or "").strip().upper()
    if not utr:
        return None
    for t in load_transactions():
        if t.get("utr", "").upper() == utr:
            return t
    return None


def find_for_beneficiary(beneficiary_id: str, scheme_id: str = None) -> list:
    out = []
    for t in load_transactions():
        if t.get("beneficiary_id") != beneficiary_id:
            continue
        if scheme_id and t.get("scheme_id") != scheme_id:
            continue
        out.append(t)
    # newest first by credit_date then utr
    out.sort(key=lambda t: (t.get("credit_date") or "", t.get("utr") or ""),
             reverse=True)
    return out


def search(utr: str = None, beneficiary_id: str = None, scheme_id: str = None,
           aadhaar_last4: str = None) -> list:
    """Best-effort lookup used when a complaint omits fields."""
    txns = load_transactions()
    hits = []
    for t in txns:
        if utr and t.get("utr", "").upper() != utr.strip().upper():
            continue
        if beneficiary_id and t.get("beneficiary_id") != beneficiary_id:
            continue
        if scheme_id and t.get("scheme_id") != scheme_id:
            continue
        if aadhaar_last4 and t.get("aadhaar_last4") != str(aadhaar_last4):
            continue
        hits.append(t)
    return hits


def account_usage(credited_account_last4: str) -> list:
    """Every transaction credited to a given account (mule-ring detection)."""
    if not credited_account_last4:
        return []
    return [t for t in load_transactions()
            if t.get("credited_to_account_last4") == credited_account_last4]
