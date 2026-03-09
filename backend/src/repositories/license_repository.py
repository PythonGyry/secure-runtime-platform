from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Iterable, Optional

from backend.src.storage.database import Database


def hash_license_key(license_key: str) -> str:
    return hashlib.sha256(license_key.encode("utf-8")).hexdigest()


class LicenseRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure_license(self, license_key: str, display_name: str = "default") -> None:
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO licenses (license_key_hash, display_name, is_active, bound_hwid, created_at, updated_at)
                VALUES (?, ?, 1, NULL, ?, ?)
                ON CONFLICT(license_key_hash) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (hash_license_key(license_key), display_name, now, now),
            )
            connection.commit()

    def get_license(self, license_key: str) -> Optional[dict]:
        license_record = self.get_managed_license(license_key)
        if license_record:
            return license_record

        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM licenses WHERE license_key_hash = ?",
                (hash_license_key(license_key),),
            ).fetchone()
        return dict(row) if row else None

    def bind_hwid(self, license_key: str, hwid: str) -> None:
        license_record = self.get_managed_license(license_key)
        if license_record:
            self.update_managed_license(license_record["license_id"], bound_hwid=hwid, last_used_at=datetime.utcnow().isoformat())
            return

        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE licenses SET bound_hwid = ?, updated_at = ? WHERE license_key_hash = ?",
                (hwid, now, hash_license_key(license_key)),
            )
            connection.commit()

    def create_managed_license(
        self,
        *,
        license_key: str,
        display_name: str,
        created_by: str,
        channel_access: Iterable[str] | dict[str, list[str]],
        version_pins: dict[str, str] | None = None,
        expires_at: str | None = None,
        notes: str = "",
        status: str = "active",
    ) -> dict:
        now = datetime.utcnow().isoformat()
        if isinstance(channel_access, dict):
            channel_access_json = json.dumps(channel_access)
        else:
            channel_access_json = json.dumps(sorted(set(channel_access)) or ["stable"])
        version_pins_json = json.dumps(version_pins if isinstance(version_pins, dict) else {})
        payload = (
            license_key,
            hash_license_key(license_key),
            display_name,
            status,
            channel_access_json,
            version_pins_json,
            expires_at,
            notes,
            created_by,
            now,
            now,
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO managed_licenses (
                    license_key,
                    license_key_hash,
                    display_name,
                    status,
                    channel_access,
                    version_pins,
                    expires_at,
                    notes,
                    created_by,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            connection.commit()
        return self.get_managed_license(license_key) or {}

    def get_managed_license(self, license_key: str) -> Optional[dict]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM managed_licenses WHERE license_key_hash = ?",
                (hash_license_key(license_key),),
            ).fetchone()
        return self._normalize(row)

    def get_managed_license_by_id(self, license_id: int) -> Optional[dict]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM managed_licenses WHERE license_id = ?",
                (license_id,),
            ).fetchone()
        return self._normalize(row)

    def list_managed_licenses(self, *, status: str | None = None) -> list[dict]:
        query = "SELECT * FROM managed_licenses"
        params: list[object] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._normalize(row) for row in rows]

    def update_managed_license(self, license_id: int, **changes: object) -> Optional[dict]:
        if not changes:
            return self.get_managed_license_by_id(license_id)

        assignments: list[str] = []
        params: list[object] = []
        for key, value in changes.items():
            if key == "channel_access":
                if isinstance(value, dict):
                    value = json.dumps(value)
                elif isinstance(value, (list, tuple, set)):
                    value = json.dumps(sorted(set(value)) or ["stable"])
            elif key == "version_pins" and isinstance(value, dict):
                value = json.dumps(value)
            assignments.append(f"{key} = ?")
            params.append(value)
        assignments.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(license_id)

        with self.database.connect() as connection:
            connection.execute(
                f"UPDATE managed_licenses SET {', '.join(assignments)} WHERE license_id = ?",
                params,
            )
            connection.commit()
        return self.get_managed_license_by_id(license_id)

    def delete_managed_license(self, license_id: int) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM managed_licenses WHERE license_id = ?", (license_id,))
            connection.commit()

    def import_legacy_license(self, license_key_hash: str, display_name: str, bound_hwid: str | None, is_active: int) -> None:
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM managed_licenses WHERE license_key_hash = ?",
                (license_key_hash,),
            ).fetchone()
            if exists:
                return
            connection.execute(
                """
                INSERT INTO managed_licenses (
                    license_key,
                    license_key_hash,
                    display_name,
                    status,
                    bound_hwid,
                    channel_access,
                    expires_at,
                    notes,
                    created_by,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"legacy-{license_key_hash[:12]}",
                    license_key_hash,
                    display_name,
                    "active" if is_active else "disabled",
                    bound_hwid,
                    json.dumps(["stable"]),
                    None,
                    "Imported from legacy hash-only record",
                    "migration",
                    now,
                    now,
                ),
            )
            connection.commit()

    def list_legacy_licenses(self) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def _normalize(self, row) -> Optional[dict]:
        if not row:
            return None
        payload = dict(row)
        try:
            payload["channel_access"] = json.loads(payload.get("channel_access", "[]"))
        except json.JSONDecodeError:
            payload["channel_access"] = ["stable"]
        try:
            payload["version_pins"] = json.loads(payload.get("version_pins", "{}"))
        except json.JSONDecodeError:
            payload["version_pins"] = {}
        return payload
