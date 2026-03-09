from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from backend.src.storage.database import Database


class DownloadTokenRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_token(
        self,
        license_id: int,
        hwid: str,
        app: str,
        channel: str,
        version: str,
        ttl_minutes: int = 5,
    ) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        expires_at = (now + timedelta(minutes=ttl_minutes)).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO managed_download_tokens (
                    download_token,
                    license_id,
                    hwid,
                    app,
                    channel,
                    version,
                    expires_at,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (token, license_id, hwid, app or "wishlist", channel, version, expires_at, now.isoformat()),
            )
            connection.commit()
        return token

    def consume_token(self, token: str) -> Optional[dict]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM managed_download_tokens WHERE download_token = ?",
                (token,),
            ).fetchone()
            if not row:
                return None
            connection.execute("DELETE FROM managed_download_tokens WHERE download_token = ?", (token,))
            connection.commit()

        payload = dict(row)
        if payload["expires_at"] < datetime.utcnow().isoformat():
            return None
        return payload
