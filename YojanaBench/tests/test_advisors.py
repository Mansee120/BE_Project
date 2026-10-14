"""Unit tests for the counterfactual and document-gap advisory agents."""
from backend.pipeline import Pipeline

# Fresh pipeline shared by the module (cheap, deterministic, no LLM needed).
pipe = Pipeline()


# ------------------------- counterfactual advisor ---------------------------
def test_counterfactual_changeable_ages(monkeypatch):
    """Age below the lower bound is fixable by waiting -> feasible, alone."""
    r = pipe.run_case("IGNOAPS-2023", {"age": 55, "bpl": True})
    cf = r["counterfactual"]
    assert cf["current_decision"] == "ineligible"
    assert cf["feasible"] is True
    assert cf["min_changes"] == 1
    assert "age" in cf["can_flip_alone"]
    age = [s for s in cf["suggestions"] if s["field"] == "age"][0]
    assert age["required"] == 60
    assert age["changeable"] is True
    assert age["alone_sufficient"] is True
    assert "age 60" in cf["summary"]


def test_counterfactual_immutable_blocker():
    """BPL status is not changeable by the applicant -> infeasible with blocker."""
    r = pipe.run_case("IGNOAPS-2023", {"age": 65, "bpl": False})
    cf = r["counterfactual"]
    assert cf["feasible"] is False
    assert cf["can_flip_alone"] == []
    blockers = [s for s in cf["suggestions"] if not s["changeable"]]
    assert any(s["field"] == "bpl" for s in blockers)
    assert len(cf["blockers"]) >= 1
    assert "cannot be modified" in cf["summary"]


def test_counterfactual_income_reduction():
    """Income above the ceiling is fixable by reducing income."""
    r = pipe.run_case("PMS-SC-2023", {"category": "SC", "annual_income": 300000})
    cf = r["counterfactual"]
    inc = [s for s in cf["suggestions"] if s["field"] == "annual_income"][0]
    assert inc["required"] <= 250000
    assert inc["changeable"] is True
    assert "annual_income" in cf["can_flip_alone"]


def test_counterfactual_eligible_has_no_changes():
    r = pipe.run_case("IGNOAPS-2023", {"age": 65, "bpl": True},
                      submitted_documents=[
                          "Age Proof (Birth Certificate/School Certificate)",
                          "BPL Card", "Aadhaar Card", "Bank Account Passbook"])
    cf = r["counterfactual"]
    assert cf["current_decision"] == "eligible"
    assert cf["feasible"] is True
    assert cf["min_changes"] == 0
    assert cf["can_flip_alone"] == []


def test_counterfactual_unknown_fields_suggest_info():
    """Missing fields are reported as information to provide, not blockers."""
    r = pipe.run_case("PMS-SC-2023", {"category": "SC"})
    cf = r["counterfactual"]
    assert "education_level" in cf["missing_info_fields"]
    missing = [s for s in cf["suggestions"] if s["kind"] == "missing_info"]
    assert missing


# --------------------------- document-gap analyzer --------------------------
def test_document_gap_detects_missing_docs():
    r = pipe.run_case("IGNOAPS-2023", {"age": 65, "bpl": True},
                      submitted_documents=["Aadhaar Card"])
    dg = r["document_gap"]
    assert dg["has_gap"] is True
    assert dg["gate_blocking"] is True
    assert dg["eligibility_without_docs"] == "eligible"
    assert dg["verdict_if_docs_complete"] == "eligible"
    assert len(dg["missing_documents"]) >= 1
    assert dg["documents"][0]["priority"] == 1
    assert dg["documents"][0]["alone_unblocks"] is (len(dg["missing_documents"]) == 1)
    assert "missing mandatory document" in dg["resolution"]


def test_document_gap_none_when_complete():
    r = pipe.run_case("IGNOAPS-2023", {"age": 65, "bpl": True},
                      submitted_documents=[
                          "Age Proof (Birth Certificate/School Certificate)",
                          "BPL Card", "Aadhaar Card", "Bank Account Passbook"])
    dg = r["document_gap"]
    assert dg["has_gap"] is False
    assert dg["missing_documents"] == []


def test_document_gap_underlying_ineligible_not_hidden():
    """If the applicant fails the rules, documents can't rescue them."""
    r = pipe.run_case("IGNOAPS-2023", {"age": 55, "bpl": True},
                      submitted_documents=["Aadhaar Card"])
    dg = r["document_gap"]
    assert dg["eligibility_without_docs"] == "ineligible"
    assert dg["verdict_if_docs_complete"] == "ineligible"


def test_pipeline_exposes_advisories():
    r = pipe.run_case("IGNOAPS-2023", {"age": 55, "bpl": True})
    assert "counterfactual" in r and "document_gap" in r
