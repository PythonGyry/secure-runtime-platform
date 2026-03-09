from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class BackupRepository:
    def __init__(self, backups_dir: Path) -> None:
        self.backups_dir = backups_dir

    def _path(self, hwid: str) -> Path:
        return self.backups_dir / f"{hwid}.json"

    def save(self, hwid: str, payload: dict) -> None:
        self._path(hwid).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def load(self, hwid: str) -> Optional[dict]:
        path = self._path(hwid)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
