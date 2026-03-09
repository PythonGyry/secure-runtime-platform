from __future__ import annotations

from dataclasses import dataclass, field
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.src.api.routes import build_router
from backend.src.core.rate_limit import RateLimitExceeded, rate_limit_exceeded_handler
from backend.src.core.settings import BackendSettings
from backend.src.repositories.admin_repository import AdminRepository
from backend.src.repositories.backup_repository import BackupRepository
from backend.src.repositories.download_token_repository import DownloadTokenRepository
from backend.src.repositories.key_repository import KeyRepository
from backend.src.repositories.license_repository import LicenseRepository
from backend.src.repositories.package_repository import PackageRepository
from backend.src.services.admin_auth_service import AdminAuthService
from backend.src.services.backup_service import BackupService
from backend.src.services.license_service import LicenseService
from backend.src.services.manifest_service import ManifestService
from backend.src.services.runtime_package_service import RuntimePackageService
from backend.src.storage.database import Database


@dataclass
class Container:
    settings: BackendSettings = field(default_factory=BackendSettings.load)

    def __post_init__(self) -> None:
        self.database = Database(self.settings.db_path)
        self.admin_repository = AdminRepository(self.database)
        self.license_repository = LicenseRepository(self.database)
        self.key_repository = KeyRepository(self.database)
        self.package_repository = PackageRepository(self.database, self.settings.packages_dir)
        self.download_token_repository = DownloadTokenRepository(self.database)
        self.backup_repository = BackupRepository(self.settings.backups_dir)

        self.key_repository.ensure_default_key(self.settings.keypair_file)
        self.admin_repository.ensure_bootstrap_admin(self.settings.admin_bootstrap_file)
        self.package_repository.sync_from_packages_dir()

        self.admin_auth_service = AdminAuthService(self.admin_repository)
        self.license_service = LicenseService(self.license_repository)
        self.manifest_service = ManifestService()
        self.runtime_package_service = RuntimePackageService()
        self.backup_service = BackupService(self.backup_repository)

    def get_server_salt(self) -> str:
        return self.admin_repository.get_config("server_salt", "wishlist-runtime-salt") or "wishlist-runtime-salt"

    def get_default_channel(self) -> str:
        return self.admin_repository.get_config("default_channel", "stable") or "stable"

    def get_client_bootstrap_url(self) -> str:
        return self.admin_repository.get_config("client_bootstrap_url", "http://127.0.0.1:8000") or "http://127.0.0.1:8000"

    def get_bootstrap_payload(self) -> dict:
        latest_releases: dict[str, dict[str, dict]] = {}
        for release in self.package_repository.list_releases(status="published"):
            app = release.get("app", "wishlist")
            channel = release["channel"]
            if app not in latest_releases:
                latest_releases[app] = {}
            current = latest_releases[app].get(channel)
            if not current:
                latest_releases[app][channel] = {
                    "version": release["version"],
                    "channel": channel,
                    "package_sha256": release["package_sha256"],
                }
                continue
            current_release = self.package_repository.get_latest_release(app, channel)
            if current_release and current_release["version"] == release["version"]:
                latest_releases[app][channel] = {
                    "version": release["version"],
                    "channel": channel,
                    "package_sha256": release["package_sha256"],
                }

        return {
            "server_salt": self.get_server_salt(),
            "default_channel": self.get_default_channel(),
            "trusted_public_keys": self.key_repository.get_trusted_public_keys(),
            "latest_releases": latest_releases,
        }

    def parse_trusted_key_ids(self) -> list[str]:
        raw = self.admin_repository.get_config("trusted_key_ids", "[]") or "[]"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []


container = Container()
app = FastAPI(title="Wishlist Platform Backend")
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(build_router(container))
app.mount("/admin", StaticFiles(directory=str((container.settings.data_dir.parent.parent / "admin").resolve()), html=True), name="admin")
icons_dir = container.settings.packages_dir / "icons"
if icons_dir.exists():
    app.mount("/api/static/icons", StaticFiles(directory=str(icons_dir)), name="icons")
