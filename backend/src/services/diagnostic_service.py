from __future__ import annotations

from backend.src.repositories.diagnostic_repository import DiagnosticRepository


class DiagnosticService:
    def __init__(self, repository: DiagnosticRepository) -> None:
        self.repository = repository

    def save_report(self, hwid: str, payload: dict, *, license_record: dict | None = None) -> dict:
        license_meta: dict = {}
        if license_record:
            license_meta = {
                "license_id": license_record.get("license_id"),
                "license_display_name": license_record.get("display_name"),
                "license_key_preview": self._mask_license_key(str(license_record.get("license_key") or "")),
            }
        return self.repository.save(hwid, payload, license_meta=license_meta)

    def rebuild_index(self) -> int:
        return self.repository.rebuild_index()

    def list_reports(self, *, hwid: str | None = None, license_id: int | None = None) -> list[dict]:
        return self.repository.list_reports(hwid=hwid, license_id=license_id)

    def get_report(self, report_id: str) -> dict | None:
        return self.repository.get_report(report_id)

    @staticmethod
    def _mask_license_key(license_key: str) -> str:
        key = license_key.strip()
        if len(key) <= 8:
            return "****"
        return f"{key[:7]}****"
