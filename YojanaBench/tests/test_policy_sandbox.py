"""Tests for the Policy Sandbox (what-if rule simulator)."""
import copy

from fastapi.testclient import TestClient

from backend.app import app
from backend.policy_sandbox import PolicySandbox, patch_scheme
from backend.pipeline import pipeline

client = TestClient(app)
sandbox = PolicySandbox()

SCHEME = "IGNOAPS-2023"   # pension: age >= 60, entitlement 600/month


# ----------------------------- field discovery -----------------------------
def test_fields_reports_patchable_rules():
    data = sandbox.fields(SCHEME)
    names = [f["field"] for f in data["fields"]]
    assert "age" in names
    age = next(f for f in data["fields"] if f["field"] == "age")
    assert age["is_numeric"] is True
    assert age["current_value"] == 60


def test_fields_unknown_scheme_raises():
    try:
        sandbox.fields("NOPE-9999")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ----------------------------- scheme patching -----------------------------
def test_patch_replaces_threshold_without_mutating_original():
    scheme = pipeline.corpus.get_scheme(SCHEME)
    snapshot = copy.deepcopy(scheme)
    patched, changes = patch_scheme(scheme, "age", 55)
    assert scheme == snapshot, "original corpus scheme must not be mutated"
    assert changes, "at least one clause should be patched"
    c1 = next(c for c in patched["eligibility_clauses"] if c["clause_id"] == "IGNOAPS-C1")
    assert c1["value"] == 55


def test_patch_on_unknown_field_is_empty():
    scheme = pipeline.corpus.get_scheme(SCHEME)
    _, changes = patch_scheme(scheme, "shoe_size", 12)
    assert changes == []


# ----------------------------- simulation ----------------------------------
def test_loosening_age_adds_eligibles_and_budget():
    r = sandbox.simulate(SCHEME, "age", 55)
    assert r["cohort_size"] > 0
    assert r["newly_eligible"] >= 1
    assert r["newly_ineligible"] == 0
    assert r["after"]["eligible"] == r["before"]["eligible"] + r["newly_eligible"] - r["newly_ineligible"]
    assert r["budget_delta"] > 0
    assert r["after"]["budget_total"] > r["before"]["budget_total"]


def test_raising_threshold_keeps_or_shrinks_cohort():
    r = sandbox.simulate(SCHEME, "age", 80)
    assert r["newly_eligible"] == 0
    assert r["after"]["eligible"] <= r["before"]["eligible"]
    assert r["budget_delta"] <= 0


def test_simulation_lists_only_changed_applicants():
    r = sandbox.simulate(SCHEME, "age", 55)
    for row in r["affected"]:
        assert row["before"] != row["after"] or \
               row["entitlement_before"] != row["entitlement_after"]


def test_simulate_unknown_field_raises():
    try:
        sandbox.simulate(SCHEME, "shoe_size", 12)
        assert False, "expected ValueError"
    except ValueError:
        pass


# ----------------------------- API endpoints --------------------------------
def test_api_sandbox_fields():
    resp = client.get("/api/sandbox/fields", params={"scheme_id": SCHEME})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheme_id"] == SCHEME
    assert any(f["field"] == "age" for f in data["fields"])


def test_api_sandbox_fields_404():
    resp = client.get("/api/sandbox/fields", params={"scheme_id": "NOPE-9999"})
    assert resp.status_code == 404


def test_api_sandbox_simulate():
    resp = client.post("/api/sandbox/simulate", json={
        "scheme_id": SCHEME, "field": "age", "new_value": 55})
    assert resp.status_code == 200
    data = resp.json()
    assert data["newly_eligible"] >= 1
    assert data["budget_delta"] > 0


def test_api_sandbox_simulate_400_on_bad_field():
    resp = client.post("/api/sandbox/simulate", json={
        "scheme_id": SCHEME, "field": "shoe_size", "new_value": 12})
    assert resp.status_code == 400


# ----------------------------- document-tamper mode ------------------------
def test_omit_document_catches_missing_papers():
    r = sandbox.simulate_document(SCHEME, "Aadhaar Card", "omit")
    assert r["mode"] == "document"
    assert r["affected_count"] >= 1
    assert "missing_mandatory_document" in r["flags_detected"]


def test_forge_document_is_detected():
    r = sandbox.simulate_document("PDS-NFSA-2023", "Ration Card", "forge")
    assert r["affected_count"] >= 1
    assert "card_bpl_contradiction" in r["flags_detected"]
    assert r["strategy"]


def test_document_mode_rejects_unknown_action():
    try:
        sandbox.simulate_document(SCHEME, "Aadhaar Card", "shred")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_api_sandbox_simulate_document_mode():
    resp = client.post("/api/sandbox/simulate", json={
        "mode": "document", "scheme_id": SCHEME,
        "document": "Aadhaar Card", "action": "omit"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "document"
    assert data["affected_count"] >= 1


def test_api_sandbox_document_mode_requires_fields():
    resp = client.post("/api/sandbox/simulate", json={
        "mode": "document", "scheme_id": SCHEME})
    assert resp.status_code == 400

