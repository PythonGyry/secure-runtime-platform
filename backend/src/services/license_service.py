from __future__ import annotations

import secrets
from datetime import datetime

from backend.src.repositories.license_repository import LicenseRepository

# Текст для користувача (без технічних деталей / адмінки)
_SUPPORT_TG = "Напишіть у Telegram @inceglist (https://t.me/inceglist)"


class LicenseService:
    def __init__(self, repository: LicenseRepository) -> None:
        self.repository = repository

    @staticmethod
    def _msg(text: str, *, with_support: bool = False) -> str:
        if with_support:
            return f"{text} {_SUPPORT_TG}."
        return text

    def create(
        self,
        *,
        display_name: str,
        created_by: str,
        channel_access: list[str] | dict[str, list[str]] | None = None,
        version_pins: dict[str, str] | None = None,
        expires_at: str | None = None,
        notes: str = "",
        max_accounts: int | None = None,
    ) -> dict:
        if channel_access is None:
            channel_access = {}
        elif isinstance(channel_access, list):
            channel_access = {"wishlist": channel_access} if channel_access else {}
        if not channel_access:
            raise ValueError("channel_access не може бути порожнім")
        return self.repository.create_managed_license(
            license_key=self._generate_license_key(),
            display_name=display_name,
            created_by=created_by,
            channel_access=channel_access,
            version_pins=version_pins or {},
            expires_at=expires_at,
            notes=notes,
            max_accounts=max_accounts,
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
        return {
            "apps": apps,
            "valid": True,
            "max_accounts": record.get("max_accounts"),
        }

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

    def rebind_to_device(self, license_key: str, hwid: str) -> tuple[bool, str, dict | None]:
        """Відв'язати попередній пристрій і прив'язати ліцензію до поточного HWID."""
        key = (license_key or "").strip()
        device = (hwid or "").strip()
        if not key:
            return False, "Введіть ліцензійний ключ", None
        if not device:
            return False, "Не вдалося визначити пристрій", None

        record = self.repository.get_managed_license(key)
        if not record:
            legacy_record = self.repository.get_license(key)
            if legacy_record:
                return False, self._msg("Цей ключ більше не підтримується.", with_support=True), None
            return False, self._msg("Ліцензію не знайдено. Перевірте ключ.", with_support=True), None

        if record["status"] != "active":
            return False, self._msg("Ліцензію вимкнено.", with_support=True), None

        expires_at = record.get("expires_at")
        if expires_at and expires_at < datetime.utcnow().isoformat():
            return False, self._msg("Термін дії ліцензії закінчився.", with_support=True), None

        bound_hwid = (record.get("bound_hwid") or "").strip() or None
        if bound_hwid == device:
            return True, "Ліцензію вже прив'язано до цього пристрою", record

        record = self.repository.update_managed_license(
            record["license_id"],
            bound_hwid=device,
            last_used_at=datetime.utcnow().isoformat(),
        )
        return True, "Пристрій оновлено. Ліцензію прив'язано до цього ПК", record

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
        version_pins = record.get("version_pins") or {}
        if not isinstance(version_pins, dict):
            version_pins = {}
        return self.repository.create_managed_license(
            license_key=self._generate_license_key(),
            display_name=record["display_name"],
            created_by=updated_by,
            channel_access=ca,
            version_pins=version_pins,
            expires_at=record.get("expires_at"),
            notes=record.get("notes", ""),
            status=record.get("status", "active"),
            max_accounts=record.get("max_accounts"),
        )

    def verify(
        self,
        license_key: str,
        hwid: str,
        channel: str = "stable",
        app: str = "wishlist",
        *,
        legacy_hwid: str | None = None,
    ) -> tuple[bool, str, dict | None]:
        record = self.repository.get_managed_license(license_key)
        if not record:
            legacy_record = self.repository.get_license(license_key)
            if legacy_record:
                return False, self._msg("Цей ключ більше не підтримується.", with_support=True), None
            return False, self._msg("Ліцензію не знайдено. Перевірте ключ.", with_support=True), None

        if record["status"] != "active":
            return False, self._msg("Ліцензію вимкнено.", with_support=True), None

        expires_at = record.get("expires_at")
        if expires_at and expires_at < datetime.utcnow().isoformat():
            return False, self._msg("Термін дії ліцензії закінчився.", with_support=True), None

        allowed = self._parse_app_channel_access(record.get("channel_access"))
        app_channels = allowed.get(app, [])
        if app_channels and channel not in app_channels:
            return False, self._msg("Немає доступу до цієї програми за вашим ключем.", with_support=True), None

        bound_hwid = record.get("bound_hwid")
        legacy = (legacy_hwid or "").strip() or None
        if bound_hwid and bound_hwid != hwid:
            if legacy and bound_hwid == legacy:
                record = self.repository.update_managed_license(
                    record["license_id"],
                    bound_hwid=hwid,
                    last_used_at=datetime.utcnow().isoformat(),
                )
            else:
                # Хто ввів валідний ключ — отримує місце на цьому ПК (без нового .exe)
                record = self.repository.update_managed_license(
                    record["license_id"],
                    bound_hwid=hwid,
                    last_used_at=datetime.utcnow().isoformat(),
                )
        elif not bound_hwid:
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

        return True, "Ліцензія дійсна", record

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
