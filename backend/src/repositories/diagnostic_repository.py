from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path


class DiagnosticRepository:
    INDEX_FILENAME = "_index.json"

    def __init__(self, diagnostics_dir: Path) -> None:
        self.diagnostics_dir = diagnostics_dir
        self.diagnostics_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.diagnostics_dir / self.INDEX_FILENAME

    @staticmethod
    def _safe_hwid_segment(hwid: str) -> str:
        cleaned = re.sub(r"[^\w.-]+", "_", (hwid or "").strip(), flags=re.UNICODE)
        return (cleaned or "unknown")[:120]

    @staticmethod
    def _safe_report_id(report_id: str) -> str:
        cleaned = re.sub(r"[^\w.-]+", "_", (report_id or "").strip(), flags=re.UNICODE)
        return cleaned[:180]

    @staticmethod
    def _summary_from_envelope(data: dict, *, file_size: int = 0) -> dict:
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        export_meta = payload.get("export_meta") if isinstance(payload.get("export_meta"), dict) else {}
        original_counts = export_meta.get("original_counts") if isinstance(export_meta.get("original_counts"), dict) else {}
        exported_counts = export_meta.get("exported_counts") if isinstance(export_meta.get("exported_counts"), dict) else {}
        return {
            "report_id": data.get("report_id"),
            "hwid": data.get("hwid"),
            "license_id": data.get("license_id"),
            "license_display_name": data.get("license_display_name"),
            "license_key_preview": data.get("license_key_preview"),
            "uploaded_at": data.get("uploaded_at"),
            "app_version": payload.get("app_version"),
            "file_size": file_size,
            "log_count": exported_counts.get("logs", len(payload.get("logs") or [])),
            "response_count": exported_counts.get("server_responses", len(payload.get("server_responses") or [])),
            "cookie_count": len(payload.get("cookies") or []),
            "account_count": payload.get("account_count") or len(payload.get("accounts") or []),
            "original_log_count": original_counts.get("logs"),
            "original_response_count": original_counts.get("server_responses"),
        }

    def _load_index(self) -> list[dict]:
        if not self._index_path.exists():
            return []
        try:
            payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        items = payload.get("reports") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict) and item.get("report_id")]

    def _save_index(self, items: list[dict]) -> None:
        sorted_items = sorted(
            items,
            key=lambda item: str(item.get("uploaded_at") or ""),
            reverse=True,
        )
        self._index_path.write_text(
            json.dumps({"reports": sorted_items}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _upsert_index_entry(self, summary: dict) -> None:
        items = self._load_index()
        report_id = summary.get("report_id")
        items = [item for item in items if item.get("report_id") != report_id]
        items.append(summary)
        self._save_index(items)

    def rebuild_index(self) -> int:
        items: list[dict] = []
        for path in self.diagnostics_dir.glob("*.json"):
            if path.name == self.INDEX_FILENAME:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            summary = self._summary_from_envelope(data, file_size=path.stat().st_size)
            summary["report_id"] = summary.get("report_id") or path.stem
            items.append(summary)
        self._save_index(items)
        return len(items)

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
        raw = json.dumps(envelope, ensure_ascii=False)
        path.write_text(raw, encoding="utf-8")
        summary = self._summary_from_envelope(envelope, file_size=len(raw.encode("utf-8")))
        summary["report_id"] = report_id
        self._upsert_index_entry(summary)
        return {"report_id": report_id, "uploaded_at": uploaded_at, "status": "saved"}

    def list_reports(self, *, hwid: str | None = None, license_id: int | None = None) -> list[dict]:
        items = self._load_index()
        if not items:
            items = self._load_index_after_rebuild()

        filtered: list[dict] = []
        for item in items:
            if hwid and str(item.get("hwid") or "") != hwid:
                continue
            if license_id is not None:
                record_license = item.get("license_id")
                if record_license is None or int(record_license) != int(license_id):
                    continue
            path = self.diagnostics_dir / f"{item.get('report_id')}.json"
            if not path.exists():
                continue
            filtered.append(item)
        return filtered

    def _load_index_after_rebuild(self) -> list[dict]:
        self.rebuild_index()
        return self._load_index()

    def get_report(self, report_id: str) -> dict | None:
        safe_id = self._safe_report_id(report_id)
        path = self.diagnostics_dir / f"{safe_id}.json"
        if not path.exists() or not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
