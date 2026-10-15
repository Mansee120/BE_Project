"""HTTP-level tests for the FastAPI backend."""
import json
import os

from fastapi.testclient import TestClient

from backend import config
from backend.app import app

client = TestClient(app)


def _expected_qa_count():
    with open(config.QA_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return len(json.load(f).get("items", []))


def _expected_scheme_count():
    return len([f for f in os.listdir(config.SCHEMES_DIR)
                if f.endswith(".json")])


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_stats():
    r = client.get("/api/stats")
    body = r.json()
    assert body["schemes"] == _expected_scheme_count()
    assert body["qa_pairs"] == _expected_qa_count()


def test_schemes_listing_and_detail():
    listing = client.get("/api/schemes").json()["schemes"]
    assert len(listing) == _expected_scheme_count()
    detail = client.get("/api/schemes/IGNOAPS-2023").json()
    assert detail["scheme_id"] == "IGNOAPS-2023"


def test_audit_endpoint():
    payload = {
        "scheme_id": "IGNOAPS-2023",
        "applicant": {"age": 65, "bpl": True},
        "submitted_documents": ["Age Proof (Birth Certificate/School Certificate)",
                                "BPL Card", "Aadhaar Card", "Bank Account Passbook"],
    }
    r = client.post("/api/audit", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"]["decision"] == "eligible"
    assert body["verdict"]["computed_entitlement"] == 200


def test_audit_unknown_scheme_404():
    r = client.post("/api/audit", json={"scheme_id": "NOPE", "applicant": {}})
    assert r.status_code == 404


def test_benchmark_endpoint():
    r = client.post("/api/benchmark/run", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["metrics"]["verdict_accuracy"] >= 0.9


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "YojanaBench" in r.text


def test_ablation_endpoint():
    r = client.post("/api/ablation/run", json={})
    assert r.status_code == 200
    variants = [c["variant"] for c in r.json()["comparison"]]
    assert variants == ["full", "no_verification", "llm_math", "no_counterfactuals"]


def test_report_endpoint():
    r = client.get("/api/report")
    assert r.status_code == 200
    body = r.json()
    assert len(body["overall_metrics"]) == 11
    assert len(body["per_scheme_accuracy"]) == _expected_scheme_count()
    assert len(body["ablation_comparison"]) == 4
    assert len(body["item_results"]) == _expected_qa_count()


def test_leaderboard_endpoint():
    r = client.get("/api/leaderboard")
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) >= 1
    # Highest verdict accuracy must rank first and metrics are only known keys.
    assert entries[0]["metrics"]["verdict_accuracy"] >= entries[-1]["metrics"]["verdict_accuracy"]
    assert "name" in entries[0] and "metrics" in entries[0]


# ---------------------------- voice assistant --------------------------------

def test_assistant_status():
    r = client.get("/api/assistant/status")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["schemes"] == _expected_scheme_count()


def test_assistant_english_amount():
    r = client.post("/api/assistant", json={
        "message": "how much amount under pm kisan",
        "lang": "en", "session_id": "t-en-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "amount"
    assert body["scheme_id"] == "PMKISAN-2023"
    assert "6,000" in body["reply"]


def test_assistant_english_documents():
    r = client.post("/api/assistant", json={
        "message": "what documents needed for ration card",
        "lang": "en", "session_id": "t-en-2"})
    body = r.json()
    assert body["intent"] == "documents"
    assert body["scheme_id"] == "PDS-NFSA-2023"


def test_assistant_audit_session():
    sid = "t-audit-1"
    r = client.post("/api/assistant", json={
        "message": "check if i am eligible for old age pension",
        "lang": "en", "session_id": sid})
    assert r.json()["intent"] == "start_audit"
    for answer in ("65", "female", "yes"):
        r = client.post("/api/assistant", json={
            "message": answer, "lang": "en", "session_id": sid})
        assert r.status_code == 200
    body = r.json()
    assert body["data"]["flow"] == "audit_done"
    assert body["data"]["verdict"] == "eligible"


def test_assistant_unknown_has_reply():
    r = client.post("/api/assistant", json={
        "message": "zzqq", "lang": "en", "session_id": "t-en-3"})
    body = r.json()
    assert body["intent"] == "fallback"
    assert body["reply"].strip()


def test_assistant_non_english_reply():
    r = client.post("/api/assistant", json={
        "message": "पीएम किसान में कितना पैसा मिलता है",
        "lang": "hi-IN", "session_id": "t-hi-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "amount"
    assert body["scheme_id"] == "PMKISAN-2023"
    assert body["reply"].strip()


def test_assistant_help_intent():
    r = client.post("/api/assistant", json={
        "message": "what can you do", "lang": "en", "session_id": "t-en-4"})
    assert r.json()["intent"] == "help"


def test_widget_static_served():
    r = client.get("/static/voicebot.js")
    assert r.status_code == 200
    assert "YojanaBench Voice Assistant" in r.text


def test_index_has_widget():
    r = client.get("/")
    assert r.status_code == 200
    assert "vb-launcher" in r.text
    assert "voicebot.js" in r.text


# ---------------------------- activity agent ---------------------------------

def test_agent_write_case_and_store(tmp_path, monkeypatch):
    from backend import case_store
    from backend.agent import ActivityAgent

    monkeypatch.setattr(case_store, "cases_dir", lambda: str(tmp_path))
    agent = ActivityAgent()
    outcome = agent.write_case("IGNOAPS-2023",
                               {"age": 65, "gender": "male", "bpl": True})
    record = outcome["record"]
    assert record["decision"] == "eligible"
    assert record["scheme_id"] == "IGNOAPS-2023"
    assert record["notice_subject"]
    assert record["case_id"].startswith("CASE-IGNOAPS-")

    saved = case_store.load(record["case_id"])
    assert saved is not None
    assert saved["case_id"] == record["case_id"]
    assert saved["decision"] == "eligible"


def test_agent_file_appeal(tmp_path, monkeypatch):
    from backend import case_store, config
    from backend.agent import ActivityAgent

    monkeypatch.setattr(case_store, "cases_dir", lambda: str(tmp_path))
    monkeypatch.setattr(config, "APPEAL_REGISTRY_PATH",
                        str(tmp_path / "appeals.json"))
    agent = ActivityAgent()

    outcome = agent.write_case("IGNOAPS-2023",
                               {"age": 40, "gender": "male", "bpl": True})
    assert outcome["record"]["decision"] == "ineligible"

    appeal = agent.file_appeal(outcome["record"])
    assert appeal["entry"]["attempt"] == 1
    assert appeal["official_notice"]["subject"]


def test_assistant_create_case_flow(tmp_path, monkeypatch):
    from backend import case_store, config
    monkeypatch.setattr(case_store, "cases_dir", lambda: str(tmp_path))
    monkeypatch.setattr(config, "APPEAL_REGISTRY_PATH",
                        str(tmp_path / "appeals.json"))
    sid = "t-case-1"
    r = client.post("/api/assistant", json={
        "message": "write the audit case for old age pension",
        "lang": "en", "session_id": sid})
    assert r.json()["intent"] == "create_case"
    assert r.json()["data"]["action"] == "case"

    for answer in ("Ramesh Kumar", "ramesh@example.com", "65", "male", "yes"):
        r = client.post("/api/assistant", json={
            "message": answer, "lang": "en", "session_id": sid})
        assert r.status_code == 200
    body = r.json()
    assert body["data"]["flow"] == "case_done"
    assert body["data"]["decision"] == "eligible"
    assert body["data"]["case_id"].startswith("CASE-")

    # confirm screen: say no so nothing is sent
    r = client.post("/api/assistant", json={
        "message": "no", "lang": "en", "session_id": sid})
    assert "not sent" in r.json()["reply"].lower()


def test_assistant_create_case_does_everything(tmp_path, monkeypatch):
    from backend import case_store, config
    from backend.agent import ActivityAgent
    monkeypatch.setattr(case_store, "cases_dir", lambda: str(tmp_path))
    monkeypatch.setattr(config, "APPEAL_REGISTRY_PATH",
                        str(tmp_path / "appeals.json"))
    sent = {}

    def _fake_send(self, record, to=None, notify_authority=False):
        sent["to"] = to or record.get("notice_recipient")
        return {"sent": True, "dry_run": False, "to": sent["to"],
                "subject": record.get("notice_subject")}

    monkeypatch.setattr(ActivityAgent, "send_notice", _fake_send)
    sid = "t-case-2"
    client.post("/api/assistant", json={
        "message": "write the audit case for old age pension",
        "lang": "en", "session_id": sid})
    for answer in ("Ramesh", "ramesh@citizen.in", "40", "male", "yes"):
        client.post("/api/assistant", json={
            "message": answer, "lang": "en", "session_id": sid})
    r = client.post("/api/assistant", json={
        "message": "yes", "lang": "en", "session_id": sid})
    body = r.json()
    assert body["intent"] == "do_all"
    assert body["data"]["sent"] is True
    assert body["data"]["appeal_filed"] is True
    assert sent["to"] == "ramesh@citizen.in"


def test_assistant_list_cases_after_create(tmp_path, monkeypatch):
    from backend import case_store, config
    monkeypatch.setattr(case_store, "cases_dir", lambda: str(tmp_path))
    monkeypatch.setattr(config, "APPEAL_REGISTRY_PATH",
                        str(tmp_path / "appeals.json"))
    sid = "t-case-3"
    client.post("/api/assistant", json={
        "message": "write the audit case for old age pension",
        "lang": "en", "session_id": sid})
    last = None
    for answer in ("Sita", "sita@example.com", "66", "female", "yes"):
        last = client.post("/api/assistant", json={
            "message": answer, "lang": "en", "session_id": sid}).json()
    case_id = last["data"]["case_id"]

    r = client.post("/api/assistant", json={
        "message": "list cases", "lang": "en", "session_id": "t-case-4"})
    body = r.json()
    assert body["intent"] == "list_cases"
    assert any(c["case_id"] == case_id for c in body["data"]["cases"])


def test_assistant_send_without_case_is_safe():
    r = client.post("/api/assistant", json={
        "message": "send the notice", "lang": "en", "session_id": "t-case-5"})
    body = r.json()
    assert body["intent"] == "fallback"
    assert "audit case" in body["reply"].lower()
