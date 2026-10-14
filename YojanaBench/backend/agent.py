"""
agent.py
--------
The **activity agent** behind the voice assistant.

The assistant's NLU (``assistant.py``) understands *questions*; this module is
the part that actually *does things*. In one call it can carry out the full
back-office workflow for a citizen:

    1. run the multi-agent audit (``pipeline.run_case``),
    2. compose the grounded, clause-cited notice (NotificationAgent output),
    3. work out the appeal route + draft letter,
    4. **write the case file** to ``runtime/cases/<case_id>.json``,
    5. deliver the notice (``mail`` - real SMTP when configured, otherwise a
       dry-run into ``runtime/outbox``), and
    6. file the appeal in the ``appeal_registry``.

Every method is pure orchestration over the existing singletons, so the agent
stays deterministic and offline-first exactly like the rest of YojanaBench.
"""
import datetime

from . import appeal_registry, case_store, composer
from .notifications import mail
from .pipeline import pipeline


class ActivityAgent:
    """Performs concrete activities on behalf of the voice assistant."""

    def __init__(self, pipe=pipeline, mailer=mail, appeals=appeal_registry,
                 cases=case_store):
        self.pipeline = pipe
        self.mail = mailer
        self.appeals = appeals
        self.cases = cases
        self.corpus = pipe.corpus

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _new_case_id(scheme_id: str) -> str:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        prefix = (scheme_id or "CASE").split("-")[0]
        return f"CASE-{prefix}-{stamp}"

    # -- activity 1: write the audit case ------------------------------------
    def write_case(self, scheme_id: str, applicant: dict,
                   submitted_documents: list = None, case_id: str = None) -> dict:
        """Run the audit and persist a complete case file.

        Returns ``{record, path, result}`` where ``record`` is the serialisable
        case summary that was written to disk and ``result`` is the raw
        pipeline output (kept in memory only).
        """
        scheme = self.corpus.get_scheme(scheme_id)
        if not scheme:
            raise ValueError(f"Unknown scheme_id: {scheme_id}")

        case_id = case_id or self._new_case_id(scheme_id)
        result = self.pipeline.run_case(
            scheme_id, applicant, submitted_documents=submitted_documents,
            case_id=case_id)
        verdict = result["verdict"]
        notice = result.get("notification") or {}
        appeal = result.get("appeal") or {}

        record = {
            "case_id": case_id,
            "scheme_id": scheme_id,
            "scheme_name": scheme["name"],
            "applicant": result["case"]["applicant"],
            "submitted_documents": submitted_documents or [],
            "decision": verdict["decision"],
            "confidence": verdict.get("confidence"),
            "explanation": verdict.get("explanation"),
            "computed_entitlement": verdict.get("computed_entitlement"),
            "entitlement_unit": verdict.get("entitlement_unit"),
            "evidence_clause_ids": verdict.get("evidence_clause_ids", []),
            "missing_documents": result["case"].get("missing_documents", []),
            "notice_type": notice.get("notice_type"),
            "notice_subject": notice.get("subject"),
            "notice_body": notice.get("body_text"),
            "notice_recipient": notice.get("recipient"),
            "authority_name": notice.get("authority_name"),
            "authority_email": notice.get("authority_email"),
            "appeal_applicable": bool(appeal.get("applicable")),
            "appeal_next_step": appeal.get("next_step"),
            "appeal_letter": appeal.get("draft_letter"),
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        path = self.cases.save(record)
        return {"record": record, "path": path, "result": result}

    # -- activity 2: deliver the notice --------------------------------------
    def send_notice(self, record: dict, to: str = None,
                    notify_authority: bool = False) -> dict:
        """Email the composed notice (dry-run to the outbox when SMTP is off)."""
        to = (to or record.get("notice_recipient")
              or (record.get("applicant") or {}).get("email"))
        subject = record.get("notice_subject") or "YojanaBench decision notice"
        body = record.get("notice_body") or ""

        if not self.mail.valid_recipient(to):
            return {"sent": False, "dry_run": True, "to": to, "subject": subject,
                    "error": "no valid applicant email on file"}

        cc = None
        if notify_authority and record.get("authority_email"):
            cc = [record["authority_email"]]
        delivery = self.mail.send(to, subject, body, cc=cc)
        if delivery.get("sent") or delivery.get("outbox_path"):
            case = {
                "case_id": record.get("case_id"),
                "scheme_id": record.get("scheme_id"),
                "applicant": record.get("applicant"),
                "submitted_documents": record.get("submitted_documents"),
            }
            self.mail.record_outbound(case, to, subject,
                                      record.get("notice_type") or "notice")
        return delivery

    # -- activity 3: file the appeal -----------------------------------------
    def file_appeal(self, record: dict, reason: str = "") -> dict:
        """Record an appeal attempt and build the official (repeat) notice."""
        entry = self.appeals.record(
            record["case_id"], record["scheme_id"], record.get("decision", ""),
            record.get("evidence_clause_ids", []), reason=reason)
        official = self.appeals.build_notice(
            record["case_id"], record.get("scheme_name", "the scheme"))
        return {"entry": entry, "official_notice": official}

    # -- activity 4: draft a free-form email ---------------------------------
    def draft_email(self, instruction: str, recipient_name: str = "",
                    scheme_name: str = "", tone: str = "formal",
                    language: str = "en") -> dict:
        return composer.generate_draft(
            instruction=instruction, recipient_name=recipient_name,
            scheme_name=scheme_name, tone=tone, language=language)

    # -- activity 5: list written cases --------------------------------------
    def list_cases(self) -> list:
        return self.cases.list_cases()


agent = ActivityAgent()
