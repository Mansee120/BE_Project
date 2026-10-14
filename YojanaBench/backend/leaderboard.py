"""
leaderboard.py
--------------
A tiny, file-backed leaderboard so anyone can score their own model on the
YojanaBench benchmark and compare against the built-in pipeline.

This is the "open evaluation harness" contribution: existing products
(myScheme etc.) publish no reproducible accuracy numbers, and no way for a third
party to be scored on the same task.

The leaderboard is stored as JSON under data/meta/leaderboard.json.
"""
import datetime
import json
import os

from . import config

LEADERBOARD_PATH = config.LEADERBOARD_PATH

# Columns shown in the (sorted) leaderboard table / dashboard.
RANK_COLUMNS = [
    "verdict_accuracy", "answer_accuracy", "token_f1",
    "entitlement_error_abs", "document_f1", "calibration_ece",
]


def load() -> dict:
    if not os.path.exists(LEADERBOARD_PATH):
        return {"benchmark_version": None, "entries": []}
    with open(LEADERBOARD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save(data: dict) -> None:
    os.makedirs(os.path.dirname(LEADERBOARD_PATH), exist_ok=True)
    with open(LEADERBOARD_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _rank_key(entry):
    """Higher verdict accuracy first, then higher answer accuracy, then lower ECE."""
    m = entry.get("metrics", {})
    return (
        -(m.get("verdict_accuracy") or 0),
        -(m.get("answer_accuracy") or 0),
        (m.get("calibration_ece") or 1),
    )


def ranked(data: dict = None) -> list:
    data = data or load()
    return sorted(data.get("entries", []), key=_rank_key)


def add_entry(name: str, metrics: dict, note: str = "", overwrite: bool = True) -> dict:
    """Append (or replace) a leaderboard entry and return the saved record."""
    data = load()
    entry = {
        "name": name,
        "note": note,
        "date": datetime.date.today().isoformat(),
        "metrics": {k: metrics.get(k) for k in RANK_COLUMNS},
    }
    entries = data.get("entries", [])
    if overwrite:
        entries = [e for e in entries if e.get("name") != name]
    entries.append(entry)
    data["entries"] = entries
    data.setdefault("benchmark_version", "1.0")
    save(data)
    return entry
