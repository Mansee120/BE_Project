"""
report.py (backend)
-------------------
Builds the accuracy report for YojanaBench as plain-Python records (lists of
dicts) so it can be serialised directly to JSON by the API and also wrapped
into pandas DataFrames by the CLI (`report.py` in the project root).

The heavy lifting is re-used from the running Pipeline: we score the full
benchmark once and then shape the item-level results into the tables that the
dashboard and the CSV report want.
"""
from .pipeline import Pipeline
from .ablation import AblationRunner


def _acc(values):
    """Mean of the non-null values (verdict accuracy is undefined for
    informational categories such as documents/appeal)."""
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def _mean(values):
    return round(sum(values) / len(values), 4) if values else 0.0


def build_report(pipeline=None):
    """Return a dict of {table_name: [row, ...]} accuracy tables."""
    pipeline = pipeline or Pipeline()

    run = pipeline.run_benchmark()
    m = run["metrics"]
    rows = run["rows"]

    # 1) Overall metrics ----------------------------------------------------
    overall = [
        {"metric": "Items scored", "value": m["count"]},
        {"metric": "Verdict accuracy (primary)", "value": m["verdict_accuracy"]},
        {"metric": "Answer accuracy (F1 >= 0.5)", "value": m["answer_accuracy"]},
        {"metric": "Token F1", "value": m["token_f1"]},
        {"metric": "Exact Match", "value": m["exact_match"]},
        {"metric": "Entitlement error (abs)", "value": m["entitlement_error_abs"]},
        {"metric": "Entitlement error (rel)", "value": m["entitlement_error_rel"]},
        {"metric": "Document F1", "value": m["document_f1"]},
        {"metric": "Calibration ECE", "value": m["calibration_ece"]},
        {"metric": "Edge-case accuracy", "value": m["edge_case_accuracy"]},
        {"metric": "Base-case accuracy", "value": m["base_case_accuracy"]},
    ]

    # 2) Per-category breakdown --------------------------------------------
    category = [
        {"category": cat, "count": v["count"],
         "verdict_accuracy": v["verdict_accuracy"], "em": v["em"], "f1": v["f1"]}
        for cat, v in m["category_breakdown"].items()
    ]

    # 3) Item-level records -------------------------------------------------
    items = [{
        "id": r["id"],
        "scheme_id": r["scheme_id"],
        "category": r["category"],
        "edge_case": r["edge_case"] or "-",
        "ground_verdict": r["ground_verdict"],
        "predicted_verdict": r["predicted_verdict"],
        "verdict_correct": r["verdict_correct"],
        "em": r["em"],
        "token_f1": r["f1"],
        "entitlement_error": r["entitlement_error"],
        "confidence": r["confidence"],
    } for r in rows]

    # 4) Per-scheme accuracy ------------------------------------------------
    per_scheme = {}
    for it in items:
        g = per_scheme.setdefault(it["scheme_id"], [])
        g.append(it)
    per_scheme_rows = []
    for sid, group in per_scheme.items():
        per_scheme_rows.append({
            "scheme_id": sid,
            "items": len(group),
            "verdict_accuracy": _acc([x["verdict_correct"] for x in group]),
            "mean_token_f1": _mean([x["token_f1"] for x in group]),
            "mean_confidence": _mean([x["confidence"] for x in group]),
        })
    per_scheme_rows.sort(key=lambda r: (r["verdict_accuracy"] is None, -(r["verdict_accuracy"] or 0)))

    # 5) Edge-case vs base-case --------------------------------------------
    groups = {"edge_case": [], "base": []}
    for it in items:
        groups["edge_case" if it["edge_case"] != "-" else "base"].append(it)
    edge_rows = [{
        "group": name,
        "items": len(group),
        "verdict_accuracy": _acc([x["verdict_correct"] for x in group]),
        "mean_token_f1": _mean([x["token_f1"] for x in group]),
    } for name, group in groups.items()]

    # 6) Ablation comparison ------------------------------------------------
    ab = AblationRunner(pipeline).run()
    ablation = [{
        "variant": c["variant"],
        "count": c["count"],
        "verdict_accuracy": c["verdict_accuracy"],
        "verdict_accuracy_delta": c["verdict_accuracy_delta"],
        "entitlement_error_abs": c["entitlement_error_abs"],
        "token_f1": c["token_f1"],
        "answer_accuracy": c["answer_accuracy"],
    } for c in ab["comparison"]]

    return {
        "overall_metrics": overall,
        "category_breakdown": category,
        "per_scheme_accuracy": per_scheme_rows,
        "edge_vs_base": edge_rows,
        "ablation_comparison": ablation,
        "item_results": items,
    }
