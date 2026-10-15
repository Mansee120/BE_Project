"""Tests for the notification / email-automation layer (Agent 11).

All delivery is exercised offline: with no SMTP credentials configured the
MailClient writes to the outbox (a dry run), so no real mail is ever sent.
"""
import os

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend import composer
import backend.appeal_registry as registry
from backend.agents import NotificationAgent
from backend.notifications import MailClient, MessageClient, extract_email, match_documents
from backend.pipeline import pipeline
from backend.app import app

client = TestClient(app)

_DOCS = ["Age Proof (Birth Certificate/School Certificate)",
         "BPL Card", "Aadhaar Card", "Bank Account Passbook"]

ELIGIBLE = {"scheme_id": "IGNOAPS-2023",
            "applicant": {"age": 65, "bpl": True, "email": "citizen@gmail.com"},
            "submitted_documents": _DOCS}

INELIGIBLE = {"scheme_id": "IGNOAPS-2023",
              "applicant": {"age": 30, "bpl": True, "email": "citizen@gmail.com"},
              "submitted_documents": _DOCS}

NEEDS_INFO = {"scheme_id": "IGNOAPS-2023",
              "applicant": {"age": 65, "email": "citizen@gmail.com"},
              "submitted_documents": []}


@pytest.fixture
def offline(monkeypatch, tmp_path):
    """Redirect every runtime artefact into a private temp directory."""
    monkeypatch.setattr(config, "RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(config, "OUTBOX_DIR", str(tmp_path / "outbox"))
    monkeypatch.setattr(config, "NOTIFICATION_LOG_PATH",
                        str(tmp_path / "notification_log.json"))
    monkeypatch.setattr(config, "APPEAL_REGISTRY_PATH",
                        str(tmp_path / "appeal_registry.json"))
    monkeypatch.setattr(config, "EMAIL_CONFIG_PATH",
                        str(tmp_path / "email_config.json"))
    monkeypatch.setattr(config, "SMS_OUTBOX_DIR", str(tmp_path / "sms_outbox"))
    monkeypatch.setattr(config, "MESSAGE_LOG_PATH",
                        str(tmp_path / "message_log.json"))
    # Force offline mode: no SMTP/IMAP credentials -> dry-run outbox.
    monkeypatch.setattr(config, "SMTP_HOST", "")
    monkeypatch.setattr(config, "SMTP_USER", "")
    monkeypatch.setattr(config, "IMAP_HOST", "")
    monkeypatch.setattr(config, "IMAP_USER", "")
    monkeypatch.setattr(config, "SMS_GATEWAY_URL", "")
    return tmp_path


def _run(payload):
    return pipeline.run_case(payload["scheme_id"], payload["applicant"],
                            submitted_documents=payload["submitted_documents"])


# ------------------------------- composition --------------------------------
def test_eligible_notice_carries_entitlement():
    note = _run(ELIGIBLE)["notification"]
    assert note["notice_type"] == "eligible"
    assert "ELIGIBLE" in note["subject"]
    assert note["recipient"] == "citizen@gmail.com"
    assert note["clause_ids"]


def test_ineligible_notice_is_actionable_and_cited():
    note = _run(INELIGIBLE)["notification"]
    assert note["notice_type"] == "ineligible"
    assert note["actionable"] is True
    assert "How you could qualify" in note["body_text"]
    assert note["clause_ids"]
    assert "<html" not in note["body_html"]  # fragment, not a full document


def test_needs_info_notice_lists_documents():
    note = _run(NEEDS_INFO)["notification"]
    assert note["notice_type"] == "needs_info"
    assert note["actionable"] is True
    assert "Documents to submit" in note["body_text"]


def test_authority_digest_lists_violated_clauses():
    res = _run(INELIGIBLE)
    digest = NotificationAgent(pipeline.corpus).authority_notice(
        res["case"], res["verdict"], res["entitlement"])
    assert digest["notice_type"] == "authority_digest"
    assert "Clauses not satisfied" in digest["body_text"]


# ------------------------------- delivery -----------------------------------
def test_dry_run_send_writes_outbox(offline):
    out = MailClient().send("citizen@gmail.com", "Subject", "plain body")
    assert out["dry_run"] is True and out["sent"] is False
    assert os.path.exists(out["outbox_path"])


def test_recipient_validation():
    assert MailClient.valid_recipient("a.b@citizen.gov.in")
    assert not MailClient.valid_recipient("bad-email")
    assert not MailClient.valid_recipient("x@example.com")
    assert not MailClient.valid_recipient(None)


def test_extract_email_and_document_matching():
    assert extract_email("Ramesh <r@gmail.com>") == "r@gmail.com"
    matched = match_documents(["bpl_card.pdf", "aadhaar.png"],
                              ["BPL Card", "Aadhaar Card"])
    assert "BPL Card" in matched and "Aadhaar Card" in matched


# ------------------------------- registry -----------------------------------
def test_appeal_registry_repeat_and_notice(offline):
    assert registry.is_repeat("CASE-X") is False
    registry.record("CASE-X", "IGNOAPS-2023", "ineligible", ["IGNOAPS-C1"])
    assert registry.is_repeat("CASE-X") is True
    registry.record("CASE-X", "IGNOAPS-2023", "ineligible", ["IGNOAPS-C1"])
    assert registry.attempts("CASE-X") == 2
    notice = registry.build_notice("CASE-X", "Old Age Pension")
    assert notice["attempt"] == 2
    assert "OFFICIAL NOTICE" in notice["body_text"]


# ------------------------------- endpoints ----------------------------------
def test_notify_endpoint_dry_run(offline):
    payload = dict(INELIGIBLE, send=True)
    r = client.post("/api/notify", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["notification"]["notice_type"] == "ineligible"
    assert body["delivery"]["dry_run"] is True


def test_appeals_endpoints_flag_repeats(offline):
    base = {"scheme_id": INELIGIBLE["scheme_id"],
            "applicant": INELIGIBLE["applicant"],
            "submitted_documents": INELIGIBLE["submitted_documents"]}
    first = client.post("/api/appeals/CASE-Y/notice", json=base).json()
    assert first["attempt"] == 1 and first["repeat"] is False
    second = client.post("/api/appeals/CASE-Y/notice", json=base).json()
    assert second["repeat"] is True and second["attempt"] == 2
    assert client.get("/api/appeals/CASE-Y").json()["attempts"] == 2


def test_notifications_status_endpoint():
    r = client.get("/api/notifications/status")
    assert r.status_code == 200
    assert r.json()["smtp"] in ("configured", "outbox (dry-run)")


# ------------------------------- sms / message ------------------------------
def test_dry_run_message_writes_outbox(offline):
    out = MessageClient().send("+919812345678", "Your BPL card is pending.")
    assert out["dry_run"] is True and out["sent"] is False
    assert out["channel"] == "sms"
    assert os.path.exists(out["outbox_path"])
    assert os.path.exists(config.MESSAGE_LOG_PATH)


def test_phone_validation():
    assert MessageClient.valid_phone("+919812345678")
    assert MessageClient.valid_phone("9812345678")
    assert not MessageClient.valid_phone("not-a-phone")
    assert not MessageClient.valid_phone(None)


def test_notify_endpoint_sms_dry_run(offline):
    payload = dict(INELIGIBLE, send=True, channel="sms", phone="+919812345678")
    r = client.post("/api/notify", json=payload)
    assert r.status_code == 200
    delivery = r.json()["delivery"]
    assert delivery["channel"] == "sms"
    assert delivery["dry_run"] is True
    assert os.path.exists(delivery["outbox_path"])


def test_notify_endpoint_sms_rejects_bad_phone(offline):
    payload = dict(INELIGIBLE, send=True, channel="sms", phone="123")
    r = client.post("/api/notify", json=payload)
    assert r.status_code == 200
    assert r.json()["delivery"]["error"]


def test_messages_status_endpoint():
    r = client.get("/api/messages/status")
    assert r.status_code == 200
    assert r.json()["mode"] in ("live", "outbox (dry-run)")


# ------------------------------- manual compose -----------------------------
def test_composer_template_fallback_offline():
    draft = composer.generate_draft(
        instruction="Your income certificate is still pending.",
        recipient_name="Ramesh", tone="reminder")
    assert draft["generated"] is False  # no LLM in the test environment
    assert draft["subject"].startswith("Reminder:")
    assert "Ramesh" in draft["body_text"]
    assert "income certificate" in draft["body_text"]


def test_composer_empty_instruction_returns_empty():
    draft = composer.generate_draft(instruction="   ")
    assert draft["subject"] == "" and draft["body_text"] == ""


def test_draft_endpoint(offline):
    r = client.post("/api/email/draft", json={
        "instruction": "Please submit your BPL card.",
        "recipient_name": "Sita", "scheme_id": "IGNOAPS-2023"})
    assert r.status_code == 200
    body = r.json()
    assert body["subject"]
    assert "BPL card" in body["body_text"]


def test_manual_email_send_dry_run(offline):
    r = client.post("/api/email/send", json={
        "to": "citizen@gmail.com", "subject": "Manual notice",
        "body_text": "Hello there.", "scheme_id": "IGNOAPS-2023"})
    assert r.status_code == 200
    delivery = r.json()["delivery"]
    assert delivery["dry_run"] is True
    assert os.path.exists(delivery["outbox_path"])


def test_manual_email_rejects_blocked_recipient(offline):
    r = client.post("/api/email/send", json={
        "to": "x@example.com", "subject": "s", "body_text": "b"})
    assert r.status_code == 400


# ------------------------------- email settings -----------------------------
def test_email_settings_persist_to_editable_file(monkeypatch, tmp_path):
    path = str(tmp_path / "email_config.json")
    monkeypatch.setattr(config, "EMAIL_CONFIG_PATH", path)
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_USE_SSL"):
        monkeypatch.setattr(config, key, getattr(config, key))  # snapshot/restore

    r = client.post("/api/email/settings",
                    json={"SMTP_HOST": "smtp.test.invalid", "SMTP_PORT": 587})
    assert r.status_code == 200
    assert r.json()["settings"]["SMTP_HOST"] == "smtp.test.invalid"
    assert r.json()["settings"]["SMTP_PASSWORD"] == config.PASSWORD_MASK
    assert os.path.exists(path)
    assert client.get("/api/email/settings").json()["settings"]["SMTP_PORT"] == 587


def test_email_test_endpoint_offline(monkeypatch):
    monkeypatch.setattr(config, "SMTP_HOST", "")
    monkeypatch.setattr(config, "SMTP_USER", "")
    r = client.post("/api/email/test")
    assert r.status_code == 200
    assert r.json()["mode"] == "outbox"
