"""
config.py
---------
Central configuration for the YojanaBench backend.

Resolves filesystem paths relative to this file so the project runs from any
working directory, and exposes small tunable settings (LLM endpoint, retrieval
weights, confidence threshold).
"""
import json
import os

# --- Filesystem layout -------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DATASET_DIR = DATA_DIR  # backwards-compatible alias
SCHEMES_DIR = os.path.join(DATA_DIR, "schemes")
GUIDELINES_DIR = os.path.join(DATA_DIR, "guidelines")
CASES_DIR = os.path.join(DATA_DIR, "cases")
QA_BENCHMARK_PATH = os.path.join(DATA_DIR, "qa", "qa_benchmark.json")
LEADERBOARD_PATH = os.path.join(DATA_DIR, "meta", "leaderboard.json")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

# --- DBT money-trace / grievance module --------------------------------------
BENEFICIARIES_PATH = os.path.join(DATA_DIR, "beneficiaries.json")
DBT_DIR = os.path.join(DATA_DIR, "dbt")
DBT_TRANSACTIONS_PATH = os.path.join(DBT_DIR, "transactions.json")

# --- Authentication ----------------------------------------------------------
# Secret used to sign session tokens. Override in production via the env var;
# a random per-process secret is generated otherwise (tokens then reset on
# restart, which is fine for the offline demo).
AUTH_SECRET = os.environ.get("YOJANA_AUTH_SECRET") or os.urandom(32).hex()
AUTH_TOKEN_TTL_SECONDS = int(os.environ.get("YOJANA_AUTH_TTL", str(12 * 3600)))

# --- Retrieval ---------------------------------------------------------------
TOP_K = 6                 # number of evidence clauses returned by the RAG agent
BM25_WEIGHT = 0.5         # hybrid retrieval weight for keyword/BM25 score
DENSE_WEIGHT = 0.5        # hybrid retrieval weight for TF-IDF cosine score

# --- Orchestrator ------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.60   # below this the human-approval gate is flagged

# --- LLM (optional, zero-cost local Ollama) ----------------------------------
OLLAMA_HOST = os.environ.get("YOJANA_OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("YOJANA_OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT = float(os.environ.get("YOJANA_OLLAMA_TIMEOUT", "8"))

# --- Notifications (email automation layer) ----------------------------------
# SMTP/IMAP credentials are the same mailbox used by the OrbitAvanya
# EmailAutomation project (Config.SENDER_EMAIL / SMTP_SERVER / ...), so notices
# are delivered for real out of the box. Every value can be overridden with the
# YOJANA_SMTP_* / YOJANA_IMAP_* environment variables.
#
# Leave YOJANA_SMTP_HOST empty (or set YOJANA_SMTP_USER empty) to fall back to
# offline "outbox" mode: notices are rendered to disk and reported as a dry run
# - no network, no mail.
RUNTIME_DIR = os.path.join(PROJECT_ROOT, "runtime")
OUTBOX_DIR = os.path.join(RUNTIME_DIR, "outbox")
GENERATED_CASES_DIR = os.path.join(RUNTIME_DIR, "cases")
NOTIFICATION_LOG_PATH = os.path.join(RUNTIME_DIR, "notification_log.json")
APPEAL_REGISTRY_PATH = os.path.join(RUNTIME_DIR, "appeal_registry.json")
EMAIL_CONFIG_PATH = os.path.join(RUNTIME_DIR, "email_config.json")

# --- Grievance / money-trace persistence -------------------------------------
USERS_PATH = os.path.join(RUNTIME_DIR, "users.json")
COMPLAINTS_PATH = os.path.join(RUNTIME_DIR, "complaints.json")

SMTP_HOST = os.environ.get("YOJANA_SMTP_HOST", "s13429.bom1.stableserver.net")
SMTP_PORT = int(os.environ.get("YOJANA_SMTP_PORT", "465"))
SMTP_USER = os.environ.get("YOJANA_SMTP_USER", "pradeep@orbitavanyatech.com")
SMTP_PASSWORD = os.environ.get("YOJANA_SMTP_PASSWORD", "Prad@2026")
SMTP_FROM_NAME = os.environ.get("YOJANA_SMTP_FROM_NAME", "YojanaBench")
SMTP_USE_SSL = os.environ.get("YOJANA_SMTP_SSL", "true").lower() not in ("0", "false", "no")

IMAP_HOST = os.environ.get("YOJANA_IMAP_HOST", "s13429.bom1.stableserver.net")
IMAP_PORT = int(os.environ.get("YOJANA_IMAP_PORT", "993"))
IMAP_USER = os.environ.get("YOJANA_IMAP_USER", "pradeep@orbitavanyatech.com")
IMAP_PASSWORD = os.environ.get("YOJANA_IMAP_PASSWORD", "Prad@2026")

# scheme_id -> government/authority email that receives verdict digests.
# Resolution order: scheme schema "authority_email" -> this map -> default below.
SCHEME_AUTHORITY_EMAILS = {}
AUTHORITY_EMAIL_DEFAULT = os.environ.get("YOJANA_AUTHORITY_EMAIL", "")

# Default language for applicant notices when the case does not specify one.
DEFAULT_NOTICE_LANGUAGE = os.environ.get("YOJANA_NOTICE_LANG", "en")

# --- Editable email settings (persisted to runtime/email_config.json) --------
# The dashboard edits SMTP/IMAP credentials at runtime - the same idea as the
# OrbitAvanya EmailAutomation dashboard that edits RUN_CAMPAIGN.Config. Values
# saved here override the environment/defaults above and survive restarts.
EMAIL_SETTING_KEYS = (
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_NAME",
    "SMTP_USE_SSL", "IMAP_HOST", "IMAP_PORT", "IMAP_USER", "IMAP_PASSWORD",
    "AUTHORITY_EMAIL_DEFAULT",
)
PASSWORD_MASK = "********"


def _coerce(key, value):
    if key in ("SMTP_PORT", "IMAP_PORT"):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if key == "SMTP_USE_SSL":
        if isinstance(value, str):
            return value.lower() not in ("0", "false", "no", "")
        return bool(value)
    return value


def _load_email_file() -> dict:
    if not os.path.exists(EMAIL_CONFIG_PATH):
        return {}
    try:
        with open(EMAIL_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _apply_email_file(data) -> None:
    for key, value in (data or {}).items():
        if key in EMAIL_SETTING_KEYS and value is not None:
            globals()[key] = _coerce(key, value)


def email_settings(mask: bool = False) -> dict:
    """Current email settings; passwords replaced by a mask when ``mask``."""
    out = {}
    for key in EMAIL_SETTING_KEYS:
        value = globals().get(key)
        if mask and "PASSWORD" in key and value:
            value = PASSWORD_MASK
        out[key] = value
    return out


def save_email_settings(data: dict) -> dict:
    """Persist the editable settings and apply them immediately (no restart)."""
    stored = _load_email_file()
    for key, value in (data or {}).items():
        if key not in EMAIL_SETTING_KEYS or value is None:
            continue
        if "PASSWORD" in key and value == PASSWORD_MASK:
            continue  # password left unchanged - keep the stored one
        stored[key] = _coerce(key, value)
    os.makedirs(os.path.dirname(EMAIL_CONFIG_PATH), exist_ok=True)
    with open(EMAIL_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(stored, f, indent=2)
    _apply_email_file(stored)
    return email_settings(mask=True)


# Apply any previously-saved overrides at import time.
_apply_email_file(_load_email_file())
