from __future__ import annotations

import secrets
from datetime import datetime

from backend.src.repositories.license_repository import LicenseRepository


class LicenseService:
    def __init__(self, repository: LicenseRepository) -> None:
        self.repository = repository

    def create(
        self,
        *,
        display_name: str,
        created_by: str,
        channel_access: list[str] | dict[str, list[str]] | None = None,
        expires_at: str | None = None,
        notes: str = "",
    ) -> dict:
        if channel_access is None:
            channel_access = {"wishlist": ["stable"]}
        elif isinstance(channel_access, list):
            channel_access = {"wishlist": channel_access} if channel_access else {"wishlist": ["stable"]}
        return self.repository.create_managed_license(
            license_key=self._generate_license_key(),
            display_name=display_name,
            created_by=created_by,
            channel_access=channel_access,
            expires_at=expires_at,
            notes=notes,
        )

    def list(self, *, status: str | None = None) -> list[dict]:
        return self.repository.list_managed_licenses(status=status)

    def get_license_info(self, license_key: str) -> dict | None:
        """Return apps for a license key (no HWID). For UI display only."""
        record = self.repository.get_managed_license((license_key or "").strip())
        if not record:
            return None
        if record["status"] != "active":
            return None
        expires_at = record.get("expires_at")
        if expires_at and expires_at < datetime.utcnow().isoformat():
            return None
        allowed = self._parse_app_channel_access(record.get("channel_access"))
        apps = sorted(allowed.keys()) if allowed else []
        return {"apps": apps, "valid": True}

    def get(self, license_id: int) -> dict | None:
        return self.repository.get_managed_license_by_id(license_id)

    def disable(self, license_id: int) -> dict | None:
        return self.repository.update_managed_license(license_id, status="disabled")

    def enable(self, license_id: int) -> dict | None:
        return self.repository.update_managed_license(license_id, status="active")

    def delete(self, license_id: int) -> None:
        self.repository.delete_managed_license(license_id)

    def unbind_hwid(self, license_id: int) -> dict | None:
        return self.repository.update_managed_license(license_id, bound_hwid=None)

    def update(self, license_id: int, **changes: object) -> dict | None:
        return self.repository.update_managed_license(license_id, **changes)

    def regenerate(self, license_id: int, *, updated_by: str) -> dict | None:
        record = self.repository.get_managed_license_by_id(license_id)
        if not record:
            return None

        self.repository.delete_managed_license(license_id)
        ca = record.get("channel_access")
        if ca is None:
            ca = {"wishlist": ["stable"]}
        elif isinstance(ca, list):
            ca = {"wishlist": ca} if ca else {"wishlist": ["stable"]}
        return self.repository.create_managed_license(
            license_key=self._generate_license_key(),
            display_name=record["display_name"],
            created_by=updated_by,
            channel_access=ca,
            expires_at=record.get("expires_at"),
            notes=record.get("notes", ""),
            status=record.get("status", "active"),
        )

    def verify(
        self,
        license_key: str,
        hwid: str,
        channel: str = "stable",
        app: str = "wishlist",
    ) -> tuple[bool, str, dict | None]:
        record = self.repository.get_managed_license(license_key)
        if not record:
            legacy_record = self.repository.get_license(license_key)
            if legacy_record:
                return False, "Legacy license records must be recreated in the admin panel", None
            return False, "License not found", None

        if record["status"] != "active":
            return False, "License is disabled", None

        expires_at = record.get("expires_at")
        if expires_at and expires_at < datetime.utcnow().isoformat():
            return False, "License has expired", None

        allowed = self._parse_app_channel_access(record.get("channel_access"))
        app_channels = allowed.get(app, [])
        if app_channels and channel not in app_channels:
            return False, f"App '{app}' / channel '{channel}' is not allowed for this license", None

        bound_hwid = record.get("bound_hwid")
        if bound_hwid and bound_hwid != hwid:
            return False, "License is already bound to another device", None
        if not bound_hwid:
            record = self.repository.update_managed_license(
                record["license_id"],
                bound_hwid=hwid,
                last_used_at=datetime.utcnow().isoformat(),
            )
        else:
            record = self.repository.update_managed_license(
                record["license_id"],
                last_used_at=datetime.utcnow().isoformat(),
            )

        return True, "License is valid", record

    def _parse_app_channel_access(self, raw: str | list | dict | None) -> dict[str, list[str]]:
        """Parse channel_access: list -> {wishlist: list}, dict -> as is."""
        if raw is None:
            return {"wishlist": ["stable"]}
        if isinstance(raw, list):
            return {"wishlist": raw if raw else ["stable"]}
        if isinstance(raw, dict):
            return {k: (v if isinstance(v, list) else [v]) for k, v in raw.items()}
        import json
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return {"wishlist": parsed if parsed else ["stable"]}
            return {k: (v if isinstance(v, list) else [v]) for k, v in parsed.items()}
        except (TypeError, json.JSONDecodeError):
            return {"wishlist": ["stable"]}

    def _generate_license_key(self) -> str:
        chunks = [secrets.token_hex(2).upper() for _ in range(4)]
        return "WL-" + "-".join(chunks)
