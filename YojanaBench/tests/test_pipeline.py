"""End-to-end tests for the multi-agent pipeline and benchmark metrics."""
import json

from backend import config
from backend.pipeline import Pipeline


def _expected_qa_count():
    with open(config.QA_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return len(json.load(f).get("items", []))


FULL_DOCS = {
    "IGNOAPS-2023": ["Age Proof (Birth Certificate/School Certificate)",
                     "BPL Card", "Aadhaar Card", "Bank Account Passbook"],
}


def make_pipeline():
    return Pipeline()


def test_eligible_case():
    p = make_pipeline()
    r = p.run_case("IGNOAPS-2023", {"age": 65, "bpl": True},
                   submitted_documents=FULL_DOCS["IGNOAPS-2023"])
    assert r["verdict"]["decision"] == "eligible"
    assert r["verdict"]["computed_entitlement"] == 200
    assert r["verdict"]["entitlement_unit"] == "INR/month"
    assert r["verdict"]["confidence"] >= 0.6


def test_ineligible_case():
    p = make_pipeline()
    r = p.run_case("IGNOAPS-2023", {"age": 58, "bpl": True},
                   submitted_documents=FULL_DOCS["IGNOAPS-2023"])
    assert r["verdict"]["decision"] == "ineligible"


def test_needs_info_when_document_missing():
    p = make_pipeline()
    r = p.run_case("IGNOAPS-2023", {"age": 65, "bpl": True},
                   submitted_documents=["BPL Card", "Aadhaar Card"])
    assert r["verdict"]["decision"] == "needs_info"
    assert "Bank Account Passbook" in r["verdict"]["missing_documents"]


def test_appeal_generated_for_rejection():
    p = make_pipeline()
    r = p.run_case("IGNOAPS-2023", {"age": 58, "bpl": True},
                   submitted_documents=FULL_DOCS["IGNOAPS-2023"])
    assert r["appeal"]["applicable"] is True
    assert "Block Development Officer" in r["appeal"]["channel"]
    assert "Appeal" in r["appeal"]["draft_letter"]


def test_entitlement_boundary_age():
    p = make_pipeline()
    r79 = p.run_case("IGNOAPS-2023", {"age": 79, "bpl": True})
    r80 = p.run_case("IGNOAPS-2023", {"age": 80, "bpl": True})
    assert r79["verdict"]["computed_entitlement"] == 200
    assert r80["verdict"]["computed_entitlement"] == 500


def test_benchmark_metrics_are_strong():
    p = make_pipeline()
    result = p.run_benchmark()
    m = result["metrics"]
    assert m["count"] == _expected_qa_count()
    assert m["verdict_accuracy"] >= 0.9
    assert m["entitlement_error_abs"] == 0
    assert m["document_f1"] == 1.0
    assert m["calibration_ece"] < 0.15


def test_benchmark_filter_by_scheme():
    p = make_pipeline()
    result = p.run_benchmark(scheme_id="PDS-NFSA-2023")
    assert all(r["scheme_id"] == "PDS-NFSA-2023" for r in result["rows"])
