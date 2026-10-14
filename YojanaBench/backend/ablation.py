"""
ablation.py
-----------
Ablation-study runner for YojanaBench.

Runs the benchmark under several pipeline configurations and reports how much
each component contributes. This is the "baselines and ablations" experiment
from the specification:

  * full              - all agents, deterministic maths            (main result)
  * no_verification   - Verification agent removed (no cross-check / doc gate)
  * llm_math          - deterministic benefit maths replaced by a naive proxy
  * no_counterfactuals- full pipeline, but score only base (non-edge) items

The comparison highlights the two design claims of the project:
  (1) Verification catches missing-document / disagreement cases,
  (2) deterministic maths prevents entitlement errors.
"""
from .pipeline import pipeline


class AblationRunner:
    # Human-readable labels for the UI
    LABELS = {
        "full": "Full pipeline (all agents)",
        "no_verification": "Ablation: no Verification",
        "llm_math": "Ablation: LLM-only maths",
        "no_counterfactuals": "Ablation: no counterfactuals in analysis",
    }

    def __init__(self, pl=None):
        self.pipeline = pl or pipeline

    def run(self, use_llm: bool = False) -> dict:
        variants = {}
        for name in self.pipeline.ABLATION_MODES:
            result = self.pipeline.run_benchmark(use_llm=use_llm, ablation=name)
            m = result["metrics"]
            variants[name] = {
                "label": self.LABELS.get(name, name),
                "count": m["count"],
                "verdict_accuracy": m["verdict_accuracy"],
                "answer_accuracy": m["answer_accuracy"],
                "token_f1": m["token_f1"],
                "exact_match": m["exact_match"],
                "entitlement_error_abs": m["entitlement_error_abs"],
                "document_f1": m["document_f1"],
                "calibration_ece": m["calibration_ece"],
                "edge_case_accuracy": m["edge_case_accuracy"],
            }

        # Deltas measured against the full pipeline
        full = variants["full"]
        comparison = []
        order = ["full", "no_verification", "llm_math", "no_counterfactuals"]
        for name in order:
            v = variants[name]
            comparison.append({
                "variant": name,
                "label": v["label"],
                "count": v["count"],
                "verdict_accuracy": v["verdict_accuracy"],
                "verdict_accuracy_delta": self._delta(v["verdict_accuracy"], full["verdict_accuracy"]),
                "entitlement_error_abs": v["entitlement_error_abs"],
                "token_f1": v["token_f1"],
                "answer_accuracy": v["answer_accuracy"],
                "calibration_ece": v["calibration_ece"],
            })

        return {
            "variants": variants,
            "comparison": comparison,
            "llm_used": use_llm,
        }

    @staticmethod
    def _delta(value, baseline):
        """Signed difference in percentage points (rounded)."""
        if value is None or baseline is None:
            return None
        return round((value - baseline) * 100, 2)
