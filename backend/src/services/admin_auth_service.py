from __future__ import annotations

from backend.src.repositories.admin_repository import AdminRepository, hash_password, _verify_password


class AdminAuthService:
    def __init__(self, repository: AdminRepository) -> None:
        self.repository = repository

    def authenticate(self, username: str, password: str) -> str | None:
        user = self.repository.get_user(username)
        if not user:
            return None
        if not _verify_password(password, user["password_hash"]):
            return None
        self.repository.migrate_password_if_legacy(username, password)
        return self.repository.create_session(username)

    def require_session(self, session_token: str | None) -> dict | None:
        if not session_token:
            return None
        return self.repository.get_session(session_token)

    def logout(self, session_token: str) -> None:
        self.repository.delete_session(session_token)
