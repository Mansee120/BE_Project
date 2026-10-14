"""
evaluation_agent.py  (Agent 7/8)
--------------------------------
Scores pipeline verdicts against the YojanaBench ground truth and produces the
metrics from the project specification:

  * Exact Match (EM)          - normalised answer equality
  * Token-level F1            - harmonic mean of token precision/recall
  * Verdict Accuracy          - eligible / ineligible / needs_info correctness
  * Entitlement Error         - absolute & relative error on computed benefits
  * Document F1               - set overlap of required documents
  * Confidence Calibration    - Expected Calibration Error (ECE-style)
"""
import math
import re
from collections import Counter

_WORD_RE = re.compile(r"[a-z0-9]+")
_DECISIONS = {"eligible", "ineligible", "needs_info"}


def _normalise(text: str) -> str:
    return " ".join(_WORD_RE.findall((text or "").lower()))


def _tokens(text: str):
    return _WORD_RE.findall((text or "").lower())


def exact_match(pred: str, ref: str) -> float:
    return 1.0 if _normalise(pred) == _normalise(ref) else 0.0


def token_f1(pred: str, ref: str) -> float:
    pc, rc = Counter(_tokens(pred)), Counter(_tokens(ref))
    if not pc or not rc:
        return 0.0
    common = sum((pc & rc).values())
    if common == 0:
        return 0.0
    precision = common / sum(pc.values())
    recall = common / sum(rc.values())
    return 2 * precision * recall / (precision + recall)


def doc_f1(pred_docs: list, ref_docs: list) -> float:
    p = {d.strip().lower() for d in (pred_docs or [])}
    r = {d.strip().lower() for d in (ref_docs or [])}
    if not p or not r:
        return 0.0
    common = len(p & r)
    if common == 0:
        return 0.0
    precision, recall = common / len(p), common / len(r)
    return 2 * precision * recall / (precision + recall)


class EvaluationAgent:
    def __init__(self, corpus):
        self.corpus = corpus

    def score_item(self, item: dict, result: dict) -> dict:
        pred_answer = result.get("answer", "")
        ref_answer = item.get("reference_answer", "")

        em = exact_match(pred_answer, ref_answer)
        f1 = token_f1(pred_answer, ref_answer)

        ground_verdict = item.get("verdict")
        pred_verdict = result.get("verdict", {}).get("decision")
        verdict_correct = None
        if ground_verdict in _DECISIONS:
            verdict_correct = 1.0 if pred_verdict == ground_verdict else 0.0

        ent_err = None
        ent_rel_err = None
        ref_val = item.get("entitlement_value")
        pred_val = result.get("verdict", {}).get("computed_entitlement")
        if ref_val is not None and pred_val is not None:
            ent_err = abs(pred_val - ref_val)
            if ref_val != 0:
                ent_rel_err = ent_err / abs(ref_val)

        # Document F1 only meaningful for document-identification questions
        df1 = None
        if item.get("category") == "documents":
            scheme = self.corpus.get_scheme(item["scheme_id"])
            ref_docs = [d["name"] for d in scheme["required_documents"]
                        if d.get("mandatory", True)]
            pred_docs = result.get("predicted_documents", [])
            df1 = doc_f1(pred_docs, ref_docs)

        return {
            "id": item["id"],
            "scheme_id": item["scheme_id"],
            "category": item["category"],
            "edge_case": item.get("edge_case"),
            "question": item["question"],
            "reference_answer": ref_answer,
            "predicted_answer": pred_answer,
            "ground_verdict": ground_verdict,
            "predicted_verdict": pred_verdict,
            "em": em,
            "f1": round(f1, 4),
            "verdict_correct": verdict_correct,
            "entitlement_error": ent_err,
            "entitlement_rel_error": ent_rel_err,
            "confidence": result.get("verdict", {}).get("confidence"),
            "document_f1": df1,
        }

    def aggregate(self, rows: list) -> dict:
        n = len(rows) or 1

        em = sum(r["em"] for r in rows) / n
        f1 = sum(r["f1"] for r in rows) / n
        # Lenient answer accuracy: fraction of answers with token-F1 >= 0.5
        answer_acc = sum(1 for r in rows if r["f1"] >= 0.5) / n

        verdict_rows = [r for r in rows if r["verdict_correct"] is not None]
        verdict_acc = (sum(r["verdict_correct"] for r in verdict_rows) /
                       len(verdict_rows)) if verdict_rows else None

        ent_rows = [r for r in rows if r["entitlement_error"] is not None]
        ent_abs = (sum(r["entitlement_error"] for r in ent_rows) /
                   len(ent_rows)) if ent_rows else None
        rel_rows = [r for r in rows if r["entitlement_rel_error"] is not None]
        ent_rel = (sum(r["entitlement_rel_error"] for r in rel_rows) /
                   len(rel_rows)) if rel_rows else None

        doc_rows = [r for r in rows if r["document_f1"] is not None]
        docf1 = (sum(r["document_f1"] for r in doc_rows) /
                 len(doc_rows)) if doc_rows else None

        ece = self._calibration(rows)

        # Per-category breakdown
        by_cat = {}
        for r in rows:
            by_cat.setdefault(r["category"], []).append(r)
        category_breakdown = {}
        for cat, items in by_cat.items():
            vrows = [x for x in items if x["verdict_correct"] is not None]
            category_breakdown[cat] = {
                "count": len(items),
                "em": round(sum(x["em"] for x in items) / len(items), 4),
                "f1": round(sum(x["f1"] for x in items) / len(items), 4),
                "verdict_accuracy": (round(sum(x["verdict_correct"] for x in vrows) /
                                           len(vrows), 4) if vrows else None),
            }

        # Breakdown by edge-case vs base
        edge_rows = [r for r in rows if r["edge_case"]]
        base_rows = [r for r in rows if not r["edge_case"]]

        def _acc(rs):
            vr = [x for x in rs if x["verdict_correct"] is not None]
            return round(sum(x["verdict_correct"] for x in vr) / len(vr), 4) if vr else None

        return {
            "count": len(rows),
            "exact_match": round(em, 4),
            "token_f1": round(f1, 4),
            "answer_accuracy": round(answer_acc, 4),
            "verdict_accuracy": round(verdict_acc, 4) if verdict_acc is not None else None,
            "entitlement_error_abs": round(ent_abs, 2) if ent_abs is not None else None,
            "entitlement_error_rel": round(ent_rel, 4) if ent_rel is not None else None,
            "document_f1": round(docf1, 4) if docf1 is not None else None,
            "calibration_ece": round(ece, 4),
            "category_breakdown": category_breakdown,
            "edge_case_accuracy": _acc(edge_rows),
            "base_case_accuracy": _acc(base_rows),
            "n_verdict_items": len(verdict_rows),
        }

    @staticmethod
    def _calibration(rows, n_buckets: int = 5) -> float:
        """Expected Calibration Error over the verdict items."""
        usable = [r for r in rows
                  if r["confidence"] is not None and r["verdict_correct"] is not None]
        if not usable:
            return 0.0
        buckets = [[] for _ in range(n_buckets)]
        for r in usable:
            idx = min(int(r["confidence"] * n_buckets), n_buckets - 1)
            buckets[idx].append(r)
        total = len(usable)
        ece = 0.0
        for b in buckets:
            if not b:
                continue
            avg_conf = sum(x["confidence"] for x in b) / len(b)
            avg_acc = sum(x["verdict_correct"] for x in b) / len(b)
            ece += (len(b) / total) * abs(avg_conf - avg_acc)
        return ece
