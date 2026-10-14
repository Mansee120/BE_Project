"""
benchmark.py
------------
The open YojanaBench evaluation harness.

Anyone can score a model on the YojanaBench benchmark and add it to the public
leaderboard, using the exact same metrics the built-in pipeline is scored with:

    # score and register the built-in pipeline
    python benchmark.py --name "YojanaBench (built-in)"

    # score a third-party model from a predictions file
    python benchmark.py --name "MyModel" --predictions my_predictions.json

Predictions file format (JSON):
    {
      "items": [
        {"id": "YB-IGNOAPS-0001", "answer": "...", "verdict": "eligible",
         "entitlement_value": 200, "confidence": 0.9, "documents": ["Aadhaar Card"]}
      ]
    }

Metrics reported: verdict accuracy, answer accuracy, token-F1, exact match,
entitlement error, document F1 and calibration (ECE).
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from backend.pipeline import Pipeline
from backend.leaderboard import add_entry, ranked


def _score_external(pipeline, preds, items):
    """Score third-party predictions item-by-item using the shared evaluator."""
    by_id = {p["id"]: p for p in preds}
    rows = []
    for item in items:
        pred = by_id.get(item["id"], {})
        result = {
            "answer": pred.get("answer", ""),
            "verdict": {
                "decision": pred.get("verdict"),
                "computed_entitlement": pred.get("entitlement_value"),
                "confidence": pred.get("confidence"),
            },
            "predicted_documents": pred.get("documents", []),
        }
        rows.append(pipeline.evaluation.score_item(item, result))
    return pipeline.evaluation.aggregate(rows)


def _print_table(entries):
    cols = ["name", "verdict_accuracy", "answer_accuracy", "token_f1",
            "entitlement_error_abs", "document_f1", "calibration_ece"]
    widths = [26, 16, 15, 9, 20, 12, 16]
    header = "".join(c.replace("_", " ")[:w - 1].ljust(w) for c, w in zip(cols, widths))
    print(header)
    print("-" * len(header))
    for e in entries:
        m = e["metrics"]
        vals = [e["name"]] + [
            ("n/a" if m.get(c) is None else
             (f"{m[c]:.4f}" if isinstance(m[c], float) else str(m[c])))
            for c in cols[1:]
        ]
        print("".join(str(v)[:w - 1].ljust(w) for v, w in zip(vals, widths)))


def main():
    ap = argparse.ArgumentParser(description="YojanaBench evaluation harness")
    ap.add_argument("--name", default="YojanaBench (built-in)",
                    help="leaderboard entry name")
    ap.add_argument("--predictions", help="JSON file of third-party predictions")
    ap.add_argument("--baseline", choices=["always-eligible", "always-ineligible"],
                    help="score a trivial constant-verdict baseline")
    ap.add_argument("--no-save", action="store_true",
                    help="score only; do not write the leaderboard")
    args = ap.parse_args()

    pipeline = Pipeline()

    if args.predictions:
        with open(args.predictions, "r", encoding="utf-8") as f:
            data = json.load(f)
        preds = data.get("items", data) if isinstance(data, dict) else data
        items = pipeline._load_benchmark()["items"]
        metrics = _score_external(pipeline, preds, items)
        note = f"external predictions ({os.path.basename(args.predictions)})"
    elif args.baseline:
        items = pipeline._load_benchmark()["items"]
        verdict = "eligible" if args.baseline == "always-eligible" else "ineligible"
        preds = [{"id": it["id"], "verdict": verdict, "answer": ""} for it in items]
        metrics = _score_external(pipeline, preds, items)
        note = f"trivial baseline: always {verdict}"
        if args.name == "YojanaBench (built-in)":
            args.name = f"Baseline: always {verdict}"
    else:
        run = pipeline.run_benchmark()
        metrics = run["metrics"]
        note = "built-in deterministic pipeline"

    print(f"\nScored model: {args.name}")
    print(json.dumps({k: metrics.get(k) for k in
                      ("verdict_accuracy", "answer_accuracy", "token_f1",
                       "exact_match", "entitlement_error_abs", "document_f1",
                       "calibration_ece")}, indent=2))

    if not args.no_save:
        add_entry(args.name, metrics, note=note)

    print("\nLeaderboard:")
    _print_table(ranked())


if __name__ == "__main__":
    main()
