from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from backend.src.storage.database import Database

_PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}:{key.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    if ":" in stored:
        try:
            salt_hex, key_hex = stored.split(":", 1)
            salt = bytes.fromhex(salt_hex)
            key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
            return secrets.compare_digest(key.hex(), key_hex)
        except (ValueError, TypeError):
            return False
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return secrets.compare_digest(legacy_hash, stored)


class AdminRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure_bootstrap_admin(self, bootstrap_file: Path) -> dict:
        user = self.get_user("admin")
        if user:
            return {"username": "admin", "bootstrap_password": None}

        password = secrets.token_urlsafe(12)
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO admin_users (username, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                ("admin", hash_password(password), now, now),
            )
            connection.commit()

        bootstrap_file.write_text(
            json.dumps(
                {
                    "username": "admin",
                    "password": password,
                    "created_at": now,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        try:
            bootstrap_file.chmod(0o600)
        except OSError:
            pass
        return {"username": "admin", "bootstrap_password": password}

    def create_or_reset_admin(self, password: str, bootstrap_file: Path) -> dict:
        """Create or reset admin user with given password. Saves to bootstrap file."""
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO admin_users (username, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash, updated_at = excluded.updated_at
                """,
                ("admin", hash_password(password), now, now),
            )
            connection.commit()

        bootstrap_file.write_text(
            json.dumps(
                {
                    "username": "admin",
                    "password": password,
                    "created_at": now,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        try:
            bootstrap_file.chmod(0o600)
        except OSError:
            pass
        return {"username": "admin", "password": password}

    def get_user(self, username: str) -> Optional[dict]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM admin_users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

    def migrate_password_if_legacy(self, username: str, password: str) -> None:
        user = self.get_user(username)
        if not user or ":" in user["password_hash"]:
            return
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE admin_users SET password_hash = ?, updated_at = ? WHERE username = ?",
                (hash_password(password), datetime.utcnow().isoformat(), username),
            )
            connection.commit()

    def create_session(self, username: str, ttl_hours: int = 12) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        expires_at = (now + timedelta(hours=ttl_hours)).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO admin_sessions (session_token, username, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, username, expires_at, now.isoformat()),
            )
            connection.commit()
        return token

    def get_session(self, session_token: str) -> Optional[dict]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM admin_sessions WHERE session_token = ?",
                (session_token,),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        if payload["expires_at"] < datetime.utcnow().isoformat():
            self.delete_session(session_token)
            return None
        return payload

    def delete_session(self, session_token: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM admin_sessions WHERE session_token = ?", (session_token,))
            connection.commit()

    def record_audit(self, username: str, action: str, payload: dict) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO admin_audit_log (username, action, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, action, json.dumps(payload, ensure_ascii=False), datetime.utcnow().isoformat()),
            )
            connection.commit()

    def list_audit_log(self, limit: int = 100) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM admin_audit_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_config(self, key: str, default: str | None = None) -> str | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT config_value FROM server_config WHERE config_key = ?",
                (key,),
            ).fetchone()
        if not row:
            return default
        return row["config_value"]

    def set_config(self, key: str, value: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO server_config (config_key, config_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(config_key) DO UPDATE SET config_value = excluded.config_value, updated_at = excluded.updated_at
                """,
                (key, value, datetime.utcnow().isoformat()),
            )
            connection.commit()
