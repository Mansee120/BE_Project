"""
composer.py
-----------
Free-form notice / email drafting for the **manual compose** feature of the
email-automation layer.

A short human instruction ("remind the applicant their income certificate is
still pending") is turned into a ready-to-send subject + body. When the local
Ollama LLM is running we ask it to write the notice; otherwise we fall back to a
deterministic template so the feature stays offline and zero-cost, exactly like
the rest of YojanaBench.
"""
from . import config
from .llm import llm_client

_TONES = ("formal", "friendly", "urgent", "reminder")


def _split_subject(text: str) -> tuple:
    """Split model output into (subject, body); tolerate a missing Subject line."""
    subject = ""
    body_lines = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not subject and stripped.lower().startswith("subject:"):
            subject = stripped.split(":", 1)[1].strip().strip('"').strip()
            continue
        body_lines.append(line)
    body = "\n".join(body_lines).strip()
    if not subject:
        first = body.splitlines()[0].strip() if body else "Notice"
        subject = first[:80]
    return subject, body


def _fallback(instruction, recipient_name, scheme_name, tone, sender_name):
    who = recipient_name.strip() or "Applicant"
    scheme = scheme_name or "your application"
    first_line = instruction.strip().splitlines()[0] if instruction.strip() else ""
    subject = (first_line[:80] or f"Notice regarding {scheme}")
    if tone == "urgent":
        subject = "Action required: " + subject
    elif tone == "reminder":
        subject = "Reminder: " + subject
    body = "\n".join([
        f"Dear {who},",
        "",
        instruction.strip() or f"This is a notice regarding {scheme}.",
        "",
        "If you have new documents or believe this is in error, please contact "
        "your grievance authority and quote the case reference above.",
        "",
        "Regards,",
        sender_name,
    ])
    return {"subject": subject, "body_text": body}


def generate_draft(instruction: str = "", recipient_name: str = "",
                   scheme_name: str = "", tone: str = "formal",
                   language: str = "en", sender_name: str = None) -> dict:
    """Draft a subject + body from a short instruction.

    Returns ``{subject, body_text, generated, model, language}``. ``generated``
    is True only when the local LLM produced the text.
    """
    sender_name = sender_name or config.SMTP_FROM_NAME or "YojanaBench"
    instruction = (instruction or "").strip()
    tone = tone if tone in _TONES else "formal"

    if not instruction:
        return {"subject": "", "body_text": "", "generated": False,
                "model": None, "language": language}

    prompt = (
        "You are an assistant that drafts official welfare-scheme notices and "
        "citizen emails for a government office. Write ONLY the email, no "
        "commentary. The FIRST line must be the subject prefixed with "
        "'Subject:'. Then a blank line, then the body. End with the signature "
        f"'{sender_name}'.\n\n"
        "Tone: {tone}\nLanguage: {language}\n"
        "Recipient name: {recipient}\nScheme: {scheme}\n"
        "Instruction: {instruction}\n"
    ).format(tone=tone, language=language,
             recipient=recipient_name or "(unknown)",
             scheme=scheme_name or "(unspecified)",
             instruction=instruction)

    text = llm_client.generate(prompt)
    if text:
        subject, body = _split_subject(text)
        if language and not language.lower().startswith("en"):
            from .notifications import mail
            body = mail.translate(body, language)
        return {"subject": subject, "body_text": body, "generated": True,
                "model": llm_client.model, "language": language}

    fb = _fallback(instruction, recipient_name, scheme_name, tone, sender_name)
    body = fb["body_text"]
    if language and not language.lower().startswith("en"):
        from .notifications import mail
        body = mail.translate(body, language)
    return {"subject": fb["subject"], "body_text": body, "generated": False,
            "model": None, "language": language}
