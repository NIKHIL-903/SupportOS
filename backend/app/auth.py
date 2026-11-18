import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.config import get_settings
from backend.app.database import get_db

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: str | None = None) -> str:
    actual_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), actual_salt.encode(), 120_000).hex()
    return f"{actual_salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    actual = hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(actual, expected)


def _encode(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    signature = hmac.new(get_settings().auth_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode(token: str) -> dict[str, object] | None:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(get_settings().auth_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def seed_demo_users() -> None:
    with get_db() as db:
        db.execute("DELETE FROM users WHERE username = 'agent'")
        existing = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        if existing:
            return
        db.executemany(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            [
                ("admin", hash_password("admin123"), "admin"),
                ("customer", hash_password("customer123"), "customer"),
            ],
        )


def login(username: str, password: str) -> dict[str, str] | None:
    with get_db() as db:
        user = db.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?", (username,)).fetchone()
    if user is None or not verify_password(password, user["password_hash"]):
        return None
    token = _encode({"sub": user["id"], "username": user["username"], "role": user["role"], "exp": time.time() + 86_400})
    return {"token": token, "username": user["username"], "role": user["role"]}


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    role: str


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    payload = _decode(credentials.credentials) if credentials else None
    if payload is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return CurrentUser(id=int(payload["sub"]), username=str(payload["username"]), role=str(payload["role"]))


def require_staff(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Staff access required")
    return user


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
