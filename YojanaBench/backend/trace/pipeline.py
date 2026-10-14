"""
trace.pipeline
--------------
Wires the seven money-trace agents into a single deterministic run:

    intake -> dbt lookup -> credit check -> reconcile -> fraud
           -> orchestrator (verdict) -> grievance notice

``TracePipeline.run`` returns one dictionary containing every intermediate
finding plus the final trace result and a per-agent trace log (name, summary,
elapsed ms) for transparency in the UI.
"""
import time

from .intake import TraceIntakeAgent
from .dbt_lookup import DBTLookupAgent
from .credit_check import CreditCheckAgent
from .reconcile import ReconciliationAgent
from .fraud import FraudAgent
from .orchestrator import TraceOrchestrator
from .notice import GrievanceNoticeAgent


class TracePipeline:
    AGENT_NAMES = [
        "trace_intake", "dbt_lookup", "credit_check", "reconcile",
        "fraud_detect", "orchestrate", "grievance_notice",
    ]

    def __init__(self):
        self.intake = TraceIntakeAgent()
        self.lookup = DBTLookupAgent()
        self.credit = CreditCheckAgent()
        self.reconcile = ReconciliationAgent()
        self.fraud = FraudAgent()
        self.orchestrator = TraceOrchestrator()
        self.notice = GrievanceNoticeAgent()

    def _step(self, log, name, fn, *args):
        start = time.perf_counter()
        result = fn(*args)
        log.append({
            "agent": name,
            "ms": round((time.perf_counter() - start) * 1000, 3),
            "summary": self._summarise(name, result),
        })
        return result

    @staticmethod
    def _summarise(name, result):
        if name == "trace_intake":
            return f"valid={result['valid']} missing={result['missing']}"
        if name == "dbt_lookup":
            m = result.get("matched")
            return f"matched={'yes' if m else 'no'} via {result.get('method')}"
        if name == "credit_check":
            return f"status={result['status']}"
        if name == "reconcile":
            return f"shortfall={result.get('shortfall')}"
        if name == "fraud_detect":
            return f"severity={result.get('severity')} flags={len(result.get('flags', []))}"
        if name == "orchestrate":
            return f"verdict={result['verdict']} conf={result['confidence']}"
        if name == "grievance_notice":
            return f"authority={result.get('authority')}"
        return "ok"

    def run(self, complaint: dict, user: dict = None) -> dict:
        log = []
        ctx = {}
        ctx["intake"] = self._step(log, "trace_intake", self.intake.run, complaint, user)
        ctx["lookup"] = self._step(log, "dbt_lookup", self.lookup.run, ctx)
        ctx["credit"] = self._step(log, "credit_check", self.credit.run, ctx)
        ctx["reconcile"] = self._step(log, "reconcile", self.reconcile.run, ctx)
        ctx["fraud"] = self._step(log, "fraud_detect", self.fraud.run, ctx)
        ctx["finding"] = self._step(log, "orchestrate", self.orchestrator.run, ctx)
        notice = self._step(log, "grievance_notice", self.notice.run, ctx)

        return {
            "beneficiary": ctx["intake"].get("beneficiary"),
            "complaint": ctx["intake"]["complaint"],
            "matched_transaction": ctx["lookup"].get("matched"),
            "candidates": ctx["lookup"].get("candidates", []),
            "finding": ctx["finding"],
            "escalation": {
                "authority": notice.get("authority"),
                "deadline_days": notice.get("deadline_days"),
            },
            "notice": notice,
            "trace": log,
        }


def trace_complaint(complaint: dict, user: dict = None) -> dict:
    """Convenience one-shot entrypoint."""
    return TracePipeline().run(complaint, user)
