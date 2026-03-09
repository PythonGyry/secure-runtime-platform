from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.src.storage.database import Database


SEMVER_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-+].*)?$")


class PackageRepository:
    def __init__(self, database: Database, packages_dir: Path) -> None:
        self.database = database
        self.packages_dir = packages_dir

    def sync_from_packages_dir(self) -> None:
        for manifest_path in sorted(self.packages_dir.glob("*.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            package_path = self.packages_dir / manifest["package_file"]
            if not package_path.exists():
                continue
            self.upsert_release(
                app=manifest.get("app", "wishlist"),
                channel=manifest.get("channel", "stable"),
                version=manifest["version"],
                module_name=manifest["module_name"],
                entrypoint=manifest["entrypoint"],
                package_file=manifest["package_file"],
                package_path=str(package_path),
                manifest_path=str(self.packages_dir / manifest_path.name),
                package_sha256=manifest["package_sha256"],
                package_size=int(manifest["package_size"]),
                status="published",
            )

    def get_latest_package(self, app: str = "wishlist", channel: str = "stable") -> Optional[dict]:
        return self.get_latest_release(app, channel)

    def get_latest_release(self, app: str = "wishlist", channel: str = "stable") -> Optional[dict]:
        releases = [r for r in self.list_releases(app=app, channel=channel, status="published")]
        if not releases:
            return None
        return max(releases, key=lambda item: self._version_key(item["version"]))

    def get_release(self, app: str, channel: str, version: str) -> Optional[dict]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_releases WHERE app = ? AND channel = ? AND version = ?",
                (app, channel, version),
            ).fetchone()
        return dict(row) if row else None

    def list_releases(
        self,
        *,
        app: str | None = None,
        channel: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        query = "SELECT * FROM runtime_releases"
        clauses: list[str] = []
        params: list[object] = []
        if app:
            clauses.append("app = ?")
            params.append(app)
        if channel:
            clauses.append("channel = ?")
            params.append(channel)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY app, published_at DESC"
        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_apps(self) -> list[str]:
        """Список app з БД (релізи)."""
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT app FROM runtime_releases ORDER BY app"
            ).fetchall()
        return [row["app"] for row in rows]

    def list_apps_from_packages_dir(self) -> list[str]:
        """Список app з маніфестів у backend/packages/*.json (без залежності від sync)."""
        apps: set[str] = set()
        if not self.packages_dir.exists():
            return []
        for manifest_path in self.packages_dir.glob("*.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                app = manifest.get("app") or "wishlist"
                apps.add(app)
            except Exception:
                continue
        return sorted(apps)

    def upsert_release(
        self,
        *,
        app: str,
        channel: str,
        version: str,
        module_name: str,
        entrypoint: str,
        package_file: str,
        package_path: str,
        manifest_path: str,
        package_sha256: str,
        package_size: int,
        status: str = "published",
    ) -> Optional[dict]:
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO runtime_releases (
                    app,
                    channel,
                    version,
                    module_name,
                    entrypoint,
                    package_file,
                    package_path,
                    manifest_path,
                    package_sha256,
                    package_size,
                    status,
                    published_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(app, channel, version) DO UPDATE SET
                    module_name = excluded.module_name,
                    entrypoint = excluded.entrypoint,
                    package_file = excluded.package_file,
                    package_path = excluded.package_path,
                    manifest_path = excluded.manifest_path,
                    package_sha256 = excluded.package_sha256,
                    package_size = excluded.package_size,
                    status = excluded.status
                """,
                (
                    app,
                    channel,
                    version,
                    module_name,
                    entrypoint,
                    package_file,
                    package_path,
                    manifest_path,
                    package_sha256,
                    package_size,
                    status,
                    now,
                ),
            )
            connection.commit()
        return self.get_release(app, channel, version)

    def update_release_status(self, app: str, channel: str, version: str, status: str) -> Optional[dict]:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE runtime_releases SET status = ? WHERE app = ? AND channel = ? AND version = ?",
                (status, app, channel, version),
            )
            connection.commit()
        return self.get_release(app, channel, version)

    def _version_key(self, version: str) -> tuple[int, int, int, str]:
        match = SEMVER_RE.match(version)
        if not match:
            return (0, 0, 0, version)
        return (
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
            version,
        )
