"""
complaints.py
-------------
Persistent complaint store for the grievance module. Each complaint records the
citizen's report, the money-trace result produced by ``backend.trace``, and the
workflow status an officer moves it through.

Storage is a single JSON file (``runtime/complaints.json``) guarded by a
re-entrant lock so concurrent FastAPI requests cannot corrupt it. This keeps the
offline demo dependency-free while remaining safe under uvicorn's threadpool.
"""
import json
import os
import secrets
import threading
from datetime import datetime, timezone

from . import config

_LOCK = threading.RLock()

# Workflow: filed -> traced -> under_review -> resolved | rejected
STATUSES = ("filed", "traced", "under_review", "resolved", "rejected")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> dict:
    if not os.path.exists(config.COMPLAINTS_PATH):
        return {"complaints": []}
    try:
        with open(config.COMPLAINTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"complaints": []}
    except (json.JSONDecodeError, OSError):
        return {"complaints": []}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(config.COMPLAINTS_PATH), exist_ok=True)
    tmp = config.COMPLAINTS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, config.COMPLAINTS_PATH)


def _new_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"CMP-{stamp}-{secrets.token_hex(3).upper()}"


def create(complaint: dict, trace: dict, filed_by: dict) -> dict:
    """Persist a complaint together with its trace result."""
    with _LOCK:
        data = _load()
        record = {
            "complaint_id": _new_id(),
            "filed_by": filed_by.get("username"),
            "filed_by_role": filed_by.get("role"),
            "beneficiary_id": (trace.get("complaint") or {}).get("beneficiary_id")
            or filed_by.get("beneficiary_id"),
            "beneficiary_name": (trace.get("beneficiary") or {}).get("name")
            or complaint.get("name"),
            "scheme_id": (trace.get("complaint") or {}).get("scheme_id"),
            "utr": (trace.get("complaint") or {}).get("utr"),
            "description": complaint.get("description", ""),
            "status": "traced",
            "filed_at": _now(),
            "updated_at": _now(),
            "trace": trace,
            "history": [{"at": _now(), "status": "filed",
                         "by": filed_by.get("username"),
                         "note": "Complaint filed and auto-traced."}],
        }
        data["complaints"].append(record)
        _save(data)
        return record


def get(complaint_id: str) -> dict:
    with _LOCK:
        for c in _load()["complaints"]:
            if c["complaint_id"] == complaint_id:
                return c
    return None


def list_for_user(user: dict) -> list:
    """Officials see everything; beneficiaries see only their own."""
    with _LOCK:
        items = list(_load()["complaints"])
    if user.get("role") == "official":
        return sorted(items, key=lambda c: c["filed_at"], reverse=True)
    return sorted(
        [c for c in items
         if c.get("filed_by") == user.get("username")
         or c.get("beneficiary_id") == user.get("beneficiary_id")],
        key=lambda c: c["filed_at"], reverse=True)


def update_status(complaint_id: str, status: str, officer: dict, note: str = "") -> dict:
    if status not in STATUSES:
        raise ValueError(f"invalid status '{status}'")
    with _LOCK:
        data = _load()
        for c in data["complaints"]:
            if c["complaint_id"] == complaint_id:
                c["status"] = status
                c["updated_at"] = _now()
                c["history"].append({"at": _now(), "status": status,
                                     "by": officer.get("username"), "note": note})
                _save(data)
                return c
    return None


def summary() -> dict:
    """Aggregate counts for the officer dashboard."""
    with _LOCK:
        items = list(_load()["complaints"])
    by_status = {s: 0 for s in STATUSES}
    by_verdict = {}
    diverted = 0
    mule = 0
    for c in items:
        by_status[c.get("status", "filed")] = by_status.get(c.get("status", "filed"), 0) + 1
        finding = (c.get("trace") or {}).get("finding") or {}
        v = finding.get("verdict", "unknown")
        by_verdict[v] = by_verdict.get(v, 0) + 1
        if finding.get("diversion"):
            diverted += 1
        if finding.get("mule_ring"):
            mule += 1
    return {
        "total": len(items),
        "by_status": by_status,
        "by_verdict": by_verdict,
        "diverted": diverted,
        "mule_ring": mule,
    }
