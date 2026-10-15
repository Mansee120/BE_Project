"""Unit tests for the rule engine, retriever, corpus and intake agent."""
import json
import os

from backend import config
from backend.condition_eval import evaluate, evaluate_all
from backend.agents import CorpusAgent, IntakeAgent


def _expected_qa_count():
    with open(config.QA_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return len(json.load(f).get("items", []))


def _expected_scheme_count():
    return len([f for f in os.listdir(config.SCHEMES_DIR)
                if f.endswith(".json")])


# ----------------------------- condition engine -----------------------------
def test_numeric_comparisons():
    assert evaluate({"age": 65}, {"field": "age", "operator": "gte", "value": 60}) is True
    assert evaluate({"age": 58}, {"field": "age", "operator": "gte", "value": 60}) is False
    assert evaluate({"age": 60}, {"field": "age", "operator": "gte", "value": 60}) is True


def test_missing_field_is_unknown():
    assert evaluate({}, {"field": "age", "operator": "gte", "value": 60}) is None


def test_membership_is_case_insensitive():
    cond = {"field": "category", "operator": "in", "value": ["SC", "ST"]}
    assert evaluate({"category": "sc"}, cond) is True
    assert evaluate({"category": "General"}, cond) is False


def test_compound_and_or():
    comp = {"operator": "and", "clauses": [
        {"field": "age", "operator": "gte", "value": 60},
        {"field": "bpl", "operator": "eq", "value": True},
    ]}
    assert evaluate({"age": 65, "bpl": True}, comp) is True
    assert evaluate({"age": 65, "bpl": False}, comp) is False
    assert evaluate({"age": 65}, comp) is None  # bpl unknown


def test_evaluate_all_summary():
    clauses = [
        {"clause_id": "A", "text": "t", "field": "age", "operator": "gte", "value": 60, "mandatory": True},
        {"clause_id": "B", "text": "t", "field": "bpl", "operator": "eq", "value": True, "mandatory": True},
    ]
    out = evaluate_all({"age": 65, "bpl": True}, clauses)
    assert out["passed"] is True and out["any_false"] is False
    out2 = evaluate_all({"age": 50, "bpl": True}, clauses)
    assert out2["any_false"] is True


# --------------------------------- corpus -----------------------------------
def test_corpus_loads_all_schemes():
    corpus = CorpusAgent()
    assert len(corpus.schemes) == _expected_scheme_count()
    assert corpus.stats["clauses"] > 0
    assert corpus.stats["qa_pairs"] == _expected_qa_count()


def test_retriever_finds_relevant_clause():
    corpus = CorpusAgent()
    hits = corpus.retriever.search(
        "monthly pension for old age 65 years BPL",
        top_k=5, scheme_id="IGNOAPS-2023")
    ids = [h["doc_id"] for h in hits]
    assert any(i.startswith("IGNOAPS") for i in ids)
    assert all(h["scheme_id"] == "IGNOAPS-2023" for h in hits)


# --------------------------------- intake -----------------------------------
def test_intake_normalises_income_in_lakhs():
    corpus = CorpusAgent()
    intake = IntakeAgent(corpus)
    case = intake.run("PMS-SC-2023", {"income": 2.5, "category": "SC"})
    assert case["applicant"]["annual_income"] == 250000


def test_intake_detects_missing_documents():
    corpus = CorpusAgent()
    intake = IntakeAgent(corpus)
    case = intake.run("IGNOAPS-2023", {"age": 65, "bpl": True},
                      submitted_documents=["BPL Card"])
    assert "Bank Account Passbook" in case["missing_documents"]
