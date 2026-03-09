from __future__ import annotations

from typing import Any, Dict

import requests


class PackageDownloader:
    def __init__(self, server_base_url: str) -> None:
        self.server_base_url = server_base_url.rstrip("/")

    def download(self, download_token: str) -> Dict[str, Any]:
        response = requests.post(
            f"{self.server_base_url}/api/v1/runtime/download",
            json={"download_token": download_token},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
