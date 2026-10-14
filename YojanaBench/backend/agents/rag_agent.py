"""
rag_agent.py  (Agent 3/8)
-------------------------
Retrieval-Augmented-Generation agent. Given a CaseRecord it builds a natural
language query from the applicant profile and pulls the most relevant clauses
from the corpus (hybrid BM25 + TF-IDF). Evidence is returned with clause IDs and
source pages so the verdict can cite where each rule came from.
"""
from .. import config


class RAGAgent:
    def __init__(self, corpus):
        self.corpus = corpus

    def _build_query(self, case: dict, focus: list = None) -> str:
        """Compose a retrieval query from the applicant profile + focus types."""
        parts = [case["scheme_name"]]
        applicant = case["applicant"]
        for key, value in applicant.items():
            parts.append(f"{key} {value}")
        if focus and "document" in focus[0]:
            parts.append("required documents checklist")
        if focus and "appeal" in focus[0]:
            parts.append("appeal grievance authority deadline")
        return " ".join(str(p) for p in parts)

    def run(self, case: dict, top_k: int = None, clause_types: list = None) -> dict:
        query = self._build_query(case, focus=clause_types)
        evidence = self.corpus.retriever.search(
            query,
            top_k=top_k or config.TOP_K,
            scheme_id=case["scheme_id"],
            clause_types=clause_types,
        )
        return {"query": query, "evidence": evidence}

    def evidence_for_scheme(self, case: dict) -> dict:
        """A wider evidence pack used by the audit (all clause types)."""
        return self.run(case, top_k=10)
