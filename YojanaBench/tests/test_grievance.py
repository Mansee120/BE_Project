"""Tests for the grievance / DBT money-trace module (auth, trace, complaints)."""
import pytest
from fastapi.testclient import TestClient

from backend import auth, complaints as complaints_mod, config, dbt
from backend.app import app
from backend.trace import TracePipeline, trace_complaint

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    """Keep tests off the real runtime/ files."""
    monkeypatch.setattr(config, "COMPLAINTS_PATH", str(tmp_path / "complaints.json"))
    monkeypatch.setattr(config, "USERS_PATH", str(tmp_path / "users.json"))


def _token(username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(username="geeta", password="geeta123"):
    return {"Authorization": "Bearer " + _token(username, password)}


# --- password hashing --------------------------------------------------------
def test_password_hash_roundtrip():
    stored = auth.hash_password("s3cret")
    assert stored.startswith("pbkdf2_sha256$")
    assert auth.verify_password("s3cret", stored)
    assert not auth.verify_password("wrong", stored)
    assert not auth.verify_password("s3cret", "garbage")


def test_password_salt_is_random():
    assert auth.hash_password("x") != auth.hash_password("x")


# --- tokens ------------------------------------------------------------------
def test_token_create_and_verify():
    user = {"username": "ravi", "role": "beneficiary", "name": "Ravi",
            "beneficiary_id": "B-0001"}
    token = auth.create_token(user, ttl=60)
    payload = auth.verify_token(token)
    assert payload["sub"] == "ravi"
    assert payload["role"] == "beneficiary"
    assert payload["beneficiary_id"] == "B-0001"


def test_token_tamper_rejected():
    token = auth.create_token({"username": "ravi", "role": "beneficiary"})
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert auth.verify_token(tampered) is None
    assert auth.verify_token("not-a-token") is None


def test_expired_token_rejected():
    token = auth.create_token({"username": "ravi", "role": "beneficiary"}, ttl=-1)
    assert auth.verify_token(token) is None


# --- auth API ----------------------------------------------------------------
def test_login_and_me():
    headers = _auth("geeta")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "beneficiary"
    assert body["beneficiary_id"] == "B-0004"


def test_login_bad_credentials():
    r = client.post("/api/auth/login", json={"username": "geeta", "password": "nope"})
    assert r.status_code == 401


def test_missing_and_bogus_token():
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me",
                      headers={"Authorization": "Bearer bogus"}).status_code == 401


# --- dbt loader --------------------------------------------------------------
def test_dbt_lookup_helpers():
    txn = dbt.find_by_utr("utr2026pmayg0001")  # case-insensitive
    assert txn is not None
    assert txn["beneficiary_id"] == "B-0004"
    assert dbt.get_beneficiary("B-0004")["name"] == "Geeta Kumari"


def test_mule_account_shared_by_multiple_beneficiaries():
    usage = dbt.account_usage("9999")
    beneficiaries = {t["beneficiary_id"] for t in usage}
    assert len(beneficiaries) >= 3


# --- trace pipeline verdicts -------------------------------------------------
@pytest.mark.parametrize("complaint,verdict", [
    ({"scheme_id": "PMKISAN-2023", "utr": "UTR2026PMK0001", "beneficiary_id": "B-0001"}, "received"),
    ({"scheme_id": "IGNOAPS-2023", "utr": "UTR2026IGNOAPS0001", "beneficiary_id": "B-0002"}, "not_credited"),
    ({"scheme_id": "MGNREGA-2023", "utr": "UTR2026MGN0001", "beneficiary_id": "B-0003"}, "partial"),
    ({"scheme_id": "NSP-PREMATRIC-2023", "utr": "UTR2026NSP0002", "beneficiary_id": "B-0007"}, "failed"),
    ({"scheme_id": "IGNDPS-2023", "utr": "UTR2026IGNDPS0002", "beneficiary_id": "B-0010"}, "diverted"),
    ({"scheme_id": "PMKISAN-2023", "beneficiary_id": "B-9999"}, "not_found"),
    ({"description": "money not received"}, "needs_info"),
])
def test_trace_verdicts(complaint, verdict):
    result = trace_complaint(complaint)
    assert result["finding"]["verdict"] == verdict


def test_trace_diversion_flags_and_mule_ring():
    result = trace_complaint({"scheme_id": "PMAYG-2023", "utr": "UTR2026PMAYG0001",
                              "beneficiary_id": "B-0004"})
    finding = result["finding"]
    assert finding["diversion"] is True
    assert finding["mule_ring"] is True
    assert finding["money_reached_beneficiary"] is False
    assert finding["severity"] == "high"


def test_trace_runs_all_seven_agents():
    result = trace_complaint({"scheme_id": "PMKISAN-2023", "utr": "UTR2026PMK0001"})
    assert [t["agent"] for t in result["trace"]] == TracePipeline.AGENT_NAMES
    assert result["notice"]["body_text"]


def test_trace_matches_despite_partial_amount_shortfall():
    result = trace_complaint({"scheme_id": "MGNREGA-2023", "utr": "UTR2026MGN0001"})
    assert result["finding"]["shortfall"] == 3000.0


# --- trace API ---------------------------------------------------------------
def test_trace_endpoint_scopes_to_own_beneficiary():
    headers = _auth("geeta")
    r = client.post("/api/trace", headers=headers,
                    json={"scheme_id": "PMAYG-2023", "utr": "UTR2026PMAYG0001"})
    assert r.status_code == 200
    assert r.json()["finding"]["verdict"] == "diverted"


def test_trace_endpoint_requires_auth():
    r = client.post("/api/trace", json={"scheme_id": "PMAYG-2023"})
    assert r.status_code == 401


# --- complaint workflow ------------------------------------------------------
def test_file_complaint_and_role_scoping():
    bene = _auth("geeta")
    r = client.post("/api/complaints", headers=bene,
                    json={"scheme_id": "PMAYG-2023", "utr": "UTR2026PMAYG0001",
                          "description": "housing money missing"})
    assert r.status_code == 200
    cid = r.json()["complaint_id"]

    mine = client.get("/api/complaints", headers=bene).json()["complaints"]
    assert any(c["complaint_id"] == cid for c in mine)

    # A different beneficiary cannot open it.
    other = _auth("ravi", "ravi123")
    assert client.get(f"/api/complaints/{cid}", headers=other).status_code == 403

    # Officials see every complaint and the summary.
    officer = _auth("officer", "officer123")
    all_c = client.get("/api/complaints", headers=officer).json()["complaints"]
    assert any(c["complaint_id"] == cid for c in all_c)
    summary = client.get("/api/complaints/summary", headers=officer).json()
    assert summary["total"] >= 1
    assert summary["diverted"] >= 1


def test_beneficiary_cannot_use_officer_endpoints():
    bene = _auth("geeta")
    assert client.get("/api/complaints/summary", headers=bene).status_code == 403


def test_officer_updates_status():
    bene = _auth("geeta")
    cid = client.post("/api/complaints", headers=bene,
                      json={"scheme_id": "PMAYG-2023", "utr": "UTR2026PMAYG0001"}
                      ).json()["complaint_id"]
    officer = _auth("officer", "officer123")
    r = client.patch(f"/api/complaints/{cid}/status", headers=officer,
                     json={"status": "under_review", "note": "checking bank"})
    assert r.status_code == 200
    assert r.json()["status"] == "under_review"
    assert r.json()["history"][-1]["note"] == "checking bank"


def test_invalid_status_rejected():
    officer = _auth("officer", "officer123")
    cid = client.post("/api/complaints", headers=officer,
                      json={"scheme_id": "PMAYG-2023", "utr": "UTR2026PMAYG0001"}
                      ).json()["complaint_id"]
    r = client.patch(f"/api/complaints/{cid}/status", headers=officer,
                     json={"status": "bogus"})
    assert r.status_code == 400


def test_beneficiary_reads_own_ledger_only():
    headers = _auth("geeta")
    r = client.get("/api/beneficiaries/B-0004", headers=headers)
    assert r.status_code == 200
    assert r.json()["beneficiary"]["beneficiary_id"] == "B-0004"
    # not their record
    assert client.get("/api/beneficiaries/B-0001", headers=headers).status_code == 403


def test_register_beneficiary_account():
    officer = _auth("admin", "admin123")
    r = client.post("/api/auth/register", headers=officer,
                    json={"username": "newuser", "password": "pw12345",
                          "role": "beneficiary", "name": "New User",
                          "beneficiary_id": "B-0005"})
    assert r.status_code == 200
    assert r.json()["beneficiary_id"] == "B-0005"
    # duplicate rejected
    r2 = client.post("/api/auth/register", headers=officer,
                     json={"username": "newuser", "password": "pw12345",
                           "role": "beneficiary", "beneficiary_id": "B-0005"})
    assert r2.status_code == 400


def test_beneficiary_cannot_register_official():
    bene = _auth("geeta")
    r = client.post("/api/auth/register", headers=bene,
                    json={"username": "fakeofficer", "password": "pw12345",
                          "role": "official"})
    assert r.status_code == 403
