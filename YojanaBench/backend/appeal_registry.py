"""
appeal_registry.py
------------------
File-backed register of appeals per case (mirrors the OrbitAvanya
``DuplicateTracker`` idea). It lets the notification layer detect a *repeat*
appeal so the system can issue an **official notice** citing the previous,
clause-cited decision instead of silently re-processing - and route genuine
new-ground appeals onward.

Storage: ``runtime/appeal_registry.json`` (see ``config.APPEAL_REGISTRY_PATH``).
"""
import datetime
import json
import os

from . import config

MAX_LEVEL = 3


def _load() -> dict:
    if not os.path.exists(config.APPEAL_REGISTRY_PATH):
        return {"appeals": []}
    try:
        with open(config.APPEAL_REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"appeals": []}
        data.setdefault("appeals", [])
        return data
    except (json.JSONDecodeError, OSError):
        return {"appeals": []}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(config.APPEAL_REGISTRY_PATH), exist_ok=True)
    with open(config.APPEAL_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def entries(case_id: str) -> list:
    return [a for a in _load()["appeals"] if a.get("case_id") == case_id]


def attempts(case_id: str) -> int:
    return len(entries(case_id))


def is_repeat(case_id: str) -> bool:
    """True once the case already has at least one recorded appeal."""
    return attempts(case_id) >= 1


def history() -> list:
    return _load()["appeals"]


def record(case_id: str, scheme_id: str, decision: str,
           clause_ids=None, reason: str = "") -> dict:
    """Append an appeal attempt and return the stored entry."""
    data = _load()
    prior = [a for a in data["appeals"] if a.get("case_id") == case_id]
    entry = {
        "case_id": case_id,
        "scheme_id": scheme_id,
        "attempt": len(prior) + 1,
        "level": min(len(prior) + 1, MAX_LEVEL),
        "decision": decision,
        "clause_ids": list(clause_ids or []),
        "reason": reason,
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    data["appeals"].append(entry)
    _save(data)
    return entry


def build_notice(case_id: str, scheme_name: str = "the scheme"):
    """Compose an official notice citing the case's recorded appeal history."""
    hist = entries(case_id)
    if not hist:
        return None
    last = hist[-1]
    prior = hist[:-1]

    lines = [
        "OFFICIAL NOTICE - repeated appeal",
        f"Case reference: {case_id}",
        f"Scheme: {scheme_name}",
        "",
        f"This is appeal attempt {last['attempt']} for the above case.",
    ]
    if prior:
        lines.append("This application was previously decided as: "
                     + ", ".join(f"{p['decision'].upper()} (attempt {p['attempt']}, "
                                 f"{p['date']})" for p in prior) + ".")
    if last.get("clause_ids"):
        lines.append("The decision stands on the following cited clauses: "
                     + ", ".join(last["clause_ids"]) + ".")
    lines.append("")
    lines.append("Repeated appeals on unchanged facts may be consolidated by the "
                 "grievance authority. If you hold new documents or new grounds, "
                 "state them explicitly; otherwise this notice is issued for record.")
    return {
        "notice_type": "repeat_notice",
        "case_id": case_id,
        "attempt": last["attempt"],
        "level": last["level"],
        "subject": f"Official notice: repeated appeal on case {case_id}",
        "body_text": "\n".join(lines),
        "clause_ids": last.get("clause_ids", []),
        "history": hist,
    }
