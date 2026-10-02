import argparse
import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Body, FastAPI, Header, HTTPException, Query

APP_TITLE = "ACA Platform"
SERVER_VERSION = "1.0.2"
API_PREFIX = "/api/v1"
PBKDF2_ITERATIONS = 310000
VALID_PHASES = tuple(range(1, 8))
INVITE_PREFIX = "ACA-TEACH-"
INVITE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
RAILWAY_VOLUME_ROOT = str(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or "").strip()

def _default_server_path(filename):
    if RAILWAY_VOLUME_ROOT:
        os.makedirs(RAILWAY_VOLUME_ROOT, exist_ok=True)
        return os.path.join(RAILWAY_VOLUME_ROOT, filename)
    return os.path.abspath(filename)

DB_PATH = os.environ.get("ACA_SERVER_DB") or _default_server_path("aca_server.sqlite3")
BACKUP_DIR = os.environ.get("ACA_SERVER_BACKUP_DIR") or _default_server_path("aca_server_backups")
_WRITE_LOCK = threading.RLock()

# Same one-time system admin seed as the desktop build. Secrets are represented
# only by their PBKDF2 records; plaintext credentials are not stored in this file.
SYSTEM_ADMIN_USERNAME = "admin"
SYSTEM_ADMIN_DISPLAY_NAME = "Principal Admin"
SYSTEM_ADMIN_SECURITY_QUESTION = "Название крутой"
SYSTEM_ADMIN_PASSWORD_HASH = {
    "salt": "ca215e6bd398c06ed63fa2bd4e1614a6",
    "digest": "ba9d0a58f68cce883fd96b3d45386815438b191f10c53855877a3794262d3f91",
    "iterations": 310000,
    "algorithm": "pbkdf2_hmac_sha256",
}
SYSTEM_ADMIN_SECURITY_ANSWER_HASH = {
    "salt": "a176525b96042cbcb9c70c99dab97dcc",
    "digest": "5ebe41c71b8ded49a9b07627daa44564360d22963ec1ad265be10345b7e8136e",
    "iterations": 310000,
    "algorithm": "pbkdf2_hmac_sha256",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def unix_now():
    return int(time.time())


def _lesson_phase_map():
    phase_lengths = [7, 8, 8, 7, 25, 10, 55]
    out = {}
    idx = 1
    for phase, count in enumerate(phase_lengths, 1):
        for _ in range(count):
            out[f"L{idx:02d}"] = phase
            idx += 1
    if idx != 121:
        raise RuntimeError("Curriculum phase map must contain 120 lessons")
    return out


LESSON_PHASE = _lesson_phase_map()


def default_state():
    return {
        "meta": {
            "app": APP_TITLE,
            "version": "server",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        "settings": {
            "probation_threshold": 8.90,
            "team_threshold": 9.30,
            "homework_penalty": 0.25,
            "active_user_role": "HOST",
            "active_student_id": None,
            "language": "ru",
            "moderator_requests": {
                "gameplay": False,
                "art": False,
                "verification": False,
            },
        },
        "students": {},
        "accounts": {},
        "auth_audit": [],
        "auth_security": {},
        "teacher_invites": {},
        "teacher_sessions": {},
        "notifications": [],
        "audit_log": [],
    }


def normalize_username(username):
    value = str(username or "").strip().casefold()
    if not (3 <= len(value) <= 32):
        raise ValueError("Username must contain 3–32 characters.")
    if any(not (ch.isalnum() or ch in "._-") for ch in value):
        raise ValueError("Username may contain letters, numbers, dot, underscore, and hyphen only.")
    return value


def validate_password(password):
    value = str(password or "")
    if len(value) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    if len(value) > 256:
        raise ValueError("Password is too long.")
    return value


def hash_password(password, salt_hex=None, iterations=None):
    password = validate_password(password)
    iterations = int(iterations or PBKDF2_ITERATIONS)
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {
        "salt": salt.hex(),
        "digest": digest.hex(),
        "iterations": iterations,
        "algorithm": "pbkdf2_hmac_sha256",
    }


def verify_password(password, record):
    if not isinstance(record, dict):
        return False
    try:
        candidate = hash_password(
            password,
            salt_hex=record["salt"],
            iterations=int(record.get("iterations", PBKDF2_ITERATIONS)),
        )["digest"]
    except Exception:
        return False
    return hmac.compare_digest(candidate, str(record.get("digest", "")))


def normalize_recovery_code(code):
    raw = str(code or "").strip().upper()
    if raw.startswith("ACA-REC-"):
        raw = raw[len("ACA-REC-"):]
    return "".join(ch for ch in raw if ch.isalnum())


def hash_recovery_code(code, salt_hex=None, iterations=None):
    normalized = normalize_recovery_code(code)
    if len(normalized) != 8:
        raise ValueError("Recovery code must contain 8 code characters.")
    iterations = int(iterations or PBKDF2_ITERATIONS)
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", normalized.encode("ascii"), salt, iterations)
    return {
        "salt": salt.hex(),
        "digest": digest.hex(),
        "iterations": iterations,
        "algorithm": "pbkdf2_hmac_sha256",
    }


def verify_recovery_code(code, record):
    if not isinstance(record, dict):
        return False
    try:
        candidate = hash_recovery_code(
            code,
            salt_hex=record["salt"],
            iterations=int(record.get("iterations", PBKDF2_ITERATIONS)),
        )["digest"]
    except Exception:
        return False
    return hmac.compare_digest(candidate, str(record.get("digest", "")))


def normalize_security_answer(answer):
    value = str(answer or "").strip().casefold()
    if not value or len(value) > 256:
        raise ValueError("Security answer is invalid.")
    return value


def hash_security_answer(answer, salt_hex=None, iterations=None):
    normalized = normalize_security_answer(answer)
    iterations = int(iterations or PBKDF2_ITERATIONS)
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", normalized.encode("utf-8"), salt, iterations)
    return {
        "salt": salt.hex(),
        "digest": digest.hex(),
        "iterations": iterations,
        "algorithm": "pbkdf2_hmac_sha256",
    }


def verify_security_answer(answer, record):
    if not isinstance(record, dict):
        return False
    try:
        candidate = hash_security_answer(
            answer,
            salt_hex=record["salt"],
            iterations=int(record.get("iterations", PBKDF2_ITERATIONS)),
        )["digest"]
    except Exception:
        return False
    return hmac.compare_digest(candidate, str(record.get("digest", "")))


def generate_recovery_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    body = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"ACA-REC-{body[:4]}-{body[4:]}"


def normalize_phases(values):
    out = []
    for value in values or []:
        try:
            p = int(value)
        except (TypeError, ValueError):
            continue
        if p in VALID_PHASES and p not in out:
            out.append(p)
    return sorted(out)


def find_account_by_username(state, username):
    normalized = str(username or "").strip().casefold()
    for uid, account in state.get("accounts", {}).items():
        if str(account.get("username", "")).casefold() == normalized:
            return uid, account
    return None, None


def public_account(account):
    return {
        "user_id": account.get("user_id"),
        "username": account.get("username"),
        "display_name": account.get("display_name"),
        "role": account.get("role"),
        "active": bool(account.get("active", True)),
        "student_id": account.get("student_id"),
        "teacher_id": account.get("teacher_id"),
        "authorized_phases": list(account.get("authorized_phases", [])),
        "must_change_password": bool(account.get("must_change_password", False)),
        "created_at": account.get("created_at"),
        "last_login_at": account.get("last_login_at"),
        "recovery_code_configured": isinstance(account.get("recovery_code"), dict),
        "security_question": account.get("security_question"),
        "security_question_configured": bool(account.get("security_question") and isinstance(account.get("security_answer"), dict)),
    }


def session_context(account):
    role = account.get("role", "STUDENT")
    phases = list(account.get("authorized_phases", []))
    is_admin = role == "ADMIN"
    is_teacher = role == "TEACHER"
    return {
        "user_id": account.get("user_id"),
        "username": account.get("username"),
        "display_name": account.get("display_name"),
        "role": role,
        "student_id": account.get("student_id"),
        "teacher_id": account.get("teacher_id"),
        "must_change_password": bool(account.get("must_change_password", False)),
        "authorized_phases": list(VALID_PHASES) if is_admin else phases,
        "permissions": {
            "view_all_students": is_admin or is_teacher,
            "manage_students": is_admin,
            "manage_teachers": is_admin,
            "manage_accounts": is_admin,
            "backup_database": is_admin,
            "grade_phases": list(VALID_PHASES) if is_admin else phases if is_teacher else [],
            "edit_own_submission_links": role == "STUDENT",
            "manage_graduation": is_admin or (is_teacher and 7 in phases),
        },
    }


def audit_auth(state, user_id, action, payload=None):
    state.setdefault("auth_audit", []).append({
        "event_id": uuid.uuid4().hex,
        "user_id": user_id,
        "action": action,
        "payload": payload or {},
        "timestamp": now_iso(),
        "unix_timestamp": unix_now(),
    })


def issue_recovery_code(state, account, action="RECOVERY_CODE_ISSUED"):
    code = generate_recovery_code()
    account["recovery_code"] = hash_recovery_code(code)
    account["recovery_code_created_at"] = now_iso()
    account["recovery_failed_attempts"] = 0
    account["recovery_locked_until"] = 0
    audit_auth(state, account.get("user_id"), action, {})
    return code


def ensure_system_admin(state):
    security = state.setdefault("auth_security", {})
    if security.get("system_admin_seed_v1_applied"):
        return
    uid, account = find_account_by_username(state, SYSTEM_ADMIN_USERNAME)
    if account is None:
        uid = "U-" + uuid.uuid4().hex
        account = {
            "user_id": uid,
            "username": SYSTEM_ADMIN_USERNAME,
            "display_name": SYSTEM_ADMIN_DISPLAY_NAME,
            "role": "ADMIN",
            "password": dict(SYSTEM_ADMIN_PASSWORD_HASH),
            "active": True,
            "created_at": now_iso(),
            "created_timestamp": unix_now(),
            "last_login_at": None,
            "last_login_timestamp": None,
            "failed_login_count": 0,
            "student_id": None,
            "teacher_id": None,
            "authorized_phases": list(VALID_PHASES),
            "must_change_password": False,
            "recovery_code": None,
            "recovery_code_created_at": None,
            "recovery_failed_attempts": 0,
            "recovery_locked_until": 0,
            "security_question": SYSTEM_ADMIN_SECURITY_QUESTION,
            "security_answer": dict(SYSTEM_ADMIN_SECURITY_ANSWER_HASH),
            "security_answer_failed_attempts": 0,
            "security_answer_locked_until": 0,
            "system_seeded": True,
        }
        state.setdefault("accounts", {})[uid] = account
    else:
        account["role"] = "ADMIN"
        account["authorized_phases"] = list(VALID_PHASES)
        account.setdefault("security_question", SYSTEM_ADMIN_SECURITY_QUESTION)
        account.setdefault("security_answer", dict(SYSTEM_ADMIN_SECURITY_ANSWER_HASH))
    security["system_admin_seed_v1_applied"] = True
    audit_auth(state, uid, "SYSTEM_ADMIN_SEED_APPLIED", {"username": SYSTEM_ADMIN_USERNAME})


def migrate_state(state):
    default = default_state()
    if not isinstance(state, dict):
        state = default
    for key, value in default.items():
        if key not in state:
            state[key] = copy.deepcopy(value)
    for key, value in default["settings"].items():
        state["settings"].setdefault(key, copy.deepcopy(value))
    state.setdefault("auth_security", {})
    for account in state.get("accounts", {}).values():
        account.setdefault("must_change_password", False)
        account.setdefault("recovery_code", None)
        account.setdefault("recovery_code_created_at", None)
        account.setdefault("recovery_failed_attempts", 0)
        account.setdefault("recovery_locked_until", 0)
        account.setdefault("security_question", None)
        account.setdefault("security_answer", None)
        account.setdefault("security_answer_failed_attempts", 0)
        account.setdefault("security_answer_locked_until", 0)
    for invite in state.get("teacher_invites", {}).values():
        invite.setdefault("is_enabled", True)
        invite.setdefault("disabled_timestamp", None)
        invite.setdefault("disabled_iso", None)
    ensure_system_admin(state)
    state["meta"]["app"] = APP_TITLE
    state["meta"]["updated_at"] = now_iso()
    return state


def db_connect():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA busy_timeout=15000")
    return con


def init_db(import_json=None, force_import=False):
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)) or ".", exist_ok=True)
    with _WRITE_LOCK, db_connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                revision INTEGER NOT NULL,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                last_seen_at INTEGER NOT NULL
            )
        """)
        row = con.execute("SELECT revision, payload FROM app_state WHERE id=1").fetchone()
        imported = None
        if import_json and os.path.exists(import_json) and (row is None or force_import):
            with open(import_json, "r", encoding="utf-8") as f:
                imported = json.load(f)
        if row is None or imported is not None:
            state = migrate_state(imported if imported is not None else default_state())
            payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
            if row is None:
                con.execute(
                    "INSERT INTO app_state(id, revision, payload, updated_at) VALUES(1,?,?,?)",
                    (1, payload, now_iso()),
                )
            else:
                con.execute(
                    "UPDATE app_state SET revision=?, payload=?, updated_at=? WHERE id=1",
                    (int(row["revision"]) + 1, payload, now_iso()),
                )
            con.execute("DELETE FROM sessions")
        else:
            state = migrate_state(json.loads(row["payload"]))
            payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
            con.execute(
                "UPDATE app_state SET payload=?, updated_at=? WHERE id=1",
                (payload, now_iso()),
            )
        con.commit()


def load_state(con=None):
    own = con is None
    con = con or db_connect()
    try:
        row = con.execute("SELECT revision, payload FROM app_state WHERE id=1").fetchone()
        if not row:
            raise RuntimeError("ACA server state is not initialized")
        return int(row["revision"]), json.loads(row["payload"])
    finally:
        if own:
            con.close()


def save_state(con, revision, state):
    state["meta"]["updated_at"] = now_iso()
    new_revision = int(revision) + 1
    con.execute(
        "UPDATE app_state SET revision=?, payload=?, updated_at=? WHERE id=1",
        (new_revision, json.dumps(state, ensure_ascii=False, separators=(",", ":")), now_iso()),
    )
    return new_revision


def mutate_state(mutator):
    with _WRITE_LOCK, db_connect() as con:
        con.execute("BEGIN IMMEDIATE")
        revision, state = load_state(con)
        result = mutator(state)
        new_revision = save_state(con, revision, state)
        con.commit()
        return new_revision, state, result


def token_hash(token):
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def issue_session(con, user_id):
    token = secrets.token_urlsafe(48)
    digest = token_hash(token)
    now = unix_now()
    con.execute(
        "INSERT INTO sessions(token_hash,user_id,created_at,expires_at,last_seen_at) VALUES(?,?,?,?,?)",
        (digest, user_id, now, now + SESSION_TTL_SECONDS, now),
    )
    return token


def authorization_token(authorization):
    raw = str(authorization or "").strip()
    if not raw.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = raw[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return token


def session_account(authorization):
    token = authorization_token(authorization)
    digest = token_hash(token)
    with db_connect() as con:
        row = con.execute(
            "SELECT user_id, expires_at FROM sessions WHERE token_hash=?",
            (digest,),
        ).fetchone()
        if not row or int(row["expires_at"]) <= unix_now():
            if row:
                con.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
                con.commit()
            raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
        revision, state = load_state(con)
        account = state.get("accounts", {}).get(row["user_id"])
        if not account or not account.get("active", True):
            raise HTTPException(status_code=401, detail="Account is disabled or no longer exists.")
        now = unix_now()
        con.execute(
            "UPDATE sessions SET last_seen_at=?, expires_at=? WHERE token_hash=?",
            (now, now + SESSION_TTL_SECONDS, digest),
        )
        con.commit()
        return token, digest, row["user_id"], account, revision, state


def require_admin(account):
    if not account or account.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Administrator access required.")


def sanitized_state(state, account):
    snap = copy.deepcopy(state)
    role = account.get("role", "STUDENT")
    uid = account.get("user_id")
    if role == "STUDENT":
        sid = account.get("student_id")
        snap["students"] = {sid: snap.get("students", {}).get(sid)} if sid and sid in snap.get("students", {}) else {}
        snap["teacher_invites"] = {}
        snap["accounts"] = {uid: public_account(account)}
        snap["auth_audit"] = []
        snap["audit_log"] = [x for x in snap.get("audit_log", []) if x.get("student_id") == sid]
        snap["notifications"] = [x for x in snap.get("notifications", []) if x.get("student_id") == sid]
    elif role == "TEACHER":
        snap["teacher_invites"] = {}
        snap["accounts"] = {uid: public_account(account)}
        snap["auth_audit"] = []
    else:
        snap["accounts"] = {k: public_account(v) for k, v in snap.get("accounts", {}).items()}
    snap["teacher_sessions"] = {}
    snap["auth_security"] = {}
    return snap


def response_bundle(state, revision, account, **extra):
    result = {
        "revision": revision,
        "context": session_context(account),
        "state": sanitized_state(state, account),
    }
    result.update(extra)
    return result


def new_student(state, name, age=0, skill_class="Unranked"):
    sid = "S" + datetime.now().strftime("%Y%m%d%H%M%S%f")
    state.setdefault("students", {})[sid] = {
        "id": sid,
        "name": str(name or "").strip(),
        "age": int(age or 0),
        "skill_class": str(skill_class or "Unranked").strip() or "Unranked",
        "active_tracks": ["Gameplay", "Decoration"],
        "attendance_skips": 0,
        "homework_skips": 0,
        "created_at": now_iso(),
        "legacy_import": None,
        "lesson_records": {},
    }
    state.setdefault("settings", {})["active_student_id"] = sid
    return sid


def base_account(state, username, password, display_name, role):
    normalized = normalize_username(username)
    _uid, existing = find_account_by_username(state, normalized)
    if existing is not None:
        raise ValueError("This username is already registered.")
    display = str(display_name or "").strip()
    if not display:
        raise ValueError("Display name is required.")
    uid = "U-" + uuid.uuid4().hex
    account = {
        "user_id": uid,
        "username": normalized,
        "display_name": display,
        "role": role,
        "password": hash_password(password),
        "active": True,
        "created_at": now_iso(),
        "created_timestamp": unix_now(),
        "last_login_at": None,
        "last_login_timestamp": None,
        "failed_login_count": 0,
        "student_id": None,
        "teacher_id": None,
        "authorized_phases": [],
        "recovery_code": None,
        "recovery_code_created_at": None,
        "recovery_failed_attempts": 0,
        "recovery_locked_until": 0,
        "security_question": None,
        "security_answer": None,
        "security_answer_failed_attempts": 0,
        "security_answer_locked_until": 0,
        "must_change_password": False,
    }
    recovery = issue_recovery_code(state, account, "RECOVERY_CODE_CREATED_WITH_ACCOUNT")
    state.setdefault("accounts", {})[uid] = account
    return account, recovery


def invite_suffix(seed):
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return "".join(INVITE_ALPHABET[b % len(INVITE_ALPHABET)] for b in digest[:4])


def generate_invite(state, phases, teacher_label=None):
    phases = normalize_phases(phases)
    if not phases:
        raise ValueError("Select at least one authorized phase.")
    invites = state.setdefault("teacher_invites", {})
    for _ in range(10000):
        seed = f"{uuid.uuid4()}|{now_iso()}|{uuid.uuid4().int}|{len(invites)}"
        code = INVITE_PREFIX + invite_suffix(seed)
        if code not in invites:
            invites[code] = {
                "creation_timestamp": unix_now(),
                "creation_iso": now_iso(),
                "is_activated": False,
                "is_enabled": True,
                "disabled_timestamp": None,
                "disabled_iso": None,
                "activation_timestamp": None,
                "activation_iso": None,
                "authorized_phases": phases,
                "teacher_label": teacher_label or "Teacher",
                "session_token_hash": None,
                "teacher_id": None,
            }
            return code
    raise RuntimeError("Unable to allocate a unique invitation code.")


def activate_teacher_invite(state, code):
    normalized = str(code or "").strip().upper()
    rec = state.setdefault("teacher_invites", {}).get(normalized)
    if rec is None:
        raise ValueError("Invite code is invalid.")
    if not rec.get("is_enabled", True):
        raise ValueError("Invite code has been disabled by an administrator.")
    if rec.get("is_activated"):
        raise ValueError("Invite code has already been used.")
    teacher_id = "T-" + uuid.uuid4().hex
    rec.update({
        "is_activated": True,
        "activation_timestamp": unix_now(),
        "activation_iso": now_iso(),
        "teacher_id": teacher_id,
    })
    return teacher_id, normalize_phases(rec.get("authorized_phases", []))


def _get_path(root, path):
    cur = root
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return False, None
        cur = cur[key]
    return True, cur


def _set_path(root, path, value):
    if not path:
        raise ValueError("Root replacement is not allowed")
    cur = root
    for key in path[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[path[-1]] = copy.deepcopy(value)


def _delete_path(root, path):
    if not path:
        raise ValueError("Root deletion is not allowed")
    cur = root
    for key in path[:-1]:
        if not isinstance(cur, dict) or key not in cur:
            return
        cur = cur[key]
    if isinstance(cur, dict):
        cur.pop(path[-1], None)


def _append_only(old, new):
    return isinstance(old, list) and isinstance(new, list) and len(new) >= len(old) and new[:len(old)] == old


def validate_patch_op(account, state, op):
    path = [str(x) for x in op.get("path") or []]
    if not path:
        raise HTTPException(status_code=403, detail="Root state replacement is forbidden.")
    root = path[0]
    role = account.get("role", "STUDENT")
    value = op.get("value")
    delete = bool(op.get("delete", False))

    if root in {"accounts", "auth_security", "auth_audit", "teacher_invites", "teacher_sessions", "meta"}:
        raise HTTPException(status_code=403, detail=f"Direct writes to {root} are forbidden.")

    if role == "ADMIN":
        return

    if root in {"notifications", "audit_log"}:
        old = op.get("old") if op.get("old_exists") else []
        if delete or not _append_only(old, value):
            raise HTTPException(status_code=403, detail=f"{root} is append-only.")
        return

    if root == "settings":
        if path == ["settings", "language"]:
            return
        if role == "TEACHER" and 7 in normalize_phases(account.get("authorized_phases")) and path[:2] == ["settings", "moderator_requests"]:
            return
        raise HTTPException(status_code=403, detail="This setting cannot be changed by this account.")

    if root != "students" or len(path) < 2:
        raise HTTPException(status_code=403, detail="This data cannot be changed by this account.")

    sid = path[1]
    if role == "STUDENT":
        if sid != account.get("student_id"):
            raise HTTPException(status_code=403, detail="Students can edit only their own profile data.")
        if len(path) < 5 or path[2] != "lesson_records":
            raise HTTPException(status_code=403, detail="Students can edit only their own submission links.")
        lesson_id = path[3]
        leaf = path[4]
        if lesson_id not in LESSON_PHASE:
            raise HTTPException(status_code=403, detail="Unknown lesson.")
        if leaf in {"level_id_link", "showcase_pipeline_url"}:
            return
        # Allow the harmless record scaffold created by setdefault() when a link
        # is attached before any grade exists.
        if leaf == "grades" and value == [] and not delete:
            return
        if leaf == "status" and value == "Not Started" and not delete:
            return
        raise HTTPException(status_code=403, detail="Students cannot change grades or lesson status.")

    if role == "TEACHER":
        if len(path) >= 4 and path[2] == "lesson_records":
            lesson_id = path[3]
            phase = LESSON_PHASE.get(lesson_id)
            if phase in normalize_phases(account.get("authorized_phases")):
                return
        if len(path) == 3 and path[2] == "homework_skips":
            return
        if len(path) == 3 and path[2] == "graduation_exam_score" and 7 in normalize_phases(account.get("authorized_phases")):
            return
        raise HTTPException(status_code=403, detail="Teacher write is outside authorized phases.")

    raise HTTPException(status_code=403, detail="Write access denied.")


app = FastAPI(title="ACA Platform Server", version=SERVER_VERSION)


@app.get("/")
def root_status():
    revision, _state = load_state()
    return {
        "ok": True,
        "service": "ACA Platform Server",
        "version": SERVER_VERSION,
        "revision": revision,
        "storage": "persistent-volume" if RAILWAY_VOLUME_ROOT else "local",
    }


@app.get("/health")
@app.get(f"{API_PREFIX}/health")
def health():
    revision, _state = load_state()
    return {"ok": True, "service": "ACA Platform Server", "version": SERVER_VERSION, "revision": revision}


@app.get(f"{API_PREFIX}/public/status")
def public_status():
    revision, state = load_state()
    return {
        "ok": True,
        "revision": revision,
        "has_admin": any(a.get("role") == "ADMIN" and a.get("active", True) for a in state.get("accounts", {}).values()),
    }


@app.post(f"{API_PREFIX}/auth/login")
def login(payload: dict = Body(...)):
    username = payload.get("username")
    password = payload.get("password")
    try:
        normalized = normalize_username(username)
    except ValueError:
        normalized = str(username or "").strip().casefold()

    with _WRITE_LOCK, db_connect() as con:
        con.execute("BEGIN IMMEDIATE")
        revision, state = load_state(con)
        uid, account = find_account_by_username(state, normalized)
        if account is None or not account.get("active", True) or not verify_password(password, account.get("password")):
            if account is not None:
                account["failed_login_count"] = int(account.get("failed_login_count", 0)) + 1
            audit_auth(state, uid, "LOGIN_FAILED", {"username": normalized})
            revision = save_state(con, revision, state)
            con.commit()
            raise HTTPException(status_code=401, detail="Invalid username or password.")
        account["failed_login_count"] = 0
        account["last_login_at"] = now_iso()
        account["last_login_timestamp"] = unix_now()
        recovery_code_once = None
        if not isinstance(account.get("recovery_code"), dict):
            recovery_code_once = issue_recovery_code(state, account, "RECOVERY_CODE_INITIALIZED")
        audit_auth(state, uid, "LOGIN_SUCCESS", {"username": normalized, "role": account.get("role")})
        revision = save_state(con, revision, state)
        token = issue_session(con, uid)
        con.commit()
        return response_bundle(state, revision, account, token=token, recovery_code_once=recovery_code_once)


@app.get(f"{API_PREFIX}/auth/session")
def resume_session(authorization: str | None = Header(default=None)):
    _token, _digest, _uid, account, revision, state = session_account(authorization)
    return response_bundle(state, revision, account)


@app.post(f"{API_PREFIX}/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    token = authorization_token(authorization)
    with db_connect() as con:
        con.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))
        con.commit()
    return {"ok": True}


@app.get(f"{API_PREFIX}/auth/security-question")
def security_question(username: str = Query(...)):
    try:
        normalized = normalize_username(username)
    except Exception:
        return {"question": None}
    _revision, state = load_state()
    _uid, account = find_account_by_username(state, normalized)
    question = None
    if account and account.get("active", True):
        question = str(account.get("security_question") or "").strip() or None
    return {"question": question}


@app.post(f"{API_PREFIX}/auth/recover/code")
def recover_code(payload: dict = Body(...)):
    username = payload.get("username")
    code = payload.get("recovery_code")
    new_password = payload.get("new_password")
    generic = "Recovery failed. Check the username and recovery code, or try again later."

    def mutation(state):
        try:
            normalized = normalize_username(username)
        except Exception:
            normalized = str(username or "").strip().casefold()
        uid, account = find_account_by_username(state, normalized)
        now = unix_now()
        if account is None or not account.get("active", True):
            return {"error": generic}
        if int(account.get("recovery_locked_until", 0) or 0) > now:
            return {"error": generic}
        if not verify_recovery_code(code, account.get("recovery_code")):
            attempts = int(account.get("recovery_failed_attempts", 0)) + 1
            account["recovery_failed_attempts"] = attempts
            if attempts >= 5:
                account["recovery_locked_until"] = now + 15 * 60
                account["recovery_failed_attempts"] = 0
            audit_auth(state, uid, "PASSWORD_RECOVERY_FAILED", {})
            return {"error": generic}
        account["password"] = hash_password(new_password)
        account["must_change_password"] = False
        account["failed_login_count"] = 0
        account["password_changed_at"] = now_iso()
        new_code = issue_recovery_code(state, account, "RECOVERY_CODE_ROTATED_AFTER_RECOVERY")
        audit_auth(state, uid, "PASSWORD_RECOVERED_WITH_CODE", {})
        return {"user_id": uid, "username": account.get("username"), "recovery_code_once": new_code}

    revision, state, result = mutate_state(mutation)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {**result, "revision": revision}


@app.post(f"{API_PREFIX}/auth/recover/question")
def recover_question(payload: dict = Body(...)):
    username = payload.get("username")
    answer = payload.get("answer")
    new_password = payload.get("new_password")
    generic = "Recovery failed. Check the username and security answer, or try again later."

    def mutation(state):
        try:
            normalized = normalize_username(username)
        except Exception:
            normalized = str(username or "").strip().casefold()
        uid, account = find_account_by_username(state, normalized)
        now = unix_now()
        if account is None or not account.get("active", True):
            return {"error": generic}
        if not account.get("security_question") or not isinstance(account.get("security_answer"), dict):
            return {"error": generic}
        if int(account.get("security_answer_locked_until", 0) or 0) > now:
            return {"error": generic}
        if not verify_security_answer(answer, account.get("security_answer")):
            attempts = int(account.get("security_answer_failed_attempts", 0)) + 1
            account["security_answer_failed_attempts"] = attempts
            if attempts >= 5:
                account["security_answer_locked_until"] = now + 15 * 60
                account["security_answer_failed_attempts"] = 0
            audit_auth(state, uid, "SECURITY_QUESTION_RECOVERY_FAILED", {})
            return {"error": generic}
        account["password"] = hash_password(new_password)
        account["must_change_password"] = False
        account["failed_login_count"] = 0
        account["security_answer_failed_attempts"] = 0
        account["security_answer_locked_until"] = 0
        account["password_changed_at"] = now_iso()
        new_code = issue_recovery_code(state, account, "RECOVERY_CODE_ROTATED_AFTER_SECURITY_QUESTION")
        audit_auth(state, uid, "PASSWORD_RECOVERED_WITH_SECURITY_QUESTION", {})
        return {"user_id": uid, "username": account.get("username"), "recovery_code_once": new_code}

    revision, state, result = mutate_state(mutation)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {**result, "revision": revision}


@app.post(f"{API_PREFIX}/auth/register/student")
def register_student(payload: dict = Body(...)):
    def mutation(state):
        try:
            age = int(payload.get("age") or 0)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Age must be a whole number.")
        if age < 0 or age > 120:
            raise HTTPException(status_code=400, detail="Age is outside the supported range.")
        try:
            account, recovery = base_account(state, payload.get("username"), payload.get("password"), payload.get("display_name"), "STUDENT")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        sid = new_student(state, account["display_name"], age, payload.get("skill_class") or "Unranked")
        account["student_id"] = sid
        audit_auth(state, account["user_id"], "STUDENT_REGISTERED", {"student_id": sid, "username": account["username"]})
        result = public_account(account)
        result["recovery_code_once"] = recovery
        return result

    revision, state, result = mutate_state(mutation)
    return {"account": result, "revision": revision}


@app.post(f"{API_PREFIX}/auth/register/teacher")
def register_teacher(payload: dict = Body(...)):
    def mutation(state):
        try:
            account, recovery = base_account(state, payload.get("username"), payload.get("password"), payload.get("display_name"), "TEACHER")
            teacher_id, phases = activate_teacher_invite(state, payload.get("invite_code"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        account["teacher_id"] = teacher_id
        account["authorized_phases"] = phases
        account["invite_code"] = str(payload.get("invite_code") or "").strip().upper()
        audit_auth(state, account["user_id"], "TEACHER_REGISTERED", {"teacher_id": teacher_id, "authorized_phases": phases})
        result = public_account(account)
        result["recovery_code_once"] = recovery
        return result

    revision, state, result = mutate_state(mutation)
    return {"account": result, "revision": revision}


@app.post(f"{API_PREFIX}/auth/register/admin")
def register_admin(payload: dict = Body(...)):
    def mutation(state):
        if any(a.get("role") == "ADMIN" and a.get("active", True) for a in state.get("accounts", {}).values()):
            raise HTTPException(status_code=403, detail="Administrator registration is already closed for this server.")
        if payload.get("bootstrap") is not True:
            raise HTTPException(status_code=403, detail="Administrator accounts can only be created through Principal Setup.")
        try:
            account, recovery = base_account(state, payload.get("username"), payload.get("password"), payload.get("display_name"), "ADMIN")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        account["authorized_phases"] = list(VALID_PHASES)
        result = public_account(account)
        result["recovery_code_once"] = recovery
        return result

    revision, state, result = mutate_state(mutation)
    return {"account": result, "revision": revision}


@app.post(f"{API_PREFIX}/auth/change-password")
def change_password(payload: dict = Body(...), authorization: str | None = Header(default=None)):
    _token, _digest, uid, account, _revision, _state = session_account(authorization)

    def mutation(state):
        current = state["accounts"].get(uid)
        if not current or not current.get("active", True):
            raise HTTPException(status_code=404, detail="Account not found or disabled.")
        if not verify_password(payload.get("current_password"), current.get("password")):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        if verify_password(payload.get("new_password"), current.get("password")):
            raise HTTPException(status_code=400, detail="New password must be different from the current password.")
        current["password"] = hash_password(payload.get("new_password"))
        current["must_change_password"] = False
        current["password_changed_at"] = now_iso()
        recovery = issue_recovery_code(state, current, "RECOVERY_CODE_ROTATED_AFTER_PASSWORD_CHANGE")
        audit_auth(state, uid, "PASSWORD_CHANGED", {})
        return recovery

    revision, state, recovery = mutate_state(mutation)
    account = state["accounts"][uid]
    return response_bundle(state, revision, account, recovery_code_once=recovery)


@app.post(f"{API_PREFIX}/auth/complete-forced-password-change")
def complete_forced(payload: dict = Body(...), authorization: str | None = Header(default=None)):
    _token, _digest, uid, _account, _revision, _state = session_account(authorization)

    def mutation(state):
        current = state["accounts"].get(uid)
        if not current or not current.get("active", True):
            raise HTTPException(status_code=404, detail="Account not found or disabled.")
        if not current.get("must_change_password", False):
            raise HTTPException(status_code=400, detail="This account does not require a forced password change.")
        if not verify_password(payload.get("current_password"), current.get("password")):
            raise HTTPException(status_code=400, detail="Temporary password is incorrect.")
        current["password"] = hash_password(payload.get("new_password"))
        current["must_change_password"] = False
        current["password_changed_at"] = now_iso()
        recovery = issue_recovery_code(state, current, "RECOVERY_CODE_ROTATED_AFTER_FORCED_CHANGE")
        audit_auth(state, uid, "FORCED_PASSWORD_CHANGE_COMPLETED", {})
        return recovery

    revision, state, recovery = mutate_state(mutation)
    account = state["accounts"][uid]
    result = response_bundle(state, revision, account, recovery_code_once=recovery)
    result["account"] = public_account(account)
    return result


@app.post(f"{API_PREFIX}/auth/regenerate-recovery-code")
def regenerate_recovery(payload: dict = Body(...), authorization: str | None = Header(default=None)):
    _token, _digest, uid, _account, _revision, _state = session_account(authorization)

    def mutation(state):
        current = state["accounts"].get(uid)
        if not current or not current.get("active", True):
            raise HTTPException(status_code=404, detail="Account not found or disabled.")
        if not verify_password(payload.get("current_password"), current.get("password")):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        return issue_recovery_code(state, current, "RECOVERY_CODE_REGENERATED")

    revision, state, recovery = mutate_state(mutation)
    account = state["accounts"][uid]
    return response_bundle(state, revision, account, recovery_code_once=recovery)


@app.get(f"{API_PREFIX}/auth/context")
def auth_context(authorization: str | None = Header(default=None)):
    _token, _digest, _uid, account, revision, state = session_account(authorization)
    return response_bundle(state, revision, account)


@app.get(f"{API_PREFIX}/state")
def get_state(revision: int | None = Query(default=None), authorization: str | None = Header(default=None)):
    _token, _digest, _uid, account, current_revision, state = session_account(authorization)
    if revision is not None and int(revision) == current_revision:
        return {"changed": False, "revision": current_revision}
    return {"changed": True, **response_bundle(state, current_revision, account)}


@app.post(f"{API_PREFIX}/state/patch")
def patch_state(payload: dict = Body(...), authorization: str | None = Header(default=None)):
    _token, _digest, uid, _account, _revision, _state = session_account(authorization)
    ops = payload.get("ops") or []
    base_revision = int(payload.get("base_revision") or 0)
    if not isinstance(ops, list) or len(ops) > 5000:
        raise HTTPException(status_code=400, detail="Invalid state patch.")

    with _WRITE_LOCK, db_connect() as con:
        con.execute("BEGIN IMMEDIATE")
        current_revision, state = load_state(con)
        account = state.get("accounts", {}).get(uid)
        if not account or not account.get("active", True):
            raise HTTPException(status_code=401, detail="Account is disabled or no longer exists.")
        for op in ops:
            if not isinstance(op, dict):
                raise HTTPException(status_code=400, detail="Invalid patch operation.")
            path = [str(x) for x in op.get("path") or []]
            exists, current = _get_path(state, path)
            old_exists = bool(op.get("old_exists", False))
            old = op.get("old")
            append_filtered = (account.get("role") != "ADMIN" and path in (["notifications"], ["audit_log"]))
            # Revision drift is safe only when the exact touched value still equals
            # the value the client originally edited. Filtered append-only logs are
            # merged specially below because the server can contain other users' rows.
            if current_revision != base_revision and not append_filtered:
                if exists != old_exists or (old_exists and current != old):
                    con.rollback()
                    raise HTTPException(status_code=409, detail="Data changed on the server. Refresh and retry this edit.")
            validate_patch_op(account, state, op)
        for op in ops:
            path = [str(x) for x in op.get("path") or []]
            if account.get("role") != "ADMIN" and path in (["notifications"], ["audit_log"]):
                old = op.get("old") if op.get("old_exists") else []
                new = op.get("value") or []
                suffix = new[len(old):] if isinstance(old, list) and isinstance(new, list) else []
                state.setdefault(path[0], []).extend(copy.deepcopy(suffix))
            elif op.get("delete"):
                _delete_path(state, path)
            else:
                _set_path(state, path, op.get("value"))
        audit_auth(state, uid, "STATE_PATCH_APPLIED", {"operations": len(ops)})
        new_revision = save_state(con, current_revision, state)
        con.commit()
        return response_bundle(state, new_revision, state["accounts"][uid])


@app.get(f"{API_PREFIX}/admin/accounts")
def admin_accounts(authorization: str | None = Header(default=None)):
    _token, _digest, _uid, account, revision, state = session_account(authorization)
    require_admin(account)
    return {"revision": revision, "accounts": [public_account(x) for x in state.get("accounts", {}).values()]}


@app.post(f"{API_PREFIX}/admin/accounts/{{user_id}}/active")
def admin_account_active(user_id: str, payload: dict = Body(...), authorization: str | None = Header(default=None)):
    _token, _digest, actor_uid, actor, _revision, _state = session_account(authorization)
    require_admin(actor)

    def mutation(state):
        target = state.get("accounts", {}).get(user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Account not found.")
        active = bool(payload.get("active"))
        if not active and target.get("role") == "ADMIN":
            active_admins = [a for a in state["accounts"].values() if a.get("role") == "ADMIN" and a.get("active", True)]
            if target.get("user_id") == actor_uid:
                raise HTTPException(status_code=400, detail="You cannot disable the administrator account currently in use.")
            if target.get("active", True) and len(active_admins) <= 1:
                raise HTTPException(status_code=400, detail="The last active administrator cannot be disabled.")
        target["active"] = active
        audit_auth(state, user_id, "ACCOUNT_ENABLED" if active else "ACCOUNT_DISABLED", {"by": actor_uid})
        return public_account(target)

    revision, state, result = mutate_state(mutation)
    return response_bundle(state, revision, state["accounts"][actor_uid], account=result)


@app.post(f"{API_PREFIX}/admin/accounts/{{user_id}}/role")
def admin_account_role(user_id: str, payload: dict = Body(...), authorization: str | None = Header(default=None)):
    _token, _digest, actor_uid, actor, _revision, _state = session_account(authorization)
    require_admin(actor)

    def mutation(state):
        target = state.get("accounts", {}).get(user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Account not found.")
        if user_id == actor_uid:
            raise HTTPException(status_code=400, detail="Change your own administrator role from another administrator account.")
        role = str(payload.get("role") or "").strip().upper()
        if role not in {"ADMIN", "TEACHER", "STUDENT"}:
            raise HTTPException(status_code=400, detail="Role must be ADMIN, TEACHER, or STUDENT.")
        old_role = target.get("role", "STUDENT")
        if old_role == "ADMIN" and role != "ADMIN" and target.get("active", True):
            active_admins = [a for a in state["accounts"].values() if a.get("role") == "ADMIN" and a.get("active", True)]
            if len(active_admins) <= 1:
                raise HTTPException(status_code=400, detail="The last active administrator cannot be demoted.")
        if role == "ADMIN":
            target["authorized_phases"] = list(VALID_PHASES)
        elif role == "TEACHER":
            phases = normalize_phases(payload.get("authorized_phases") or target.get("authorized_phases") or [7])
            target["authorized_phases"] = phases
            if not target.get("teacher_id"):
                target["teacher_id"] = "T-" + uuid.uuid4().hex
        else:
            target["authorized_phases"] = []
            if not target.get("student_id") or target.get("student_id") not in state.get("students", {}):
                target["student_id"] = new_student(state, target.get("display_name") or target.get("username") or "Student", 0, "Unranked")
        target["role"] = role
        target["role_changed_at"] = now_iso()
        audit_auth(state, user_id, "ACCOUNT_ROLE_CHANGED", {"by": actor_uid, "from": old_role, "to": role, "authorized_phases": target.get("authorized_phases", [])})
        return public_account(target)

    revision, state, result = mutate_state(mutation)
    return response_bundle(state, revision, state["accounts"][actor_uid], account=result)


@app.post(f"{API_PREFIX}/admin/accounts/{{user_id}}/reset-password")
def admin_reset_password(user_id: str, payload: dict = Body(...), authorization: str | None = Header(default=None)):
    _token, _digest, actor_uid, actor, _revision, _state = session_account(authorization)
    require_admin(actor)

    def mutation(state):
        target = state.get("accounts", {}).get(user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Account not found.")
        try:
            target["password"] = hash_password(payload.get("temporary_password"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        target["recovery_code"] = None
        target["recovery_code_created_at"] = None
        target["recovery_failed_attempts"] = 0
        target["recovery_locked_until"] = 0
        target["must_change_password"] = bool(payload.get("force_change", True))
        target["password_reset_at"] = now_iso()
        target["failed_login_count"] = 0
        audit_auth(state, user_id, "PASSWORD_RESET_BY_ADMIN", {"by": actor_uid, "force_change": target["must_change_password"]})
        return public_account(target)

    revision, state, result = mutate_state(mutation)
    return response_bundle(state, revision, state["accounts"][actor_uid], account=result)


@app.post(f"{API_PREFIX}/admin/invites")
def admin_generate_invite(payload: dict = Body(...), authorization: str | None = Header(default=None)):
    _token, _digest, actor_uid, actor, _revision, _state = session_account(authorization)
    require_admin(actor)

    def mutation(state):
        try:
            return generate_invite(state, payload.get("authorized_phases"), payload.get("teacher_label"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    revision, state, code = mutate_state(mutation)
    return response_bundle(state, revision, state["accounts"][actor_uid], code=code)


@app.post(f"{API_PREFIX}/admin/invites/{{invite_code}}/enabled")
def admin_invite_enabled(invite_code: str, payload: dict = Body(...), authorization: str | None = Header(default=None)):
    _token, _digest, actor_uid, actor, _revision, _state = session_account(authorization)
    require_admin(actor)

    def mutation(state):
        code = str(invite_code or "").strip().upper()
        rec = state.get("teacher_invites", {}).get(code)
        if rec is None:
            raise HTTPException(status_code=404, detail="Invite code not found.")
        enabled = bool(payload.get("enabled"))
        rec["is_enabled"] = enabled
        if enabled:
            rec["disabled_timestamp"] = None
            rec["disabled_iso"] = None
        else:
            rec["disabled_timestamp"] = unix_now()
            rec["disabled_iso"] = now_iso()
        return dict(rec)

    revision, state, record = mutate_state(mutation)
    return response_bundle(state, revision, state["accounts"][actor_uid], record=record)


@app.post(f"{API_PREFIX}/admin/invites/{{invite_code}}/reissue")
def admin_invite_reissue(invite_code: str, authorization: str | None = Header(default=None)):
    _token, _digest, actor_uid, actor, _revision, _state = session_account(authorization)
    require_admin(actor)

    def mutation(state):
        code = str(invite_code or "").strip().upper()
        rec = state.get("teacher_invites", {}).get(code)
        if rec is None:
            raise HTTPException(status_code=404, detail="Invite code not found.")
        if not rec.get("is_activated"):
            rec["is_enabled"] = False
            rec["disabled_timestamp"] = unix_now()
            rec["disabled_iso"] = now_iso()
        new_code = generate_invite(state, rec.get("authorized_phases") or [7], rec.get("teacher_label") or "Teacher")
        state["teacher_invites"][new_code]["reissued_from"] = code
        return new_code

    revision, state, new_code = mutate_state(mutation)
    return response_bundle(state, revision, state["accounts"][actor_uid], code=new_code)


@app.post(f"{API_PREFIX}/admin/backup")
def admin_backup(authorization: str | None = Header(default=None)):
    _token, _digest, _uid, account, revision, state = session_account(authorization)
    require_admin(account)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, "aca_server_state_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return {"ok": True, "revision": revision, "path": os.path.abspath(path)}


def main():
    global DB_PATH, BACKUP_DIR
    parser = argparse.ArgumentParser(description="ACA Platform central server")
    cloud_host = "0.0.0.0" if (os.environ.get("PORT") or os.environ.get("RAILWAY_ENVIRONMENT")) else "127.0.0.1"
    parser.add_argument("--host", default=os.environ.get("ACA_SERVER_HOST", cloud_host))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT") or os.environ.get("ACA_SERVER_PORT", "8787")))
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--backup-dir", default=BACKUP_DIR)
    parser.add_argument("--import-json", default=None, help="Import an existing aca_system_db.json before serving")
    parser.add_argument("--force-import", action="store_true", help="Replace existing server state from --import-json")
    args = parser.parse_args()
    DB_PATH = os.path.abspath(os.path.expanduser(args.db))
    BACKUP_DIR = os.path.abspath(os.path.expanduser(args.backup_dir))

    # First Railway boot: if a legacy JSON snapshot was uploaded to the persistent
    # volume before the SQLite file exists, import it automatically exactly once.
    import_json = args.import_json
    if not import_json and not os.path.exists(DB_PATH) and RAILWAY_VOLUME_ROOT:
        candidate = os.path.join(RAILWAY_VOLUME_ROOT, "aca_system_db.json")
        if os.path.exists(candidate):
            import_json = candidate

    init_db(import_json, args.force_import)
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


# Initialize when imported by uvicorn/gunicorn using environment-configured paths.
if __name__ != "__main__":
    init_db()

if __name__ == "__main__":
    main()
