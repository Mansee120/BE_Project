"""
case_store.py
-------------
Persistence for audit cases *written* by the voice assistant's agent layer.

Unlike the hand-authored sample cases under ``data/cases`` these are generated
at runtime and stored under ``runtime/cases`` (see ``config.GENERATED_CASES_DIR``).
Each file is a self-contained, human-readable JSON record of one audit: the
applicant input, the clause-cited verdict, the grounded notice and the appeal
outcome - so a citizen (or an officer) can reopen exactly what the agent did.

Kept deliberately tiny and dependency-free, mirroring ``appeal_registry``.
"""
import datetime
import json
import os
import re

from . import config


def cases_dir() -> str:
    path = getattr(config, "GENERATED_CASES_DIR",
                   os.path.join(config.RUNTIME_DIR, "cases"))
    os.makedirs(path, exist_ok=True)
    return path


def _safe(case_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", case_id or "case") or "case"


def save(record: dict) -> str:
    """Write one case record to disk and return its path."""
    path = os.path.join(cases_dir(), f"{_safe(record.get('case_id'))}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    return path


def load(case_id: str):
    path = os.path.join(cases_dir(), f"{_safe(case_id)}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def list_cases() -> list:
    """All written cases, newest first (by creation time when present)."""
    out = []
    for fname in os.listdir(cases_dir()):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(cases_dir(), fname), "r", encoding="utf-8") as f:
                out.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue

    def _key(rec):
        return rec.get("created_at") or datetime.datetime.min.isoformat()

    return sorted(out, key=_key, reverse=True)
