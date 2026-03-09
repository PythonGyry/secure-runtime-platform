from __future__ import annotations

from backend.src.repositories.backup_repository import BackupRepository


class BackupService:
    def __init__(self, repository: BackupRepository) -> None:
        self.repository = repository

    def save_backup(self, hwid: str, payload: dict) -> None:
        self.repository.save(hwid, payload)

    def load_backup(self, hwid: str) -> dict | None:
        return self.repository.load(hwid)
