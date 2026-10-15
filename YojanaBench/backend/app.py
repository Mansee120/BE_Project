"""
app.py
------
FastAPI backend for YojanaBench. Exposes the multi-agent audit pipeline, the
benchmark runner and dataset statistics, and serves the single-page dashboard.

Run with:  python run.py      (or)  uvicorn backend.app:app --reload
"""
import os

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List

from . import config
from . import appeal_registry
from . import notifications
from . import composer
from . import auth
from . import complaints as complaints_mod
from . import dbt
from .notifications import mail, sms
from .pipeline import pipeline
from .ablation import AblationRunner
from .report import build_report
from .leaderboard import ranked
from . import assistant as assistant_mod
from .trace import trace_complaint

app = FastAPI(
    title="YojanaBench API",
    description="Benchmark + multi-agent audit pipeline for India welfare-scheme documents.",
    version="1.0.0",
)

# Allow the dashboard (served elsewhere during dev) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- request models -----------------------------------------------------------
class AuditRequest(BaseModel):
    scheme_id: str = Field(..., description="Target scheme id, e.g. IGNOAPS-2023")
    applicant: dict = Field(default_factory=dict, description="Applicant field map")
    submitted_documents: Optional[List[str]] = None
    case_id: Optional[str] = None
    use_llm: bool = False


class BenchmarkRequest(BaseModel):
    scheme_id: str = None
    category: str = None
    use_llm: bool = False


class AblationRequest(BaseModel):
    use_llm: bool = False


class NotifyRequest(BaseModel):
    scheme_id: str = Field(..., description="Target scheme id, e.g. IGNOAPS-2023")
    applicant: dict = Field(default_factory=dict, description="Applicant field map")
    submitted_documents: Optional[List[str]] = None
    case_id: Optional[str] = None
    use_llm: bool = False
    send: bool = Field(False, description="Actually deliver the notice (else preview)")
    notify_authority: bool = Field(False, description="CC the scheme authority")
    channel: str = Field("email", description="Delivery channel: 'email' or 'sms'")
    to: Optional[str] = Field(None, description="Override email recipient")
    phone: Optional[str] = Field(None, description="SMS recipient (channel='sms')")


class AppealRequest(BaseModel):
    scheme_id: str
    applicant: dict = Field(default_factory=dict)
    submitted_documents: Optional[List[str]] = None
    send: bool = False
    notify_authority: bool = False


class ReplySyncRequest(BaseModel):
    since_hours: int = 72
    auto_send: bool = False


class DraftEmailRequest(BaseModel):
    instruction: str = Field("", description="Short human instruction for the notice")
    recipient_name: str = ""
    scheme_id: Optional[str] = None
    tone: str = "formal"
    language: str = "en"


class ManualEmailRequest(BaseModel):
    to: str = Field(..., description="Recipient email address")
    subject: str = ""
    body_text: str = ""
    cc: Optional[List[str]] = None
    from_name: Optional[str] = None
    send: bool = True
    scheme_id: Optional[str] = None
    applicant: dict = Field(default_factory=dict)
    submitted_documents: Optional[List[str]] = None
    case_id: Optional[str] = None
    notify_authority: bool = False


class EmailSettingsRequest(BaseModel):
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_NAME: Optional[str] = None
    SMTP_USE_SSL: Optional[bool] = None
    IMAP_HOST: Optional[str] = None
    IMAP_PORT: Optional[int] = None
    IMAP_USER: Optional[str] = None
    IMAP_PASSWORD: Optional[str] = None
    AUTHORITY_EMAIL_DEFAULT: Optional[str] = None


class AssistantRequest(BaseModel):
    message: str = Field(..., description="Recognised speech / typed question")
    lang: str = Field("en", description="BCP-47 language tag the user spoke in, e.g. hi-IN")
    session_id: Optional[str] = None


# -- grievance / money-trace request models -----------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = Field("beneficiary", description="beneficiary | official")
    name: str = ""
    beneficiary_id: Optional[str] = None


class ComplaintRequest(BaseModel):
    scheme_id: str = Field(..., description="Scheme the payment belongs to")
    utr: Optional[str] = Field(None, description="DBT transaction reference, if known")
    beneficiary_id: Optional[str] = None
    expected_amount: Optional[float] = None
    description: str = Field("", description="Free-text grievance in the citizen's words")


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., description="filed | traced | under_review | resolved | rejected")
    note: str = ""


# -- auth helper --------------------------------------------------------------
def current_user(authorization: str = Header(None)) -> dict:
    """Resolve the bearer token to a user payload, or raise 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    payload = auth.verify_token(authorization.split(" ", 1)[1].strip())
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


def require_official(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "official":
        raise HTTPException(status_code=403, detail="Officer role required")
    return user


# -- API endpoints ------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "llm": pipeline.dataset_stats()["llm"]}


@app.get("/api/stats")
def stats():
    """Dataset statistics for the dashboard header cards."""
    return pipeline.dataset_stats()


@app.get("/api/schemes")
def list_schemes():
    return {"schemes": pipeline.corpus.list_schemes()}


@app.get("/api/schemes/{scheme_id}")
def get_scheme(scheme_id: str):
    scheme = pipeline.corpus.get_scheme(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Unknown scheme: {scheme_id}")
    return scheme


@app.get("/api/cases")
def list_cases():
    """Sample applications shipped with the dataset."""
    return {"cases": pipeline.list_cases()}


@app.post("/api/audit")
def audit(req: AuditRequest):
    """Run the full multi-agent audit for a single application."""
    if not pipeline.corpus.get_scheme(req.scheme_id):
        raise HTTPException(status_code=404, detail=f"Unknown scheme: {req.scheme_id}")
    try:
        result = pipeline.run_case(
            req.scheme_id, req.applicant,
            submitted_documents=req.submitted_documents,
            case_id=req.case_id, use_llm=req.use_llm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@app.get("/api/benchmark")
def benchmark_items(scheme_id: str = None, category: str = None):
    """Return the raw QA benchmark (optionally filtered)."""
    data = pipeline._load_benchmark()
    items = data["items"]
    if scheme_id:
        items = [i for i in items if i["scheme_id"] == scheme_id]
    if category:
        items = [i for i in items if i["category"] == category]
    return {"benchmark_version": data.get("benchmark_version"), "count": len(items),
            "items": items}


@app.post("/api/benchmark/run")
def run_benchmark(req: BenchmarkRequest):
    """Execute the pipeline over the benchmark and return metric tables."""
    return pipeline.run_benchmark(scheme_id=req.scheme_id, category=req.category,
                                  use_llm=req.use_llm)


@app.post("/api/ablation/run")
def run_ablation(req: AblationRequest):
    """Run the baselines/ablations experiment and return the comparison."""
    return AblationRunner().run(use_llm=req.use_llm)


@app.get("/api/report")
def accuracy_report():
    """Accuracy report tables (overall, per-category, per-scheme, edge/base,
    ablation, item-level) as JSON for the dashboard and CSV export."""
    return build_report(pipeline)


@app.get("/api/leaderboard")
def leaderboard():
    """Public leaderboard of models scored on the YojanaBench benchmark."""
    return {"entries": ranked()}


# -- multilingual voice assistant ---------------------------------------------
@app.get("/api/assistant/status")
def assistant_status():
    """Assistant readiness: number of schemes it can explain."""
    return assistant_mod.assistant.status()


@app.get("/api/assistant/welcome")
def assistant_welcome(lang: str = "en"):
    """Localised greeting spoken when the assistant opens or the language changes."""
    return assistant_mod.assistant.welcome(lang)


@app.post("/api/assistant")
def assistant_reply(req: AssistantRequest):
    """Natural-language answer for the voice assistant widget.

    Speaks any language: the question is translated to English for intent
    detection and the answer is translated back into ``req.lang`` (when the
    optional ``deep_translator`` package is available). Stateful sessions
    power the guided verbal audit.
    """
    return assistant_mod.assistant.handle(
        req.message, lang=req.lang, session_id=req.session_id)


# -- notification / email-automation layer ------------------------------------
def _sms_text(notice: dict, verdict: dict = None) -> str:
    """Condense a grounded notice into a short SMS-friendly message (<= 480 chars)."""
    import re as _re
    subject = (notice.get("subject") or "YojanaBench notice").strip()
    body = _re.sub(r"\s+", " ", (notice.get("body_text") or "").strip())
    body = _re.sub(r"^(Dear [^,]+,?\s*)", "", body, flags=_re.I)
    text = f"{subject} - {body}".strip(" -")
    return text[:480]


@app.get("/api/notifications/status")
def notifications_status():
    """Whether the layer is live (SMTP/IMAP configured) or in outbox dry-run."""
    return mail.status()


@app.post("/api/notify")
def notify(req: NotifyRequest):
    """Compose (and optionally deliver) the grounded notice for one case."""
    if not pipeline.corpus.get_scheme(req.scheme_id):
        raise HTTPException(status_code=404, detail=f"Unknown scheme: {req.scheme_id}")
    try:
        result = pipeline.run_case(req.scheme_id, req.applicant,
                                   submitted_documents=req.submitted_documents,
                                   case_id=req.case_id, use_llm=req.use_llm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    notice = result["notification"]
    delivery = None
    if req.send:
        channel = (req.channel or "email").lower()
        if channel == "sms":
            phone = (req.phone or req.applicant.get("phone")
                     or req.applicant.get("mobile"))
            delivery = sms.send(phone, _sms_text(notice, result["verdict"]),
                                subject=notice.get("subject"))
        else:
            recipient = (req.to or notice["recipient"] or "").strip()
            if not mail.valid_recipient(recipient):
                delivery = {"sent": False, "dry_run": True, "channel": "email",
                            "to": recipient,
                            "error": "no valid applicant email on file"}
            else:
                cc = ([notice["authority_email"]]
                      if req.notify_authority and notice["authority_email"] else None)
                delivery = mail.send(recipient, notice["subject"],
                                     notice["body_text"], notice["body_html"], cc=cc)
                mail.record_outbound(result["case"], recipient,
                                     notice["subject"], notice["notice_type"])
    return {"notification": notice, "delivery": delivery, "verdict": result["verdict"]}


@app.get("/api/messages/status")
def messages_status():
    """Whether the SMS channel is live (gateway set) or in outbox dry-run."""
    return sms.status()


@app.get("/api/appeals")
def list_appeals():
    """Full appeal register (all cases)."""
    return {"appeals": appeal_registry.history()}


@app.get("/api/appeals/{case_id}")
def case_appeals(case_id: str):
    """Appeal history + repeat flag for one case."""
    return {"case_id": case_id,
            "attempts": appeal_registry.attempts(case_id),
            "repeat": appeal_registry.is_repeat(case_id),
            "entries": appeal_registry.entries(case_id)}


@app.post("/api/appeals/{case_id}/notice")
def appeal_notice(case_id: str, req: AppealRequest):
    """Record an appeal attempt and, if it repeats, issue an official notice."""
    scheme = pipeline.corpus.get_scheme(req.scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Unknown scheme: {req.scheme_id}")
    try:
        result = pipeline.run_case(req.scheme_id, req.applicant,
                                   submitted_documents=req.submitted_documents,
                                   case_id=case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    verdict = result["verdict"]
    was_repeat = appeal_registry.is_repeat(case_id)
    entry = appeal_registry.record(case_id, req.scheme_id, verdict["decision"],
                                   verdict.get("evidence_clause_ids", []))
    official = appeal_registry.build_notice(case_id, scheme["name"])

    delivery = None
    recipient = result["notification"]["recipient"]
    if req.send and mail.valid_recipient(recipient):
        cc = ([result["notification"]["authority_email"]]
              if req.notify_authority and result["notification"]["authority_email"]
              else None)
        delivery = mail.send(recipient, official["subject"], official["body_text"],
                             cc=cc)
        mail.record_outbound(result["case"], recipient, official["subject"],
                             "repeat_notice")

    return {"repeat": was_repeat, "attempt": entry["attempt"],
            "official_notice": official, "verdict": verdict, "delivery": delivery}


@app.post("/api/replies/sync")
def replies_sync(req: ReplySyncRequest):
    """Pull inbox replies, match attachments to required docs and re-audit.

    Turns the one-shot audit into a closed loop: a citizen replying with the
    missing documents can flip ``needs_info`` -> ``eligible`` automatically.
    """
    replies = mail.scan_replies(since_hours=req.since_hours)
    processed = []
    for reply in replies:
        addr = notifications.extract_email(reply.get("from", ""))
        entry = mail.lookup_by_email(addr)
        if not entry:
            processed.append({"from": addr, "matched": False})
            continue
        scheme = pipeline.corpus.get_scheme(entry.get("scheme_id"))
        if not scheme:
            processed.append({"from": addr, "matched": False,
                              "error": "unknown scheme on the logged notice"})
            continue
        required = [d["name"] for d in scheme["required_documents"]
                    if d.get("mandatory", True)]
        matched = notifications.match_documents(reply.get("attachments", []), required)
        merged = list(dict.fromkeys((entry.get("submitted_documents") or []) + matched))
        result = pipeline.run_case(entry.get("scheme_id"), entry.get("applicant") or {},
                                   submitted_documents=merged,
                                   case_id=entry.get("case_id"))
        processed.append({
            "case_id": entry.get("case_id"),
            "from": addr,
            "matched_documents": matched,
            "uploads": reply.get("attachments", []),
            "previous_notice_type": entry.get("notice_type"),
            "new_verdict": result["verdict"]["decision"],
        })
    return {"replies_found": len(replies), "processed": processed}


@app.post("/api/email/draft")
def email_draft(req: DraftEmailRequest):
    """Draft a notice/email subject + body from a short instruction (AI or template)."""
    scheme_name = ""
    if req.scheme_id:
        scheme = pipeline.corpus.get_scheme(req.scheme_id)
        scheme_name = scheme["name"] if scheme else ""
    return composer.generate_draft(
        instruction=req.instruction, recipient_name=req.recipient_name,
        scheme_name=scheme_name, tone=req.tone, language=req.language)


@app.post("/api/email/send")
def email_send(req: ManualEmailRequest):
    """Send a manually composed notice/email (dry-run to the outbox when offline)."""
    if not mail.valid_recipient(req.to):
        raise HTTPException(status_code=400,
                            detail=f"Invalid or blocked recipient email: {req.to!r}")
    cc = list(req.cc or [])
    if req.notify_authority and config.AUTHORITY_EMAIL_DEFAULT \
            and config.AUTHORITY_EMAIL_DEFAULT not in cc:
        cc.append(config.AUTHORITY_EMAIL_DEFAULT)
    subject = (req.subject or "").strip() or "(no subject)"
    delivery = mail.send(req.to, subject, req.body_text,
                         cc=cc or None, from_name=req.from_name)
    if delivery.get("sent") or delivery.get("outbox_path"):
        case = {
            "case_id": req.case_id,
            "scheme_id": req.scheme_id,
            "applicant": req.applicant,
            "submitted_documents": req.submitted_documents or [],
        }
        mail.record_outbound(case, req.to, subject, "manual")
    return {"delivery": delivery}


@app.get("/api/email/settings")
def get_email_settings():
    """Current SMTP/IMAP settings (passwords masked)."""
    return {"settings": config.email_settings(mask=True)}


@app.post("/api/email/settings")
def set_email_settings(req: EmailSettingsRequest):
    """Persist SMTP/IMAP settings to runtime/email_config.json and apply them."""
    return {"settings": config.save_email_settings(req.model_dump(exclude_none=True))}


@app.post("/api/email/test")
def test_email_connection():
    """Verify the configured SMTP credentials (login only, no mail sent)."""
    return mail.test_connection()


# -- grievance / money-trace --------------------------------------------------
@app.post("/api/auth/login")
def login(req: LoginRequest):
    """Authenticate and return a signed bearer token + public user record."""
    user = auth.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"token": auth.create_token(user), "user": user}


@app.get("/api/auth/me")
def whoami(user: dict = Depends(current_user)):
    record = auth.get_user(user["sub"])
    if not record:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return record


@app.post("/api/auth/register")
def register(req: RegisterRequest, user: dict = Depends(current_user)):
    """Create an account. Beneficiary accounts may be created by anyone;
    official accounts require an existing official (admin) caller."""
    if req.role == "official" and user.get("role") != "official":
        raise HTTPException(status_code=403, detail="Only officials can create officials")
    try:
        record = auth.create_user(req.username, req.password, req.role,
                                  name=req.name, beneficiary_id=req.beneficiary_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return record


@app.get("/api/beneficiaries/{beneficiary_id}")
def get_beneficiary(beneficiary_id: str, user: dict = Depends(current_user)):
    """Beneficiary profile + their DBT ledger. Beneficiaries may only read
    their own; officials may read anyone's."""
    if user.get("role") != "official" and user.get("beneficiary_id") != beneficiary_id:
        raise HTTPException(status_code=403, detail="Not your beneficiary record")
    bene = dbt.get_beneficiary(beneficiary_id)
    if not bene:
        raise HTTPException(status_code=404, detail=f"Unknown beneficiary: {beneficiary_id}")
    return {"beneficiary": bene, "transactions": dbt.find_for_beneficiary(beneficiary_id)}


@app.get("/api/dbt/transactions")
def list_transactions(utr: str = None, beneficiary_id: str = None,
                      scheme_id: str = None, user: dict = Depends(current_user)):
    """Query the DBT ledger. Beneficiaries are scoped to their own records."""
    if user.get("role") != "official":
        beneficiary_id = user.get("beneficiary_id")
    return {"transactions": dbt.search(utr=utr, beneficiary_id=beneficiary_id,
                                       scheme_id=scheme_id)}


@app.post("/api/trace")
def trace_only(req: ComplaintRequest, user: dict = Depends(current_user)):
    """Run the money-trace pipeline without filing a complaint (preview)."""
    return trace_complaint(req.model_dump(exclude_none=True), user=user)


@app.post("/api/complaints")
def file_complaint(req: ComplaintRequest, user: dict = Depends(current_user)):
    """File a grievance and immediately run the money-trace pipeline."""
    complaint = req.model_dump(exclude_none=True)
    trace = trace_complaint(complaint, user=user)
    record = complaints_mod.create(complaint, trace, user)
    return record


@app.get("/api/complaints")
def list_complaints(user: dict = Depends(current_user)):
    """Officials see all complaints; beneficiaries see only their own."""
    return {"complaints": complaints_mod.list_for_user(user)}


@app.get("/api/complaints/summary")
def complaints_summary(user: dict = Depends(require_official)):
    """Aggregate counts for the officer dashboard."""
    return complaints_mod.summary()


@app.get("/api/complaints/{complaint_id}")
def get_complaint(complaint_id: str, user: dict = Depends(current_user)):
    record = complaints_mod.get(complaint_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Unknown complaint: {complaint_id}")
    if user.get("role") != "official" \
            and record.get("filed_by") != user.get("username") \
            and record.get("beneficiary_id") != user.get("beneficiary_id"):
        raise HTTPException(status_code=403, detail="Not your complaint")
    return record


@app.patch("/api/complaints/{complaint_id}/status")
def set_complaint_status(complaint_id: str, req: StatusUpdateRequest,
                         user: dict = Depends(require_official)):
    """Officers move a complaint through the workflow."""
    try:
        record = complaints_mod.update_status(complaint_id, req.status, user, req.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not record:
        raise HTTPException(status_code=404, detail=f"Unknown complaint: {complaint_id}")
    return record


# -- frontend -----------------------------------------------------------------
if os.path.isdir(config.FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(config.FRONTEND_DIR, "index.html"),
                            headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    @app.get("/grievance")
    def grievance_page():
        return FileResponse(os.path.join(config.FRONTEND_DIR, "grievance.html"),
                            headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
