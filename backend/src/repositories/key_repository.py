from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.src.storage.database import Database
from shared.crypto.runtime_crypto import generate_keypair_b64


class KeyRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure_default_key(self, keypair_file: Path) -> dict:
        active_key = self.get_active_key()
        if active_key:
            self._sync_trusted_key_ids()
            return active_key

        if keypair_file.exists():
            payload = json.loads(keypair_file.read_text(encoding="utf-8"))
            key_record = self.create_key(
                private_key_b64=payload["private_key_b64"],
                public_key_b64=payload["public_key_b64"],
                status="active",
            )
            self._sync_trusted_key_ids()
            return key_record

        private_key_b64, public_key_b64 = generate_keypair_b64()
        key_record = self.create_key(
            private_key_b64=private_key_b64,
            public_key_b64=public_key_b64,
            status="active",
        )
        keypair_file.write_text(
            json.dumps(
                {
                    "private_key_b64": private_key_b64,
                    "public_key_b64": public_key_b64,
                    "key_id": key_record["key_id"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self._sync_trusted_key_ids()
        return key_record

    def create_key(self, *, private_key_b64: str, public_key_b64: str, status: str = "trusted") -> dict:
        key_id = secrets.token_hex(8)
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO signing_keys (key_id, private_key_b64, public_key_b64, status, created_at, rotated_at, retired_at)
                VALUES (?, ?, ?, ?, ?, NULL, NULL)
                """,
                (key_id, private_key_b64, public_key_b64, status, now),
            )
            connection.commit()
        return self.get_key(key_id) or {}

    def get_key(self, key_id: str) -> Optional[dict]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM signing_keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_active_key(self) -> Optional[dict]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM signing_keys WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def list_keys(self) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM signing_keys ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def activate_key(self, key_id: str) -> Optional[dict]:
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE signing_keys SET status = 'trusted', rotated_at = COALESCE(rotated_at, ?) WHERE status = 'active'",
                (now,),
            )
            connection.execute(
                "UPDATE signing_keys SET status = 'active', rotated_at = ? WHERE key_id = ?",
                (now, key_id),
            )
            connection.commit()
        self._sync_trusted_key_ids()
        return self.get_key(key_id)

    def retire_key(self, key_id: str) -> Optional[dict]:
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE signing_keys SET status = 'retired', retired_at = ? WHERE key_id = ?",
                (now, key_id),
            )
            connection.commit()
        self._sync_trusted_key_ids()
        return self.get_key(key_id)

    def get_trusted_public_keys(self) -> dict[str, str]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT key_id, public_key_b64 FROM signing_keys WHERE status IN ('active', 'trusted')"
            ).fetchall()
        return {row["key_id"]: row["public_key_b64"] for row in rows}

    def _sync_trusted_key_ids(self) -> None:
        trusted_ids = sorted(self.get_trusted_public_keys().keys())
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO server_config (config_key, config_value, updated_at)
                VALUES ('trusted_key_ids', ?, ?)
                ON CONFLICT(config_key) DO UPDATE SET config_value = excluded.config_value, updated_at = excluded.updated_at
                """,
                (json.dumps(trusted_ids), datetime.utcnow().isoformat()),
            )
            connection.commit()
