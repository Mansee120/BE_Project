"""
auth.py
-------
Authentication and role-based access control for the YojanaBench grievance
module. Implemented with the Python standard library only (no external crypto
dependency):

  * passwords  - PBKDF2-HMAC-SHA256 with a per-user random salt and a high
                 iteration count, stored as ``pbkdf2_sha256$iter$salt$hash``.
  * sessions   - compact, signed (HMAC-SHA256) bearer tokens carrying the
                 username, role, linked beneficiary id and an expiry.

Two roles are supported:

  * ``beneficiary`` - a member of the public; may file complaints and see only
    their own.
  * ``official``    - a department officer; may see and act on every complaint.

Default demo accounts are seeded on first use (see ``SEED_USERS``).
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from . import config

# --- password hashing --------------------------------------------------------
_ALGO = "pbkdf2_sha256"
_ITERATIONS = 200_000


def hash_password(password: str, salt: bytes = None, iterations: int = _ITERATIONS) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != _ALGO:
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# --- signed session tokens ---------------------------------------------------
def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(payload_b64: str) -> str:
    mac = hmac.new(config.AUTH_SECRET.encode("utf-8"),
                   payload_b64.encode("ascii"), hashlib.sha256)
    return _b64e(mac.digest())


def create_token(user: dict, ttl: int = None) -> str:
    now = int(time.time())
    payload = {
        "sub": user["username"],
        "username": user["username"],
        "role": user["role"],
        "name": user.get("name", user["username"]),
        "beneficiary_id": user.get("beneficiary_id"),
        "iat": now,
        "exp": now + (ttl or config.AUTH_TOKEN_TTL_SECONDS),
    }
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_token(token: str) -> dict:
    """Return the token payload, or ``None`` if invalid/expired/tampered."""
    if not token or "." not in token:
        return None
    payload_b64, signature = token.split(".", 1)
    if not hmac.compare_digest(_sign(payload_b64), signature):
        return None
    try:
        payload = json.loads(_b64d(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload


# --- user store --------------------------------------------------------------
# Demo accounts are created automatically the first time the store is used.
SEED_USERS = [
    {"username": "ravi", "password": "ravi123", "role": "beneficiary",
     "name": "Ravi Kumar", "beneficiary_id": "B-0001"},
    {"username": "sita", "password": "sita123", "role": "beneficiary",
     "name": "Sita Devi", "beneficiary_id": "B-0002"},
    {"username": "geeta", "password": "geeta123", "role": "beneficiary",
     "name": "Geeta Kumari", "beneficiary_id": "B-0004"},
    {"username": "raju", "password": "raju123", "role": "beneficiary",
     "name": "Raju Prasad", "beneficiary_id": "B-0010"},
    {"username": "officer", "password": "officer123", "role": "official",
     "name": "Block Officer", "beneficiary_id": None, "admin": False},
    {"username": "admin", "password": "admin123", "role": "official",
     "name": "District Administrator", "beneficiary_id": None, "admin": True},
]


def _load_raw() -> dict:
    if not os.path.exists(config.USERS_PATH):
        return {"users": []}
    try:
        with open(config.USERS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"users": []}
    except (json.JSONDecodeError, OSError):
        return {"users": []}


def _save_raw(data: dict) -> None:
    os.makedirs(os.path.dirname(config.USERS_PATH), exist_ok=True)
    with open(config.USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _seed_if_empty() -> None:
    data = _load_raw()
    if data.get("users"):
        return
    users = []
    for seed in SEED_USERS:
        user = dict(seed)
        user["password"] = hash_password(seed["password"])
        user.setdefault("admin", False)
        users.append(user)
    _save_raw({"users": users})


def _public(user: dict) -> dict:
    """Strip the password hash before the record leaves this module."""
    return {k: v for k, v in user.items() if k != "password"}


def list_users() -> list:
    _seed_if_empty()
    return [_public(u) for u in _load_raw().get("users", [])]


def get_user(username: str) -> dict:
    _seed_if_empty()
    for u in _load_raw().get("users", []):
        if u["username"] == username:
            return _public(u)
    return None


def authenticate(username: str, password: str) -> dict:
    """Return the public user record on success, else ``None``."""
    _seed_if_empty()
    for u in _load_raw().get("users", []):
        if u["username"] == username and verify_password(password, u.get("password", "")):
            return _public(u)
    return None


def create_user(username: str, password: str, role: str, name: str = "",
                beneficiary_id: str = None, admin: bool = False) -> dict:
    """Create a new user. Raises ``ValueError`` on duplicates/invalid input."""
    username = (username or "").strip().lower()
    if not username or not password:
        raise ValueError("username and password are required")
    if role not in ("beneficiary", "official"):
        raise ValueError("role must be 'beneficiary' or 'official'")
    if role == "beneficiary" and not beneficiary_id:
        raise ValueError("beneficiary accounts must be linked to a beneficiary_id")
    _seed_if_empty()
    data = _load_raw()
    if any(u["username"] == username for u in data.get("users", [])):
        raise ValueError("username already exists")
    user = {
        "username": username,
        "password": hash_password(password),
        "role": role,
        "name": name or username,
        "beneficiary_id": beneficiary_id,
        "admin": bool(admin),
    }
    data.setdefault("users", []).append(user)
    _save_raw(data)
    return _public(user)
