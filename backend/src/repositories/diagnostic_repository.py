from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path


class DiagnosticRepository:
    def __init__(self, diagnostics_dir: Path) -> None:
        self.diagnostics_dir = diagnostics_dir
        self.diagnostics_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_hwid_segment(hwid: str) -> str:
        cleaned = re.sub(r"[^\w.-]+", "_", (hwid or "").strip(), flags=re.UNICODE)
        return (cleaned or "unknown")[:120]

    @staticmethod
    def _safe_report_id(report_id: str) -> str:
        cleaned = re.sub(r"[^\w.-]+", "_", (report_id or "").strip(), flags=re.UNICODE)
        return cleaned[:180]

    def save(self, hwid: str, payload: dict, *, license_meta: dict | None = None) -> dict:
        report_id = f"{self._safe_hwid_segment(hwid)}_{int(time.time() * 1000)}"
        uploaded_at = datetime.utcnow().isoformat()
        envelope = {
            "report_id": report_id,
            "hwid": hwid,
            "uploaded_at": uploaded_at,
            **(license_meta or {}),
            "payload": payload,
        }
        path = self.diagnostics_dir / f"{report_id}.json"
        path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"report_id": report_id, "uploaded_at": uploaded_at, "status": "saved"}

    def list_reports(self, *, hwid: str | None = None, license_id: int | None = None) -> list[dict]:
        items: list[dict] = []
        for path in sorted(self.diagnostics_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if hwid and data.get("hwid") != hwid:
                continue
            if license_id is not None and data.get("license_id") != license_id:
                continue
            payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
            items.append(
                {
                    "report_id": data.get("report_id", path.stem),
                    "hwid": data.get("hwid"),
                    "license_id": data.get("license_id"),
                    "license_display_name": data.get("license_display_name"),
                    "license_key_preview": data.get("license_key_preview"),
                    "uploaded_at": data.get("uploaded_at"),
                    "app_version": payload.get("app_version"),
                    "log_count": len(payload.get("logs") or []),
                    "response_count": len(payload.get("server_responses") or []),
                    "cookie_count": len(payload.get("cookies") or []),
                    "account_count": payload.get("account_count") or len(payload.get("accounts") or []),
                }
            )
        return items

    def get_report(self, report_id: str) -> dict | None:
        safe_id = self._safe_report_id(report_id)
        path = self.diagnostics_dir / f"{safe_id}.json"
        if not path.exists() or not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
