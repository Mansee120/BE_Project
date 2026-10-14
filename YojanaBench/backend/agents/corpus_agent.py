"""
corpus_agent.py  (Agent 1/8)
----------------------------
Offline ingestion agent. Loads the scheme schemas and the rendered guideline
documents, flattens them into a clause-level corpus and builds the hybrid
retriever that every online agent relies on.

Output:
  * self.schemes          -> {scheme_id: schema}
  * self.clauses          -> list of clause dicts (doc_id, scheme_id, type, text)
  * self.retriever        -> HybridRetriever over self.clauses
  * self.stats            -> dataset statistics for the dashboard
"""
import json
import os

from .. import config
from ..retrieval import HybridRetriever


class CorpusAgent:
    def __init__(self, dataset_dir: str = None):
        self.dataset_dir = dataset_dir or config.DATASET_DIR
        self.schemes = {}
        self.clauses = []
        self.guideline_texts = {}
        self.retriever = None
        self.stats = {}
        self.load()

    # -- loading --------------------------------------------------------------
    def _load_schemes(self):
        schemes_dir = os.path.join(self.dataset_dir, "schemes")
        for fname in sorted(os.listdir(schemes_dir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(schemes_dir, fname), "r", encoding="utf-8") as f:
                scheme = json.load(f)
            self.schemes[scheme["scheme_id"]] = scheme

    def _load_guidelines(self):
        gdir = os.path.join(self.dataset_dir, "guidelines")
        if not os.path.isdir(gdir):
            return
        for fname in sorted(os.listdir(gdir)):
            if not fname.endswith(".txt"):
                continue
            with open(os.path.join(gdir, fname), "r", encoding="utf-8") as f:
                self.guideline_texts[fname[:-4]] = f.read()

    def _build_clauses(self):
        """Flatten every scheme into clause-level retrievable units."""
        self.clauses = []
        for sid, scheme in self.schemes.items():
            prefix = sid.split("-")[0]

            # Eligibility clauses
            for c in scheme["eligibility_clauses"]:
                self.clauses.append({
                    "doc_id": c["clause_id"],
                    "scheme_id": sid,
                    "type": "eligibility",
                    "text": f"Eligibility criterion for {scheme['name']}: {c['text']}",
                    "source": f"{sid} guidelines, Eligibility section",
                })

            # Entitlement rules
            for e in scheme["entitlement_rules"]:
                self.clauses.append({
                    "doc_id": e["rule_id"],
                    "scheme_id": sid,
                    "type": "entitlement",
                    "text": f"Entitlement / benefit rule for {scheme['name']}: {e['text']}",
                    "source": f"{sid} guidelines, Entitlement section",
                })

            # Required documents
            for d in scheme["required_documents"]:
                tag = "mandatory" if d.get("mandatory", True) else "optional"
                self.clauses.append({
                    "doc_id": d["doc_id"],
                    "scheme_id": sid,
                    "type": "documents",
                    "text": f"{tag.capitalize()} document required for {scheme['name']}: {d['name']}",
                    "source": f"{sid} guidelines, Documents section",
                })

            # Appeal hierarchy
            for a in scheme["appeal_hierarchy"]:
                self.clauses.append({
                    "doc_id": f"{prefix}-APL{a['level']}",
                    "scheme_id": sid,
                    "type": "appeal",
                    "text": (f"Appeal level {a['level']} for {scheme['name']}: "
                             f"{a['authority']} within {a['deadline_days']} days. {a['description']}"),
                    "source": f"{sid} guidelines, Grievance section",
                })

    def _compute_stats(self):
        """Aggregate dataset statistics reported on the dashboard."""
        per_scheme = {}
        for c in self.clauses:
            per_scheme.setdefault(c["scheme_id"], 0)
            per_scheme[c["scheme_id"]] += 1
        total_chars = sum(len(t) for t in self.guideline_texts.values())
        est_pages = round(total_chars / 1800, 1)  # ~1800 chars per guideline page
        by_type = {}
        for c in self.clauses:
            by_type[c["type"]] = by_type.get(c["type"], 0) + 1
        self.stats = {
            "schemes": len(self.schemes),
            "guideline_documents": len(self.guideline_texts),
            "clauses": len(self.clauses),
            "chunks": len(self.clauses),
            "estimated_pages": est_pages,
            "by_type": by_type,
            "per_scheme_clauses": per_scheme,
        }
        # QA benchmark stats are added lazily by the evaluation agent / app.
        qa_path = os.path.join(self.dataset_dir, "qa_benchmark.json")
        if not os.path.exists(qa_path):
            qa_path = os.path.join(self.dataset_dir, "qa", "qa_benchmark.json")
        if os.path.exists(qa_path):
            with open(qa_path, "r", encoding="utf-8") as f:
                qa = json.load(f)
            items = qa.get("items", [])
            cat_counts = {}
            edge_count = 0
            cf_count = 0
            for it in items:
                cat_counts[it["category"]] = cat_counts.get(it["category"], 0) + 1
                if it.get("edge_case"):
                    edge_count += 1
                if it.get("counterfactual_of"):
                    cf_count += 1
            self.stats["qa_pairs"] = len(items)
            self.stats["qa_by_category"] = cat_counts
            self.stats["qa_edge_cases"] = edge_count
            self.stats["qa_counterfactuals"] = cf_count

    # -- public ---------------------------------------------------------------
    def load(self):
        self._load_schemes()
        self._load_guidelines()
        self._build_clauses()
        self.retriever = HybridRetriever(self.clauses)
        self._compute_stats()
        return self

    def get_scheme(self, scheme_id: str):
        return self.schemes.get(scheme_id)

    def list_schemes(self):
        """Compact scheme summaries for the API/UI."""
        out = []
        for sid, s in self.schemes.items():
            out.append({
                "scheme_id": sid,
                "name": s["name"],
                "level": s["level"],
                "state": s.get("state", "All India"),
                "category": s["category"],
                "summary": s["summary"],
                "n_eligibility": len(s["eligibility_clauses"]),
                "n_entitlement": len(s["entitlement_rules"]),
                "n_documents": len(s["required_documents"]),
                "n_appeal_levels": len(s["appeal_hierarchy"]),
            })
        return out
