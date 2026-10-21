"""Tests for deterministic fake / tampered-document detection."""
from backend.document_integrity import (
    check_integrity, apply_tamper, BPL_INCOME_LIMIT,
)
from backend.pipeline import pipeline


def codes(flags):
    return {f["code"] for f in flags}


# ----------------------------- impossible values ---------------------------
def test_impossible_values_are_flagged():
    flags = check_integrity({"age": 150, "disability_percent": 150,
                             "family_size": 99}, None)
    assert {"age_invalid", "disability_invalid", "family_size_invalid"} <= codes(flags)


def test_negative_and_implausible_income():
    assert "income_negative" in codes(check_integrity({"annual_income": -100}, None))
    assert "income_implausible" in codes(
        check_integrity({"annual_income": 999_999_999}, None))


def test_clean_applicant_has_no_flags():
    assert check_integrity({"age": 40, "annual_income": 90_000, "bpl": True}, None) == []


# ----------------------------- contradictions ------------------------------
def test_bpl_income_contradiction():
    flags = check_integrity(
        {"bpl": True, "annual_income": BPL_INCOME_LIMIT + 1}, None)
    assert "bpl_income_contradiction" in codes(flags)
    assert any(f["severity"] == "high" for f in flags)


def test_income_tax_contradiction():
    flags = check_integrity(
        {"is_income_tax_payer": True, "annual_income": 100_000}, None)
    assert "income_tax_contradiction" in codes(flags)


def test_card_bpl_contradiction_both_ways():
    a = check_integrity({"card_type": "AAY", "bpl": False}, None)
    b = check_integrity({"card_type": "APL", "bpl": True}, None)
    assert "card_bpl_contradiction" in codes(a)
    assert "card_bpl_contradiction" in codes(b)


def test_widow_and_education_age_contradictions():
    assert "widow_age_contradiction" in codes(
        check_integrity({"is_widow": True, "age": 15}, None))
    assert "education_age_contradiction" in codes(
        check_integrity({"education_level": "UG", "age": 15}, None))


def test_secc_pucca_contradiction():
    assert "secc_pucca_contradiction" in codes(
        check_integrity({"secc_listed": True, "owns_pucca_house": True}, None))


# ----------------------------- evidence checks -----------------------------
def _scheme(*docs):
    return {"required_documents": [{"name": d, "mandatory": True} for d in docs]}


def test_unsupported_claim_when_backing_doc_missing():
    scheme = _scheme("BPL Card", "Aadhaar Card")
    flags = check_integrity({"bpl": True}, scheme, ["Aadhaar Card"],
                            documents_assumed_complete=False)
    assert "unsupported_claim" in codes(flags)


def test_claim_supported_by_submitted_doc_is_clean():
    scheme = _scheme("BPL Card", "Aadhaar Card")
    flags = check_integrity({"bpl": True}, scheme, ["BPL Card", "Aadhaar Card"],
                            documents_assumed_complete=False)
    assert "unsupported_claim" not in codes(flags)


def test_evidence_checks_neutral_without_document_list():
    scheme = _scheme("BPL Card")
    assert check_integrity({"bpl": True}, scheme, None,
                           documents_assumed_complete=True) == []


def test_scheme_not_requiring_proof_does_not_flag_claim():
    scheme = _scheme("Aadhaar Card")
    assert "unsupported_claim" not in codes(
        check_integrity({"bpl": True}, scheme, ["Aadhaar Card"],
                        documents_assumed_complete=False))


# ----------------------------- tamper simulation ---------------------------
def test_omit_removes_submitted_document():
    app, docs, changes = apply_tamper({}, ["Aadhaar Card", "BPL Card"],
                                      "Aadhaar Card", "omit")
    assert docs == ["BPL Card"]
    assert changes[0]["location"] == "submitted_documents"


def test_forge_income_creates_tax_contradiction():
    app, docs, _ = apply_tamper({}, ["Income Certificate", "Aadhaar Card"],
                                "Income Certificate", "forge")
    assert "income_tax_contradiction" in codes(check_integrity(app, None))


def test_forge_age_creates_invalid_age():
    app, _, _ = apply_tamper({}, ["Age Proof"], "Age Proof", "forge")
    assert "age_invalid" in codes(check_integrity(app, None))


def test_unknown_tamper_action_raises():
    try:
        apply_tamper({}, ["Aadhaar Card"], "Aadhaar Card", "shred")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ----------------------------- pipeline integration ------------------------
def test_verification_agent_reports_integrity_flags():
    result = pipeline.run_case("PDS-NFSA-2023",
                               {"bpl": True, "annual_income": 900_000})
    integ = result["verification"]["integrity_flags"]
    assert any(f["code"] == "bpl_income_contradiction" for f in integ)


def test_high_integrity_flag_raises_human_gate():
    result = pipeline.run_case("PDS-NFSA-2023",
                               {"bpl": True, "annual_income": 900_000})
    assert result["verdict"]["document_integrity"]["suspected_forgery"] is True
    assert result["verdict"]["human_approval_required"] is True


def test_clean_case_has_no_integrity_flags():
    result = pipeline.run_case("PDS-NFSA-2023",
                               {"age": 35, "card_type": "AAY", "bpl": True,
                                "family_size": 4})
    assert result["verification"]["integrity_flags"] == []
    assert result["verdict"]["document_integrity"]["suspected_forgery"] is False
