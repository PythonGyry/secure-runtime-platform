from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from client.src.security.dpapi import is_available, protect_b64, unprotect_b64
from shared.crypto.runtime_crypto import decrypt_bytes, derive_fernet_key, encrypt_bytes

_DPAPI_PREFIX = "dpapi:"


class BootstrapStateStore:
    def __init__(self, path: Path, hwid: str) -> None:
        self.path = path
        self.key = derive_fernet_key("bootstrap-state", hwid)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS bootstrap_state (
                    state_key TEXT PRIMARY KEY,
                    encrypted_value TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _load(self, state_key: str) -> Optional[str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT encrypted_value FROM bootstrap_state WHERE state_key = ?",
                (state_key,),
            ).fetchone()
        if not row:
            return None
        raw = row[0]
        try:
            if raw.startswith(_DPAPI_PREFIX):
                if not is_available():
                    return None
                blob = unprotect_b64(raw[len(_DPAPI_PREFIX) :])
                return decrypt_bytes(blob, key=self.key).decode("utf-8")
            return decrypt_bytes(raw.encode("utf-8"), key=self.key).decode("utf-8")
        except Exception:
            return None

    def _save(self, state_key: str, value: str) -> None:
        fernet_blob = encrypt_bytes(value.encode("utf-8"), key=self.key)
        if is_available():
            stored = _DPAPI_PREFIX + protect_b64(fernet_blob)
        else:
            stored = fernet_blob.decode("utf-8")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO bootstrap_state (state_key, encrypted_value)
                VALUES (?, ?)
                ON CONFLICT(state_key) DO UPDATE SET encrypted_value = excluded.encrypted_value
                """,
                (state_key, stored),
            )
            connection.commit()

    def _delete(self, state_key: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM bootstrap_state WHERE state_key = ?", (state_key,))
            connection.commit()

    def load_license_key(self) -> Optional[str]:
        return self._load("license_key")

    def save_license_key(self, license_key: str) -> None:
        self._save("license_key", license_key)

    def load_server_url(self, default: str) -> str:
        return self._load("server_url") or default

    def save_server_url(self, server_url: str) -> None:
        self._save("server_url", server_url)

    def load_channel(self, default: str) -> str:
        return self._load("channel") or default

    def save_channel(self, channel: str) -> None:
        self._save("channel", channel)

    def clear(self) -> None:
        self._delete("license_key")
