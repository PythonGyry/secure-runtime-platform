from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from backend.src.core.rate_limit import (
    ADMIN_LOGIN_FAIL_DELAY,
    LICENSE_CHECK_FAIL_DELAY,
    rate_limit_dep,
)
from shared.crypto.runtime_crypto import generate_keypair_b64


class LicenseCheckBody(BaseModel):
    license_key: str
    hwid: str
    app: str = "wishlist"
    channel: str = "stable"


class LicenseInfoBody(BaseModel):
    license_key: str


class DownloadBody(BaseModel):
    download_token: str


class BackupBody(BaseModel):
    license_key: str
    hwid: str
    payload: dict


class BackupLoadBody(BaseModel):
    license_key: str
    hwid: str


class AdminLoginBody(BaseModel):
    username: str
    password: str


class AdminLicenseCreateBody(BaseModel):
    display_name: str
    channel_access: list[str] | dict[str, list[str]] | None = None  # {"wishlist": ["stable"], ...}
    version_pins: dict[str, str] | None = None  # {"wishlist": "1.0.5"} — яку версію грузити; якщо нема — найновіша
    expires_at: str | None = None
    notes: str = ""


class AdminLicenseUpdateBody(BaseModel):
    display_name: Optional[str] = None
    channel_access: Optional[dict[str, list[str]]] = None
    version_pins: Optional[dict[str, str]] = None
    expires_at: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class AdminReleaseStatusBody(BaseModel):
    status: str


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


def _require_admin(container, authorization: str | None) -> dict:
    token = _extract_token(authorization)
    session = container.admin_auth_service.require_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Admin authentication required")
    return session


def build_router(container) -> APIRouter:
    router = APIRouter()
    public_router = APIRouter(prefix="/api/v1")
    admin_router = APIRouter(prefix="/api/admin")

    @public_router.get("/health")
    def health() -> dict:
        active_key = container.key_repository.get_active_key()
        return {
            "status": "ok",
            "public_key_b64": active_key["public_key_b64"] if active_key else "",
            "active_key_id": active_key["key_id"] if active_key else None,
        }

    @public_router.get("/bootstrap/config")
    def bootstrap_config() -> dict:
        return container.get_bootstrap_payload()

    @public_router.post("/license/info")
    def license_info(
        body: LicenseInfoBody,
        _: None = Depends(rate_limit_dep("license/info")),
    ) -> dict:
        """Return apps for a license key (no HWID). For UI display only."""
        info = container.license_service.get_license_info(body.license_key)
        if not info:
            return {"valid": False, "apps": []}
        return info

    @public_router.post("/license/check")
    async def license_check(
        body: LicenseCheckBody,
        _: None = Depends(rate_limit_dep("license/check")),
    ) -> dict:
        requested_app = (body.app or "wishlist").strip()
        requested_channel = (body.channel or container.get_default_channel()).strip()
        is_valid, message, license_record = container.license_service.verify(
            (body.license_key or "").strip(),
            (body.hwid or "").strip(),
            requested_channel,
            app=requested_app,
        )
        if not is_valid:
            await asyncio.sleep(LICENSE_CHECK_FAIL_DELAY)
            return {"valid": False, "message": message}

        version_pins = (license_record or {}).get("version_pins") or {}
        if not isinstance(version_pins, dict):
            version_pins = {}
        pinned_version = version_pins.get(requested_app)
        if pinned_version:
            package_record = container.package_repository.get_release(
                requested_app, requested_channel, pinned_version
            )
        else:
            package_record = None
        if not package_record:
            package_record = container.package_repository.get_latest_release(requested_app, requested_channel)
        if not package_record:
            raise HTTPException(status_code=404, detail="No runtime package available")

        active_key = container.key_repository.get_active_key()
        if not active_key:
            raise HTTPException(status_code=500, detail="No active signing key configured")

        manifest, signature = container.manifest_service.create(
            package_record,
            key_record=active_key,
            server_salt=container.get_server_salt(),
        )
        download_token = container.download_token_repository.create_token(
            int(license_record["license_id"]),
            (body.hwid or "").strip(),
            requested_app,
            requested_channel,
            package_record["version"],
        )
        icon_url = None
        icons_dir = container.settings.packages_dir / "icons"
        if (icons_dir / f"{requested_app}.ico").exists():
            icon_url = f"/api/static/icons/{requested_app}.ico"
        return {
            "valid": True,
            "message": message,
            "manifest": manifest,
            "signature": signature,
            "download_token": download_token,
            "icon_url": icon_url,
        }

    @public_router.post("/runtime/download")
    def runtime_download(body: DownloadBody) -> dict:
        token_record = container.download_token_repository.consume_token(body.download_token)
        if not token_record:
            raise HTTPException(status_code=401, detail="Invalid or expired download token")

        license_record = container.license_repository.get_managed_license_by_id(int(token_record["license_id"]))
        if not license_record:
            raise HTTPException(status_code=401, detail="Unknown license binding")

        package_record = container.package_repository.get_release(
            token_record.get("app", "wishlist"),
            token_record["channel"],
            token_record["version"],
        )
        if not package_record or package_record["version"] != token_record["version"]:
            raise HTTPException(status_code=404, detail="Runtime package version not found")

        package_bytes = container.runtime_package_service.load_plain_package(package_record)
        encrypted_package = container.runtime_package_service.encrypt_for_client(
            package_bytes,
            license_key=(license_record["license_key"] or "").strip(),
            hwid=(token_record["hwid"] or "").strip(),
            server_salt=container.get_server_salt(),
            version=package_record["version"],
        )
        return {
            "version": package_record["version"],
            "channel": package_record["channel"],
            "encrypted_package": encrypted_package,
        }

    @public_router.post("/backup/upload")
    def backup_upload(body: BackupBody) -> dict:
        is_valid, message, _license_record = container.license_service.verify(body.license_key, body.hwid)
        if not is_valid:
            raise HTTPException(status_code=403, detail=message)

        container.backup_service.save_backup(body.hwid, body.payload)
        return {"status": "saved"}

    @public_router.post("/backup/download")
    def backup_download(body: BackupLoadBody) -> dict:
        is_valid, message, _license_record = container.license_service.verify(body.license_key, body.hwid)
        if not is_valid:
            raise HTTPException(status_code=403, detail=message)

        return {"payload": container.backup_service.load_backup(body.hwid)}

    @admin_router.post("/login")
    async def admin_login(
        body: AdminLoginBody,
        _: None = Depends(rate_limit_dep("admin/login")),
    ) -> dict:
        session_token = container.admin_auth_service.authenticate(body.username, body.password)
        if not session_token:
            await asyncio.sleep(ADMIN_LOGIN_FAIL_DELAY)
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        return {"session_token": session_token, "username": body.username}

    @admin_router.post("/logout")
    def admin_logout(authorization: str | None = Header(default=None)) -> dict:
        token = _extract_token(authorization)
        if token:
            container.admin_auth_service.logout(token)
        return {"status": "ok"}

    @admin_router.get("/bootstrap")
    def admin_bootstrap(authorization: str | None = Header(default=None)) -> dict:
        session = _require_admin(container, authorization)
        return {
            "username": session["username"],
            "server": container.get_bootstrap_payload(),
            "stats": {
                "licenses": len(container.license_service.list()),
                "releases": len(container.package_repository.list_releases()),
                "keys": len(container.key_repository.list_keys()),
            },
        }

    @admin_router.get("/licenses")
    def admin_list_licenses(status: str | None = None, authorization: str | None = Header(default=None)) -> dict:
        _require_admin(container, authorization)
        return {"items": container.license_service.list(status=status)}

    @admin_router.post("/licenses")
    def admin_create_license(body: AdminLicenseCreateBody, authorization: str | None = Header(default=None)) -> dict:
        session = _require_admin(container, authorization)
        channel_access = body.channel_access
        if channel_access is None:
            channel_access = {}
        elif isinstance(channel_access, list):
            channel_access = {"wishlist": channel_access} if channel_access else {}
        if isinstance(channel_access, dict) and not channel_access:
            raise HTTPException(
                status_code=400,
                detail="Оберіть хоча б одну програму та канал (channel_access не може бути порожнім).",
            )
        record = container.license_service.create(
            display_name=body.display_name,
            created_by=session["username"],
            channel_access=channel_access,
            version_pins=body.version_pins or {},
            expires_at=body.expires_at,
            notes=body.notes,
        )
        container.admin_repository.record_audit(session["username"], "license.create", {"license_id": record["license_id"]})
        return record

    @admin_router.patch("/licenses/{license_id}")
    def admin_update_license(
        license_id: int,
        body: AdminLicenseUpdateBody,
        authorization: str | None = Header(default=None),
    ) -> dict:
        session = _require_admin(container, authorization)
        changes = {key: value for key, value in (body.model_dump() if hasattr(body, "model_dump") else body.dict()).items() if value is not None}
        record = container.license_service.update(license_id, **changes)
        if not record:
            raise HTTPException(status_code=404, detail="License not found")
        container.admin_repository.record_audit(session["username"], "license.update", {"license_id": license_id, "changes": changes})
        return record

    @admin_router.post("/licenses/{license_id}/unbind")
    def admin_unbind_license(license_id: int, authorization: str | None = Header(default=None)) -> dict:
        session = _require_admin(container, authorization)
        record = container.license_service.unbind_hwid(license_id)
        if not record:
            raise HTTPException(status_code=404, detail="License not found")
        container.admin_repository.record_audit(session["username"], "license.unbind", {"license_id": license_id})
        return record

    @admin_router.post("/licenses/{license_id}/regenerate")
    def admin_regenerate_license(license_id: int, authorization: str | None = Header(default=None)) -> dict:
        session = _require_admin(container, authorization)
        record = container.license_service.regenerate(license_id, updated_by=session["username"])
        if not record:
            raise HTTPException(status_code=404, detail="License not found")
        container.admin_repository.record_audit(session["username"], "license.regenerate", {"license_id": license_id})
        return record

    @admin_router.delete("/licenses/{license_id}")
    def admin_delete_license(license_id: int, authorization: str | None = Header(default=None)) -> dict:
        session = _require_admin(container, authorization)
        container.license_service.delete(license_id)
        container.admin_repository.record_audit(session["username"], "license.delete", {"license_id": license_id})
        return {"status": "deleted"}

    @admin_router.get("/keys")
    def admin_list_keys(authorization: str | None = Header(default=None)) -> dict:
        _require_admin(container, authorization)
        keys = container.key_repository.list_keys()
        safe = [{k: v for k, v in key.items() if k != "private_key_b64"} for key in keys]
        return {"items": safe}

    @admin_router.post("/keys")
    def admin_generate_key(authorization: str | None = Header(default=None)) -> dict:
        session = _require_admin(container, authorization)
        private_key_b64, public_key_b64 = generate_keypair_b64()
        record = container.key_repository.create_key(
            private_key_b64=private_key_b64,
            public_key_b64=public_key_b64,
            status="trusted",
        )
        container.admin_repository.record_audit(session["username"], "key.generate", {"key_id": record["key_id"]})
        return record

    @admin_router.post("/keys/{key_id}/activate")
    def admin_activate_key(key_id: str, authorization: str | None = Header(default=None)) -> dict:
        session = _require_admin(container, authorization)
        record = container.key_repository.activate_key(key_id)
        if not record:
            raise HTTPException(status_code=404, detail="Key not found")
        container.admin_repository.record_audit(session["username"], "key.activate", {"key_id": key_id})
        return record

    @admin_router.post("/keys/{key_id}/retire")
    def admin_retire_key(key_id: str, authorization: str | None = Header(default=None)) -> dict:
        session = _require_admin(container, authorization)
        record = container.key_repository.retire_key(key_id)
        if not record:
            raise HTTPException(status_code=404, detail="Key not found")
        container.admin_repository.record_audit(session["username"], "key.retire", {"key_id": key_id})
        return record

    @admin_router.get("/apps")
    def admin_list_apps(authorization: str | None = Header(default=None)) -> dict:
        _require_admin(container, authorization)
        from_db = container.package_repository.list_apps()
        from_packages = container.package_repository.list_apps_from_packages_dir()
        apps = sorted(set(from_db) | set(from_packages))
        return {"items": apps}

    @admin_router.get("/releases")
    def admin_list_releases(app: str | None = None, channel: str | None = None, authorization: str | None = Header(default=None)) -> dict:
        _require_admin(container, authorization)
        return {"items": container.package_repository.list_releases(app=app, channel=channel)}

    @admin_router.post("/releases/sync")
    def admin_sync_releases(authorization: str | None = Header(default=None)) -> dict:
        session = _require_admin(container, authorization)
        container.package_repository.sync_from_packages_dir()
        container.admin_repository.record_audit(session["username"], "release.sync", {})
        return {"items": container.package_repository.list_releases()}

    @admin_router.patch("/releases/{app}/{channel}/{version}")
    def admin_update_release_status(
        app: str,
        channel: str,
        version: str,
        body: AdminReleaseStatusBody,
        authorization: str | None = Header(default=None),
    ) -> dict:
        session = _require_admin(container, authorization)
        record = container.package_repository.update_release_status(app, channel, version, body.status)
        if not record:
            raise HTTPException(status_code=404, detail="Release not found")
        container.admin_repository.record_audit(
            session["username"],
            "release.status",
            {"app": app, "channel": channel, "version": version, "status": body.status},
        )
        return record

    @admin_router.get("/audit")
    def admin_audit(authorization: str | None = Header(default=None)) -> dict:
        _require_admin(container, authorization)
        return {"items": container.admin_repository.list_audit_log()}

    router.include_router(public_router)
    router.include_router(admin_router)
    return router
