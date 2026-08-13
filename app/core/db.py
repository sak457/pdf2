"""
SQLite persistence layer.

A single-file, dependency-free (stdlib ``sqlite3``) store that gives the app:
  * DB-backed users with PBKDF2-hashed passwords (admin designated by env),
  * per-user "work sessions" (each upload/sample load = one session holding the
    gzipped data + a JSON snapshot of everything the analyst does), and
  * strict ownership (a user sees only their own sessions; an admin sees all).

Nothing here imports Streamlit; ``serialize_state`` / ``restore_state`` take a
mapping (``st.session_state``) but treat it as a plain dict.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager

from . import loader

DB_PATH = os.environ.get(
    "AML_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "aml.db"))

PBKDF2_ITERS = 200_000
STATE_VERSION = 2
TOKEN_TTL_HOURS = 24  # "stay logged in" cookie lifetime


# --------------------------------------------------------------------------- #
#  Connection
# --------------------------------------------------------------------------- #
@contextmanager
def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=5.0)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=5000")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


DDL = """
CREATE TABLE IF NOT EXISTS users (
  username      TEXT PRIMARY KEY,
  password_hash BLOB NOT NULL,
  salt          BLOB NOT NULL,
  iterations    INTEGER NOT NULL DEFAULT 200000,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  created_by    TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  username   TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  csv_gz     BLOB NOT NULL,
  row_count  INTEGER NOT NULL,
  meta       TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(username, updated_at DESC);
CREATE TABLE IF NOT EXISTS session_state (
  session_id INTEGER PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
  state_json TEXT NOT NULL,
  state_hash TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS auth_tokens (
  token           TEXT PRIMARY KEY,            -- sha256 of the raw cookie value
  username        TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
  last_session_id INTEGER,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at      TEXT NOT NULL
);
"""


def init_db() -> bool:
    """Create tables and bootstrap the admin account. Returns True if the
    bootstrap used the *default* admin password (so the UI can warn)."""
    with _connect() as con:
        con.executescript(DDL)
        con.execute(f"PRAGMA user_version={STATE_VERSION}")
    purge_expired_tokens()
    return bootstrap()


# --------------------------------------------------------------------------- #
#  Passwords / users
# --------------------------------------------------------------------------- #
def _hash_pw(password: str, salt: bytes, iters: int = PBKDF2_ITERS) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, iters)


def admin_usernames() -> set[str]:
    raw = os.environ.get("AML_ADMIN_USERS", "admin")
    return {u.strip() for u in raw.split(",") if u.strip()}


def is_admin(username: str) -> bool:
    return str(username) in admin_usernames()


def users_count() -> int:
    with _connect() as con:
        return con.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_user(username: str, password: str, created_by: str | None = None) -> None:
    username = str(username).strip()
    if not username:
        raise ValueError("Username is required.")
    if not str(password):
        raise ValueError("Password is required.")
    salt = os.urandom(16)
    with _connect() as con:
        exists = con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
        if exists:
            raise ValueError(f"User “{username}” already exists.")
        con.execute(
            "INSERT INTO users(username, password_hash, salt, iterations, created_by) "
            "VALUES (?,?,?,?,?)",
            (username, _hash_pw(password, salt), salt, PBKDF2_ITERS, created_by))


def verify_user(username: str, password: str) -> bool:
    username = str(username).strip()
    with _connect() as con:
        row = con.execute(
            "SELECT password_hash, salt, iterations FROM users WHERE username=?",
            (username,)).fetchone()
    if not row:
        # constant-ish time even for unknown users
        _hash_pw(password, b"dummy-salt-000000", PBKDF2_ITERS)
        return False
    calc = _hash_pw(password, row["salt"], row["iterations"])
    return hmac.compare_digest(calc, row["password_hash"])


def set_password(username: str, new_password: str) -> None:
    salt = os.urandom(16)
    with _connect() as con:
        con.execute("UPDATE users SET password_hash=?, salt=?, iterations=? WHERE username=?",
                    (_hash_pw(new_password, salt), salt, PBKDF2_ITERS, str(username).strip()))


def delete_user(username: str) -> None:
    with _connect() as con:
        con.execute("DELETE FROM users WHERE username=?", (str(username).strip(),))


def list_users() -> list[dict]:
    with _connect() as con:
        rows = con.execute(
            "SELECT username, created_at, created_by FROM users ORDER BY username").fetchall()
    return [dict(r) for r in rows]


def bootstrap() -> bool:
    """Create the env-designated admin account(s) if the users table is empty.
    Returns True if the default password ('admin') was used."""
    if users_count() > 0:
        return False
    pw = os.environ.get("AML_ADMIN_PASSWORD", "admin")
    default_used = "AML_ADMIN_PASSWORD" not in os.environ
    for name in sorted(admin_usernames()):
        try:
            create_user(name, pw, created_by="bootstrap")
        except ValueError:
            pass
    return default_used


# --------------------------------------------------------------------------- #
#  Work sessions
# --------------------------------------------------------------------------- #
def _can_access(con, sid: int, acting_user: str):
    """Write access: only the owner or an admin. Used by rename/delete."""
    row = con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not row:
        raise LookupError("Session not found.")
    if row["username"] != acting_user and not is_admin(acting_user):
        raise PermissionError("Not authorised for this session.")
    return row


def _can_read(con, sid: int, acting_user: str):
    """Read access: the owner, an admin, or any user reading an admin-created
    session (normal users are read-only browsers of the admin's sessions)."""
    row = con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not row:
        raise LookupError("Session not found.")
    if (row["username"] == acting_user or is_admin(acting_user)
            or is_admin(row["username"])):
        return row
    raise PermissionError("Not authorised for this session.")


def create_session(username: str, name: str, df) -> int:
    csv = df[loader.export_columns(df)].to_csv(index=False).encode("utf-8")
    blob = gzip.compress(csv)
    meta = json.dumps({"columns": list(loader.export_columns(df))})
    with _connect() as con:
        cur = con.execute(
            "INSERT INTO sessions(username, name, csv_gz, row_count, meta) VALUES (?,?,?,?,?)",
            (str(username), str(name)[:200], blob, int(len(df)), meta))
        return cur.lastrowid


def list_sessions(acting_user: str) -> list[dict]:
    with _connect() as con:
        if is_admin(acting_user):
            rows = con.execute(
                "SELECT id, username, name, created_at, updated_at, row_count "
                "FROM sessions ORDER BY updated_at DESC").fetchall()
        else:
            # Normal users browse sessions created by admins (read-only).
            admins = sorted(admin_usernames())
            ph = ",".join("?" * len(admins)) or "NULL"
            rows = con.execute(
                "SELECT id, username, name, created_at, updated_at, row_count "
                f"FROM sessions WHERE username IN ({ph}) ORDER BY updated_at DESC",
                admins).fetchall()
    return [dict(r) for r in rows]


def load_session(sid: int, acting_user: str):
    with _connect() as con:
        row = _can_read(con, sid, acting_user)
    csv = gzip.decompress(row["csv_gz"])
    df = loader.read_csv(io.BytesIO(csv))
    return dict(row), df


def rename_session(sid: int, new_name: str, acting_user: str) -> None:
    with _connect() as con:
        _can_access(con, sid, acting_user)
        con.execute("UPDATE sessions SET name=?, updated_at=datetime('now') WHERE id=?",
                    (str(new_name)[:200], sid))


def touch_session(sid: int) -> None:
    with _connect() as con:
        con.execute("UPDATE sessions SET updated_at=datetime('now') WHERE id=?", (sid,))


def delete_session(sid: int, acting_user: str) -> None:
    with _connect() as con:
        _can_access(con, sid, acting_user)
        con.execute("DELETE FROM sessions WHERE id=?", (sid,))  # state cascades


def wipe_all_sessions() -> None:
    """Admin: delete ALL sessions and their state. User accounts are kept."""
    with _connect() as con:
        con.execute("DELETE FROM session_state")
        con.execute("DELETE FROM sessions")


# --------------------------------------------------------------------------- #
#  State snapshot
# --------------------------------------------------------------------------- #
def serialize_state(ss) -> tuple[str, str]:
    poi = dict(ss.get("poi") or {})
    photo = poi.pop("photo", None)
    poi["photo_b64"] = base64.b64encode(photo).decode() if photo else None
    state = {
        "v": STATE_VERSION,
        "poi": poi,
        "nodes": ss.get("nodes") or {},
        "cp_groups": ss.get("cp_groups") or [],
        "cp_next_id": ss.get("cp_next_id", 1),
        "disabled": sorted(ss.get("disabled") or []),
        "kpi_hidden": sorted(ss.get("kpi_hidden") or []),
        "hidden_charts": sorted(ss.get("hidden_charts") or []),
        "hidden_tabs": sorted(ss.get("hidden_tabs") or []),
        "hide_risk": bool(ss.get("hide_risk", False)),
        "attachments": ss.get("attachments") or [],
        "att_next_id": ss.get("att_next_id", 1),
        "bluf_override": ss.get("bluf_override", ""),
        "analyst_note": ss.get("analyst_note", ""),
        "chat": ss.get("chat") or [],
    }
    js = json.dumps(state, ensure_ascii=False, sort_keys=True)
    return js, hashlib.sha256(js.encode("utf-8")).hexdigest()


def restore_state(ss, js: str) -> None:
    s = json.loads(js)
    poi = dict(s.get("poi") or {})
    b64 = poi.pop("photo_b64", None)
    poi["photo"] = base64.b64decode(b64) if b64 else None
    ss["poi"] = {**(ss.get("poi") or {}), **poi}
    ss["nodes"] = s.get("nodes") or {}
    ss["cp_groups"] = s.get("cp_groups") or []
    ss["cp_next_id"] = s.get("cp_next_id", 1)
    ss["disabled"] = set(s.get("disabled") or [])
    ss["kpi_hidden"] = set(s.get("kpi_hidden") or [])
    ss["hidden_charts"] = set(s.get("hidden_charts") or [])
    ss["hidden_tabs"] = set(s.get("hidden_tabs") or [])
    ss["hide_risk"] = bool(s.get("hide_risk", False))
    ss["attachments"] = s.get("attachments") or []
    ss["att_next_id"] = s.get("att_next_id", 1)
    ss["bluf_override"] = s.get("bluf_override", "")
    ss["analyst_note"] = s.get("analyst_note", "")
    ss["chat"] = s.get("chat") or []


def save_state(sid: int, state_json: str, state_hash: str) -> None:
    with _connect() as con:
        con.execute(
            "INSERT INTO session_state(session_id, state_json, state_hash, updated_at) "
            "VALUES (?,?,?,datetime('now')) "
            "ON CONFLICT(session_id) DO UPDATE SET "
            "state_json=excluded.state_json, state_hash=excluded.state_hash, "
            "updated_at=datetime('now')",
            (sid, state_json, state_hash))


def load_state(sid: int) -> str | None:
    with _connect() as con:
        row = con.execute("SELECT state_json FROM session_state WHERE session_id=?",
                          (sid,)).fetchone()
    return row["state_json"] if row else None


# --------------------------------------------------------------------------- #
#  Persistent-login tokens ("stay logged in" cookie)
# --------------------------------------------------------------------------- #
def _token_hash(raw: str) -> str:
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()


def create_token(username: str) -> str:
    """Issue a persistent-login token for a user; returns the RAW value to put
    in the cookie (only its sha256 is stored)."""
    raw = secrets.token_urlsafe(32)
    with _connect() as con:
        con.execute(
            "INSERT INTO auth_tokens(token, username, expires_at) "
            "VALUES (?,?,datetime('now', ?))",
            (_token_hash(raw), str(username), f"+{TOKEN_TTL_HOURS} hours"))
    return raw


def verify_token(raw: str) -> str | None:
    """Return the username for a valid, unexpired token, else None."""
    if not raw:
        return None
    with _connect() as con:
        row = con.execute(
            "SELECT username FROM auth_tokens "
            "WHERE token=? AND expires_at > datetime('now')",
            (_token_hash(raw),)).fetchone()
    return row["username"] if row else None


def token_last_session(raw: str) -> int | None:
    if not raw:
        return None
    with _connect() as con:
        row = con.execute("SELECT last_session_id FROM auth_tokens WHERE token=?",
                          (_token_hash(raw),)).fetchone()
    return row["last_session_id"] if row and row["last_session_id"] is not None else None


def set_token_session(raw: str, sid: int | None) -> None:
    if not raw:
        return
    with _connect() as con:
        con.execute("UPDATE auth_tokens SET last_session_id=? WHERE token=?",
                    (sid, _token_hash(raw)))


def delete_token(raw: str) -> None:
    if not raw:
        return
    with _connect() as con:
        con.execute("DELETE FROM auth_tokens WHERE token=?", (_token_hash(raw),))


def purge_expired_tokens() -> None:
    with _connect() as con:
        con.execute("DELETE FROM auth_tokens WHERE expires_at <= datetime('now')")
