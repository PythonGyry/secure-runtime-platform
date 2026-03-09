from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox

import requests

from client.src.bootstrap.license_client import LicenseClient
from client.src.bootstrap.manifest_client import ManifestClient
from client.src.bootstrap.package_downloader import PackageDownloader
from client.src.bootstrap.package_verifier import PackageVerifier
from client.src.bootstrap.state_store import BootstrapStateStore
from client.src.config.bootstrap_settings import BootstrapSettings
from client.src.launcher.runtime_launcher import RuntimeLauncher
from client.src.security.device import get_hwid
from client.src.ui.connection_error_dialog import show_connection_error
from client.src.ui.icon_resolver import get_verified_icon_path
from client.src.ui.license_dialog import ask_app_choice, ask_license_key


class BootstrapApplication:
    def __init__(self) -> None:
        self.settings = BootstrapSettings.load()
        self.hwid = get_hwid()
        self.state_store = BootstrapStateStore(self.settings.state_db_path, self.hwid)
        self.server_base_url = self.state_store.load_server_url(self.settings.default_server_base_url)
        self.channel = self.state_store.load_channel(self.settings.default_channel)
        self.license_client = LicenseClient(self.server_base_url)
        self.manifest_client = ManifestClient(self.license_client)
        self.package_downloader = PackageDownloader(self.server_base_url)
        self.package_verifier = PackageVerifier()
        self.runtime_launcher = RuntimeLauncher()

    def run(self) -> None:
        cached_license_key = self.state_store.load_license_key()
        license_key = cached_license_key
        status_message = ""
        while True:
            if not license_key:
                license_key = ask_license_key(
                    status_message=status_message,
                    license_client=self.license_client,
                )
                status_message = ""
            if not license_key:
                return

            try:
                time.sleep(0.5)
                bootstrap_config = self.license_client.get_bootstrap_config()
                self.package_verifier.set_trusted_public_keys(bootstrap_config.trusted_public_keys)
                self.channel = self.state_store.load_channel(bootstrap_config.default_channel)

                license_key = license_key.strip()
                # Яку апку завантажувати: фіксована при збірці (-a), одна з ліцензії, або вибір кнопками
                app = "wishlist"
                try:
                    info = self.license_client.get_license_info(license_key)
                    allowed_apps = (info.get("apps") or []) if info.get("valid") else []
                except Exception:
                    allowed_apps = []
                fixed_app = (self.settings.fixed_app or "").strip()
                if fixed_app:
                    app = fixed_app
                elif len(allowed_apps) == 1:
                    app = allowed_apps[0]
                elif len(allowed_apps) > 1:
                    chosen = ask_app_choice(allowed_apps)
                    if chosen is None:
                        status_message = ""
                        continue
                    app = chosen
                elif allowed_apps:
                    app = allowed_apps[0]
                response = self.manifest_client.fetch(
                    license_key=license_key,
                    hwid=self.hwid,
                    channel=self.channel,
                    app=app,
                )
                if not response.get("valid"):
                    self.state_store.clear()
                    license_key = None
                    cached_license_key = None
                    status_message = response.get("message", "Невірний або заблокований ліцензійний ключ.")
                    continue

                self.state_store.save_license_key(license_key)
                self.state_store.save_server_url(self.server_base_url)
                self.state_store.save_channel(self.channel)

                icon_path_str: str | None = None
                icon_url = response.get("icon_url")
                if icon_url:
                    icons_dir = self.settings.runtime_data_dir / "icons"
                    icons_dir.mkdir(parents=True, exist_ok=True)
                    cache_path = icons_dir / f"{app}.ico"
                    try:
                        r = requests.get(
                            f"{self.server_base_url}{icon_url}",
                            timeout=10,
                        )
                        if r.status_code == 200:
                            cache_path.write_bytes(r.content)
                            icon_path_str = str(cache_path)
                    except Exception:
                        pass

                manifest = response["manifest"]
                signature = response["signature"]
                self.package_verifier.verify_manifest(manifest, signature)

                package_response = self.package_downloader.download(response["download_token"])
                runtime_zip = self.package_verifier.decrypt_to_memory(
                    encrypted_package_b64=package_response["encrypted_package"],
                    license_key=license_key,
                    hwid=self.hwid,
                    server_salt=manifest["server_salt"],
                    version=manifest["version"],
                    expected_sha256=manifest["package_sha256"],
                )

                context = {
                    "license_key": license_key,
                    "hwid": self.hwid,
                    "server_base_url": self.server_base_url,
                    "server_salt": bootstrap_config.server_salt,
                    "legacy_base_dir": str(self.settings.legacy_base_dir),
                    "runtime_data_dir": str(self.settings.runtime_data_dir),
                    "icon_path": icon_path_str,
                    "app_version": manifest.get("version", ""),
                }
                self.runtime_launcher.launch(
                    runtime_zip,
                    manifest["module_name"],
                    manifest["entrypoint"],
                    context,
                )
                return
            except requests.exceptions.ConnectionError:
                url = self.server_base_url or "сервер"
                show_connection_error(url)
                raise
            except Exception as exc:
                root = tk.Tk()
                root.withdraw()
                icon_path = get_verified_icon_path()
                if icon_path:
                    try:
                        root.iconbitmap(str(icon_path))
                    except Exception:
                        pass
                try:
                    messagebox.showerror("Помилка", str(exc), parent=root)
                finally:
                    root.destroy()
                raise
