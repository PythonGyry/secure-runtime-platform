from __future__ import annotations

from typing import Any, Dict

from client.src.bootstrap.license_client import LicenseClient


class ManifestClient:
    def __init__(self, license_client: LicenseClient) -> None:
        self.license_client = license_client

    def fetch(self, *, license_key: str, hwid: str, channel: str = "stable", app: str = "wishlist") -> Dict[str, Any]:
        return self.license_client.check_license(license_key=license_key, hwid=hwid, channel=channel, app=app)
