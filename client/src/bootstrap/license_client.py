from __future__ import annotations

import time
from typing import Any, Dict

import requests

from shared.contracts.runtime_manifest import BootstrapConfigResponse

_CONNECT_RETRIES = 5
_CONNECT_RETRY_DELAY = 2.0


def _request_with_retry(method: str, url: str, **kwargs: Any) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(_CONNECT_RETRIES):
        try:
            return requests.request(method, url, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout) as exc:
            last_exc = exc
            if attempt < _CONNECT_RETRIES - 1:
                time.sleep(_CONNECT_RETRY_DELAY * (attempt + 1))
    raise last_exc  # type: ignore[misc]


class LicenseClient:
    def __init__(self, server_base_url: str) -> None:
        self.server_base_url = server_base_url.rstrip("/")

    def get_health(self) -> Dict[str, Any]:
        response = _request_with_retry("GET", f"{self.server_base_url}/api/v1/health", timeout=10)
        response.raise_for_status()
        return response.json()

    def get_bootstrap_config(self) -> BootstrapConfigResponse:
        response = _request_with_retry("GET", f"{self.server_base_url}/api/v1/bootstrap/config", timeout=10)
        response.raise_for_status()
        return BootstrapConfigResponse.from_dict(response.json())

    def get_license_info(self, license_key: str) -> Dict[str, Any]:
        """Get apps for a license key (no HWID). For UI display."""
        response = _request_with_retry(
            "POST",
            f"{self.server_base_url}/api/v1/license/info",
            json={"license_key": (license_key or "").strip()},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def check_license(self, license_key: str, hwid: str, channel: str = "stable", app: str = "wishlist") -> Dict[str, Any]:
        payload = {
            "license_key": license_key,
            "hwid": hwid,
            "channel": channel,
            "app": app,
        }
        response = _request_with_retry(
            "POST",
            f"{self.server_base_url}/api/v1/license/check",
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
