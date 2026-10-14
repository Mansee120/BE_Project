"""
notifications.py
----------------
Thin, dependency-light email adapter for YojanaBench's notification layer.

The outbound (SMTP) and inbound (IMAP) mechanics are adapted from the OrbitAvanya
EmailAutomation project, stripped down to what the audit pipeline needs:

  * deliver a clause-cited verdict notice to an applicant / authority,
  * keep a file-backed outbound log so citizen *replies* can be matched back to a
    case and re-audited,
  * scan an inbox for replies (with attachments) over IMAP.

Design rule: YojanaBench stays offline and zero-cost. When SMTP/IMAP credentials
are absent (the default) every "send" is written to ``runtime/outbox`` as a
``.eml`` file and reported as a dry run - no network, no mail.
"""
import email
import json
import os
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate

from . import config

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ANGLE_RE = re.compile(r"<([^>]+)>")

# Obvious non-deliverable domains we refuse even in dry-run mode.
_BLOCKED_DOMAINS = {"example.com", "test.com", "invalid", "localhost", "example.org"}


def extract_email(raw: str) -> str:
    """Pull the bare address out of a ``Name <addr@host>`` header value."""
    if not raw:
        return ""
    m = _ANGLE_RE.search(raw)
    return (m.group(1) if m else raw).strip()


def match_documents(filenames, required_names) -> list:
    """Loose filename -> schema-document matching (e.g. ``bpl_card.pdf`` -> ``BPL Card``)."""
    norm = [f.lower() for f in (filenames or [])]
    matched = []
    for name in required_names or []:
        key = name.lower()
        tokens = [t for t in re.split(r"[^a-z0-9]+", key) if len(t) > 3]
        for fname in norm:
            if key in fname or any(t in fname for t in tokens):
                matched.append(name)
                break
    return matched


def _text_to_html(text: str) -> str:
    import html as _html
    return "<pre style=\"font-family:Arial,sans-serif;white-space:pre-wrap;\">" \
           + _html.escape(text or "") + "</pre>"


def _smtp_send(msg, recipients):
    if config.SMTP_USE_SSL:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT,
                              context=ctx, timeout=30) as s:
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.sendmail(config.SMTP_USER, recipients, msg.as_string())
    else:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as s:
            s.starttls(context=ssl.create_default_context())
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.sendmail(config.SMTP_USER, recipients, msg.as_string())


def _parse_message(msg) -> dict:
    """Extract from / subject / date / plain body / attachment filenames."""
    body = ""
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                fname = part.get_filename()
                if fname:
                    attachments.append(fname)
                continue
            if part.get_content_type() == "text/plain":
                try:
                    body += part.get_payload(decode=True).decode("utf-8", "ignore")
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", "ignore")
        except Exception:
            body = str(msg.get_payload())
    return {
        "from": msg.get("From", ""),
        "subject": msg.get("Subject", ""),
        "date": msg.get("Date", ""),
        "body": body.strip(),
        "attachments": attachments,
    }


class MailClient:
    def __init__(self):
        for d in (config.RUNTIME_DIR, config.OUTBOX_DIR):
            os.makedirs(d, exist_ok=True)

    # -- status ---------------------------------------------------------------
    def smtp_available(self) -> bool:
        return bool(config.SMTP_HOST and config.SMTP_USER)

    def imap_available(self) -> bool:
        return bool(config.IMAP_HOST and config.IMAP_USER)

    def status(self) -> dict:
        return {
            "smtp": "configured" if self.smtp_available() else "outbox (dry-run)",
            "imap": "configured" if self.imap_available() else "disabled",
            "authority_email": config.AUTHORITY_EMAIL_DEFAULT or None,
        }

    def test_connection(self) -> dict:
        """Attempt an SMTP login to verify the configured credentials.

        Returns ``{ok, mode, message|error}``. Never raises.
        """
        if not self.smtp_available():
            return {"ok": False, "mode": "outbox",
                    "error": "No SMTP host/user configured - running in outbox "
                             "(dry-run) mode."}
        try:
            if config.SMTP_USE_SSL:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT,
                                      context=ctx, timeout=20) as s:
                    s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            else:
                with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT,
                                  timeout=20) as s:
                    s.starttls(context=ssl.create_default_context())
                    s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            return {"ok": True, "mode": "smtp",
                    "message": f"Connected & authenticated as {config.SMTP_USER}."}
        except Exception as exc:  # pragma: no cover - live network path
            return {"ok": False, "mode": "smtp", "error": str(exc)}

    # -- validation (offline-safe) --------------------------------------------
    @staticmethod
    def valid_recipient(addr) -> bool:
        if not addr or not isinstance(addr, str):
            return False
        addr = addr.strip()
        if not _EMAIL_RE.match(addr):
            return False
        domain = addr.split("@", 1)[1].lower()
        return domain not in _BLOCKED_DOMAINS

    # -- compose --------------------------------------------------------------
    @staticmethod
    def _build_message(to, subject, body_text, body_html=None, cc=None, from_name=None):
        sender = config.SMTP_USER or "no-reply@yojanabench.local"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr((from_name or config.SMTP_FROM_NAME, sender))
        msg["To"] = to
        if cc:
            msg["Cc"] = ", ".join(cc) if isinstance(cc, (list, tuple)) else str(cc)
        msg["Date"] = formatdate(localtime=True)
        msg.attach(MIMEText(body_text or "", "plain", "utf-8"))
        msg.attach(MIMEText(body_html or _text_to_html(body_text), "html", "utf-8"))
        return msg

    # -- send -----------------------------------------------------------------
    def send(self, to, subject, body_text, body_html=None, cc=None, from_name=None) -> dict:
        """Send (or dry-run to the outbox). Never raises; returns a status dict."""
        result = {
            "sent": False, "dry_run": True, "to": to, "cc": list(cc or []),
            "subject": subject, "error": None,
        }
        if not self.valid_recipient(to):
            result["error"] = f"invalid recipient: {to!r}"
            return result
        msg = self._build_message(to, subject, body_text, body_html, cc, from_name)
        if not self.smtp_available():
            result["outbox_path"] = self._write_outbox(msg)
            return result
        try:
            _smtp_send(msg, [to] + list(cc or []))
            result["sent"] = True
            result["dry_run"] = False
        except Exception as exc:  # pragma: no cover - live network path
            result["error"] = str(exc)
        return result

    def _write_outbox(self, msg) -> str:
        os.makedirs(config.OUTBOX_DIR, exist_ok=True)
        stamp = formatdate(localtime=True).replace(":", "").replace(",", "").replace(" ", "_")
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", msg["To"])[:60]
        path = os.path.join(config.OUTBOX_DIR, f"{stamp}_{safe}.eml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(msg.as_string())
        return path

    # -- outbound log (enables reply matching) --------------------------------
    def record_outbound(self, case: dict, to: str, subject: str, notice_type: str) -> None:
        log = self._load_log()
        log.insert(0, {
            "case_id": case.get("case_id"),
            "scheme_id": case.get("scheme_id"),
            "applicant": case.get("applicant", {}),
            "submitted_documents": case.get("submitted_documents", []),
            "to": to,
            "subject": subject,
            "notice_type": notice_type,
            "date": formatdate(localtime=True),
        })
        self._save_log(log[:500])

    def lookup_by_email(self, addr: str):
        if not addr:
            return None
        target = addr.strip().lower()
        for entry in self._load_log():
            if (entry.get("to") or "").strip().lower() == target:
                return entry
        return None

    def _load_log(self):
        if not os.path.exists(config.NOTIFICATION_LOG_PATH):
            return []
        try:
            with open(config.NOTIFICATION_LOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_log(self, log):
        os.makedirs(os.path.dirname(config.NOTIFICATION_LOG_PATH), exist_ok=True)
        with open(config.NOTIFICATION_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2, ensure_ascii=False)

    # -- IMAP reply scan ------------------------------------------------------
    def scan_replies(self, since_hours: int = 72, limit: int = 25) -> list:
        """Return recent inbox messages (empty list when IMAP is not configured)."""
        if not self.imap_available():
            return []
        import datetime as _dt

        since = (_dt.datetime.now() - _dt.timedelta(hours=since_hours)) \
            .strftime("%d-%b-%Y")
        out = []
        conn = None
        try:  # pragma: no cover - live network path
            conn = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
            conn.login(config.IMAP_USER, config.IMAP_PASSWORD)
            conn.select("INBOX")
            typ, data = conn.search(None, f'(SINCE "{since}")')
            if typ != "OK":
                return []
            ids = data[0].split()[-limit:]
            for num in reversed(ids):
                typ, msg_data = conn.fetch(num, "(RFC822)")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    continue
                out.append(_parse_message(email.message_from_bytes(msg_data[0][1])))
        except Exception:
            return out
        finally:
            if conn is not None:
                try:
                    conn.logout()
                except Exception:
                    pass
        return out

    # -- translation (optional) -----------------------------------------------
    @staticmethod
    def translate(text: str, target_lang: str) -> str:
        if not target_lang or target_lang.lower().startswith("en"):
            return text
        try:  # optional dependency; degrades to the original text
            from deep_translator import GoogleTranslator
            return GoogleTranslator(source="auto", target=target_lang).translate(text)
        except Exception:
            return text


# Shared singleton used by the API layer.
mail = MailClient()
