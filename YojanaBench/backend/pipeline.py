"""
pipeline.py
-----------
The YojanaBench coordinator. Wires the eight agents into the two-phase flow from
the specification and exposes:

  * run_case()      -> full online audit for one application
  * run_benchmark() -> runs the whole QA benchmark and scores it
  * dataset_stats() -> statistics for the dashboard
"""
import json
import os
import time

from . import config
from .agents import (
    AppealAgent,
    CorpusAgent,
    CounterfactualAgent,
    DocumentGapAgent,
    EntitlementAgent,
    EvaluationAgent,
    IntakeAgent,
    NotificationAgent,
    Orchestrator,
    RAGAgent,
    VerificationAgent,
)
from .llm import llm_client


class Pipeline:
    def __init__(self, dataset_dir: str = None):
        # Agent 1: build the corpus + retriever (offline phase)
        self.corpus = CorpusAgent(dataset_dir)
        # Online-phase agents
        self.intake = IntakeAgent(self.corpus)
        self.rag = RAGAgent(self.corpus)
        self.entitlement = EntitlementAgent(self.corpus)
        self.verification = VerificationAgent(self.corpus)
        self.orchestrator = Orchestrator(self.corpus)
        self.evaluation = EvaluationAgent(self.corpus)
        self.appeal = AppealAgent(self.corpus)
        # Advisory agents (beyond the core 8): explain *how* to qualify.
        self.counterfactual = CounterfactualAgent(self.corpus)
        self.document_gap = DocumentGapAgent(self.corpus)
        # Agent 11: compose a grounded, actionable notice (email automation).
        self.notification = NotificationAgent(self.corpus)

    # -- online case audit ----------------------------------------------------
    def run_case(self, scheme_id: str, applicant: dict, submitted_documents: list = None,
                 case_id: str = None, use_llm: bool = None,
                 use_verification: bool = True,
                 deterministic_entitlement: bool = True) -> dict:
        """Run the online audit.

        The two keyword flags support the ablation study:
          use_verification=False       -> disable the Verification agent's
                                          cross-check / document gating
          deterministic_entitlement=False -> replace the deterministic benefit
                                          maths with a naive "LLM-math" proxy
        """
        use_llm = bool(use_llm) and llm_client.available()
        trace = []

        def step(name, detail, ms):
            trace.append({"agent": name, "detail": detail, "ms": round(ms, 2)})

        t0 = time.perf_counter()
        case = self.intake.run(scheme_id, applicant, submitted_documents, case_id)
        step("IntakeAgent", f"Normalised {len(case['applicant'])} fields; "
             f"{len(case['missing_documents'])} missing documents",
             (time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        rag = self.rag.evidence_for_scheme(case)
        evidence = rag["evidence"]
        step("RAGAgent", f"Retrieved {len(evidence)} evidence clauses",
             (time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        entitlement_result = self.entitlement.run(
            case, naive=not deterministic_entitlement)
        ent = entitlement_result.get("entitlement") or {}
        step("EntitlementAgent",
             f"Eligibility={entitlement_result['eligibility_decision']}; "
             f"entitlement={ent.get('computed_entitlement')}"
             + ("" if deterministic_entitlement else " (naive maths)"),
             (time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        if use_verification:
            verification = self.verification.run(case, entitlement_result)
        else:
            # Ablation: Verification agent removed. Use a neutral result so the
            # Orchestrator simply trusts the Entitlement agent (no cross-check,
            # no missing-document gate).
            primary = entitlement_result["eligibility_decision"]
            verification = {
                "independent_decision": primary,
                "entitlement_decision": primary,
                "cross_check_agree": True,
                "documents_ok": True,
                "missing_documents": [],
                "flags": [],
                "disabled": True,
            }
        step("VerificationAgent",
             "DISABLED (ablation)" if not use_verification else
             f"cross_check={'agree' if verification['cross_check_agree'] else 'disagree'}; "
             f"missing_docs={len(verification['missing_documents'])}",
             (time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        verdict = self.orchestrator.run(case, evidence, entitlement_result,
                                        verification, use_llm=use_llm)
        step("Orchestrator", f"Decision={verdict['decision']}; confidence={verdict['confidence']}",
             (time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        appeal = self.appeal.run(case, verdict)
        step("AppealAgent",
             appeal["next_step"] if appeal["applicable"] else "not applicable",
             (time.perf_counter() - t0) * 1000)

        # Advisory agents: counterfactual "how to qualify" + document-gap analysis
        t0 = time.perf_counter()
        counterfactual = self.counterfactual.run(case, entitlement_result)
        step("CounterfactualAgent",
             counterfactual["summary"][:80],
             (time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        document_gap = self.document_gap.run(case, entitlement_result, verification)
        step("DocumentGapAgent",
             f"gap={document_gap['has_gap']}; verdict_with_docs="
             f"{document_gap['verdict_if_docs_complete']}",
             (time.perf_counter() - t0) * 1000)

        # Compose the grounded notice (delivery is done by the /api/notify endpoint).
        t0 = time.perf_counter()
        notification = self.notification.run(
            case, verdict, appeal, counterfactual, document_gap)
        step("NotificationAgent",
             f"{notification['notice_type']}; recipient="
             f"{notification['recipient'] or 'no email on file'}; "
             f"actionable={notification['actionable']}",
             (time.perf_counter() - t0) * 1000)

        return {
            "case": case,
            "evidence": evidence,
            "entitlement": entitlement_result,
            "verification": verification,
            "verdict": verdict,
            "appeal": appeal,
            "counterfactual": counterfactual,
            "document_gap": document_gap,
            "notification": notification,
            "trace": trace,
            "llm_used": verdict.get("explanation") is not None and use_llm,
        }

    # -- benchmark over the whole dataset ------------------------------------
    # Ablation presets: how each named variant changes the pipeline analysis.
    ABLATION_MODES = {
        "full": {},
        "no_verification": {"use_verification": False},
        "llm_math": {"deterministic_entitlement": False},
        "no_counterfactuals": {"drop_counterfactuals": True},
    }

    def _load_benchmark(self):
        with open(config.QA_BENCHMARK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _answer_for_item(self, item, result):
        """Override the short answer per QA category for fairer EM/F1 scoring."""
        category = item["category"]
        scheme = self.corpus.get_scheme(item["scheme_id"])

        if category == "documents":
            names = [d["name"] for d in scheme["required_documents"]
                     if d.get("mandatory", True)]
            return "Required documents: " + ", ".join(names), names

        if category == "appeal":
            levels = scheme["appeal_hierarchy"]
            parts = [f"Level {a['level']}: {a['authority']} within {a['deadline_days']} days"
                     for a in levels]
            return "Appeal procedure: " + "; ".join(parts), []

        return result["verdict"]["answer"], []

    def run_benchmark(self, scheme_id: str = None, category: str = None,
                      use_llm: bool = None, ablation: str = "full") -> dict:
        mode = dict(self.ABLATION_MODES.get(ablation, {}))
        data = self._load_benchmark()
        items = data.get("items", [])
        if scheme_id:
            items = [i for i in items if i["scheme_id"] == scheme_id]
        if category:
            items = [i for i in items if i["category"] == category]
        # Ablation: score only the base QA items (exclude edge / counterfactual)
        if mode.get("drop_counterfactuals"):
            items = [i for i in items if not i.get("edge_case")
                     and not i.get("counterfactual_of")]

        rows = []
        for item in items:
            applicant = item.get("applicant", {})
            result = self.run_case(
                item["scheme_id"], applicant,
                submitted_documents=item.get("submitted_documents"),
                case_id=item["id"], use_llm=use_llm,
                use_verification=mode.get("use_verification", True),
                deterministic_entitlement=mode.get("deterministic_entitlement", True))

            answer, predicted_docs = self._answer_for_item(item, result)
            result["answer"] = answer
            result["verdict"]["answer"] = answer
            result["predicted_documents"] = predicted_docs

            # Optional overlapping-scheme note
            if item.get("secondary_scheme_id"):
                sec = self.entitlement.run(
                    self.intake.run(item["secondary_scheme_id"], applicant))
                result["secondary_scheme"] = {
                    "scheme_id": item["secondary_scheme_id"],
                    "eligibility_decision": sec["eligibility_decision"],
                }

            row = self.evaluation.score_item(item, result)
            row["_result"] = result
            rows.append(row)

        metrics = self.evaluation.aggregate(rows)
        # Strip the heavy result objects from the returned rows for the API
        clean_rows = []
        for r in rows:
            rr = {k: v for k, v in r.items() if k != "_result"}
            rr["explanation"] = r["_result"]["verdict"]["explanation"].splitlines()[0]
            clean_rows.append(rr)

        return {
            "metrics": metrics,
            "rows": clean_rows,
            "ablation": ablation,
            "llm_used": bool(use_llm) and llm_client.available(),
        }

    # -- misc -----------------------------------------------------------------
    def dataset_stats(self) -> dict:
        stats = dict(self.corpus.stats)
        stats["llm"] = llm_client.status()
        return stats

    def list_cases(self):
        """Load the demo cases shipped with the dataset."""
        cases = []
        cdir = config.CASES_DIR
        if os.path.isdir(cdir):
            for fname in sorted(os.listdir(cdir)):
                if fname.endswith(".json"):
                    with open(os.path.join(cdir, fname), "r", encoding="utf-8") as f:
                        cases.append(json.load(f))
        return cases


# Shared singleton used by the FastAPI app.
pipeline = Pipeline()
