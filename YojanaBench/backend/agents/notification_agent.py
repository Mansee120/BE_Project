"""
notification_agent.py  (Agent 11/11)
------------------------------------
Turns a completed audit into a **grounded, actionable notice** - and, for
retained/repeat appeals, an official notice.

This is the email-automation layer, but the contribution is *grounding*: every
notice is assembled from the audit's own outputs - the clause-cited verdict, the
CounterfactualAgent's verified "how to qualify" advice and the DocumentGapAgent's
prioritised document list - so nothing in the email is invented.

The agent only *composes* (pure, offline and testable). Delivery is handled by
``backend/notifications.py`` and the ``/api/notify`` endpoint.
"""
import html as _html

from .. import config


def _p(text):
    return {"type": "p", "text": text}


def _h(text):
    return {"type": "h", "text": text}


def _ul(items):
    return {"type": "ul", "items": list(items)}


class NotificationAgent:
    def __init__(self, corpus):
        self.corpus = corpus

    # -- recipients -----------------------------------------------------------
    @staticmethod
    def _recipient(case):
        applicant = case.get("applicant", {}) or {}
        return (applicant.get("email") or case.get("applicant_email")
                or case.get("email"))

    @staticmethod
    def _language(case):
        applicant = case.get("applicant", {}) or {}
        return (applicant.get("language") or case.get("language")
                or config.DEFAULT_NOTICE_LANGUAGE)

    def _authority(self, scheme):
        first = (scheme.get("appeal_hierarchy") or [{}])[0]
        email = (scheme.get("authority_email")
                 or config.SCHEME_AUTHORITY_EMAILS.get(scheme["scheme_id"])
                 or config.AUTHORITY_EMAIL_DEFAULT)
        return first.get("authority", "Appellate Authority"), (email or None)

    # -- rendering ------------------------------------------------------------
    @staticmethod
    def _render_text(blocks):
        out = []
        for b in blocks:
            if b["type"] == "h":
                out.append(b["text"])
                out.append("-" * len(b["text"]))
            elif b["type"] == "p":
                out.append(b["text"])
            elif b["type"] == "ul":
                out.extend(f"  - {item}" for item in b["items"])
            out.append("")
        return "\n".join(out).strip()

    @staticmethod
    def _render_html(blocks):
        parts = ["<div style=\"font-family:Arial,sans-serif;line-height:1.5;"
                 "color:#1f2937;max-width:640px;\">"]
        for b in blocks:
            if b["type"] == "h":
                parts.append(f"<h3 style=\"margin:16px 0 4px;\">{_html.escape(b['text'])}</h3>")
            elif b["type"] == "p":
                parts.append(f"<p style=\"margin:6px 0;\">{_html.escape(b['text'])}</p>")
            elif b["type"] == "ul":
                items = "".join(f"<li>{_html.escape(i)}</li>" for i in b["items"])
                parts.append(f"<ul style=\"margin:6px 0 6px 18px;\">{items}</ul>")
        parts.append("</div>")
        return "".join(parts)

    # -- applicant notice -----------------------------------------------------
    def run(self, case, verdict, appeal=None, counterfactual=None,
            document_gap=None, kind=None):
        scheme = self.corpus.get_scheme(case["scheme_id"])
        decision = verdict["decision"]
        recipient = self._recipient(case)
        authority_name, authority_email = self._authority(scheme)

        blocks = [
            _p(f"Scheme: {scheme['name']} ({scheme['scheme_id']})."),
            _p(f"Case reference: {case.get('case_id', 'N/A')}."),
        ]
        clause_ids = list(verdict.get("evidence_clause_ids", []))
        actionable = False

        if decision == "eligible":
            subject = f"YojanaBench decision: ELIGIBLE - {scheme['name']}"
            blocks.append(_h("Decision: ELIGIBLE"))
            blocks.append(_p(verdict.get("explanation", "")))
            if verdict.get("computed_entitlement") is not None:
                blocks.append(_p(
                    f"Your computed entitlement: {verdict.get('computed_entitlement')} "
                    f"{verdict.get('entitlement_unit') or ''} "
                    f"({verdict.get('entitlement_formula') or ''})."))
        elif decision == "ineligible":
            subject = f"YojanaBench decision: NOT ELIGIBLE - {scheme['name']}"
            blocks.append(_h("Decision: NOT ELIGIBLE"))
            blocks.append(_p(verdict.get("explanation", "")))
            if counterfactual and counterfactual.get("summary"):
                blocks.append(_h("How you could qualify"))
                blocks.append(_p(counterfactual["summary"]))
                actionable = bool(counterfactual.get("feasible"))
                if counterfactual.get("blockers"):
                    blocks.append(_p("Cannot be changed: "
                                     + "; ".join(counterfactual["blockers"]) + "."))
            if appeal and appeal.get("applicable"):
                blocks.append(_h("Your right to appeal"))
                blocks.append(_p(appeal.get("next_step", "")))
                if appeal.get("draft_letter"):
                    blocks.append(_p("A draft appeal letter is included below."))
        else:  # needs_info
            subject = f"YojanaBench decision: ACTION NEEDED - {scheme['name']}"
            blocks.append(_h("Decision: MORE INFORMATION NEEDED"))
            blocks.append(_p(verdict.get("explanation", "")))
            if document_gap and document_gap.get("missing_documents"):
                blocks.append(_h("Documents to submit"))
                blocks.append(_ul([f"{d['name']} (priority {d['priority']})"
                                   for d in document_gap.get("documents", [])]))
                blocks.append(_p(document_gap.get("resolution", "")))
                actionable = True
            if document_gap and document_gap.get("unknown_fields"):
                blocks.append(_h("Additional details required"))
                blocks.append(_ul(document_gap.get("unknown_fields")))

        if decision != "eligible" and authority_name:
            blocks.append(_p("Grievance authority: " + authority_name
                             + (f" ({authority_email})." if authority_email else ".")))

        if clause_ids:
            blocks.append(_h("Cited clauses (provenance)"))
            blocks.append(_p(", ".join(clause_ids)))

        return {
            "notice_type": kind or decision,
            "recipient": recipient,
            "language": self._language(case),
            "authority_name": authority_name,
            "authority_email": authority_email,
            "subject": subject,
            "body_text": self._render_text(blocks),
            "body_html": self._render_html(blocks),
            "clause_ids": clause_ids,
            "actionable": actionable,
            "appeal_letter": (appeal or {}).get("draft_letter"),
        }

    # -- authority digest -----------------------------------------------------
    def authority_notice(self, case, verdict, entitlement_result=None):
        scheme = self.corpus.get_scheme(case["scheme_id"])
        authority_name, authority_email = self._authority(scheme)
        decision = verdict["decision"]
        blocks = [
            _p(f"Scheme: {scheme['name']} ({scheme['scheme_id']})."),
            _h(f"Applicant decision: {decision.upper()}"),
            _p(f"Case reference: {case.get('case_id', 'N/A')}."),
            _p(verdict.get("explanation", "")),
        ]
        violated = []
        if entitlement_result:
            for c in entitlement_result.get("eligibility", {}).get("clauses", []):
                if c.get("mandatory", True) and c.get("result") is False:
                    violated.append(f"[{c.get('clause_id')}] {c.get('text')}")
        if violated:
            blocks.append(_h("Clauses not satisfied"))
            blocks.append(_ul(violated))
        blocks.append(_p(f"Verdict confidence: {verdict.get('confidence')}."))
        if verdict.get("human_approval_required"):
            blocks.append(_p("Flagged for human review before any adverse action."))
        return {
            "notice_type": "authority_digest",
            "recipient": authority_email,
            "authority_name": authority_name,
            "subject": (f"YojanaBench audit digest: {case.get('case_id', 'N/A')} - "
                        f"{decision.upper()}"),
            "body_text": self._render_text(blocks),
            "body_html": self._render_html(blocks),
            "clause_ids": list(verdict.get("evidence_clause_ids", [])),
        }
