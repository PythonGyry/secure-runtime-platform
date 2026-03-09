from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS licenses (
                    license_key_hash TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    bound_hwid TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS download_tokens (
                    download_token TEXT PRIMARY KEY,
                    license_key_hash TEXT NOT NULL,
                    hwid TEXT NOT NULL,
                    version TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS managed_licenses (
                    license_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT NOT NULL UNIQUE,
                    license_key_hash TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    bound_hwid TEXT,
                    channel_access TEXT NOT NULL,
                    expires_at TEXT,
                    notes TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_used_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS signing_keys (
                    key_id TEXT PRIMARY KEY,
                    private_key_b64 TEXT NOT NULL,
                    public_key_b64 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    rotated_at TEXT,
                    retired_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_releases (
                    release_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    version TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    entrypoint TEXT NOT NULL,
                    package_file TEXT NOT NULL,
                    package_path TEXT NOT NULL,
                    manifest_path TEXT NOT NULL,
                    package_sha256 TEXT NOT NULL,
                    package_size INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    UNIQUE(channel, version)
                )
                """
            )
            self._migrate_runtime_releases_add_app(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS managed_download_tokens (
                    download_token TEXT PRIMARY KEY,
                    license_id INTEGER NOT NULL,
                    hwid TEXT NOT NULL,
                    app TEXT NOT NULL DEFAULT 'wishlist',
                    channel TEXT NOT NULL,
                    version TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._migrate_download_tokens_add_app(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    session_token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS server_config (
                    config_key TEXT PRIMARY KEY,
                    config_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._seed_server_config(connection)
            connection.commit()

    def _migrate_download_tokens_add_app(self, connection: sqlite3.Connection) -> None:
        cursor = connection.execute("PRAGMA table_info(managed_download_tokens)")
        columns = [row[1] for row in cursor.fetchall()]
        if "app" in columns:
            return
        connection.execute("ALTER TABLE managed_download_tokens ADD COLUMN app TEXT NOT NULL DEFAULT 'wishlist'")

    def _migrate_runtime_releases_add_app(self, connection: sqlite3.Connection) -> None:
        """Migrate runtime_releases: add app column if missing."""
        cursor = connection.execute("PRAGMA table_info(runtime_releases)")
        columns = [row[1] for row in cursor.fetchall()]
        if "app" in columns:
            return
        connection.execute(
            """
            CREATE TABLE runtime_releases_new (
                release_id INTEGER PRIMARY KEY AUTOINCREMENT,
                app TEXT NOT NULL DEFAULT 'wishlist',
                channel TEXT NOT NULL,
                version TEXT NOT NULL,
                module_name TEXT NOT NULL,
                entrypoint TEXT NOT NULL,
                package_file TEXT NOT NULL,
                package_path TEXT NOT NULL,
                manifest_path TEXT NOT NULL,
                package_sha256 TEXT NOT NULL,
                package_size INTEGER NOT NULL,
                status TEXT NOT NULL,
                published_at TEXT NOT NULL,
                UNIQUE(app, channel, version)
            )
            """
        )
        connection.execute(
            "INSERT INTO runtime_releases_new (release_id, app, channel, version, module_name, entrypoint, package_file, package_path, manifest_path, package_sha256, package_size, status, published_at) "
            "SELECT release_id, 'wishlist', channel, version, module_name, entrypoint, package_file, package_path, manifest_path, package_sha256, package_size, status, published_at FROM runtime_releases"
        )
        connection.execute("DROP TABLE runtime_releases")
        connection.execute("ALTER TABLE runtime_releases_new RENAME TO runtime_releases")

    def _seed_server_config(self, connection: sqlite3.Connection) -> None:
        now = datetime.utcnow().isoformat()
        defaults = {
            "server_salt": "wishlist-runtime-salt",
            "client_bootstrap_url": "http://127.0.0.1:8000",
            "default_channel": "stable",
        }
        for key, value in defaults.items():
            connection.execute(
                """
                INSERT INTO server_config (config_key, config_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(config_key) DO NOTHING
                """,
                (key, value, now),
            )
        connection.execute(
            """
            INSERT INTO server_config (config_key, config_value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(config_key) DO NOTHING
            """,
            ("trusted_key_ids", json.dumps([]), now),
        )
