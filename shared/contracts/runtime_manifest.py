from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(slots=True)
class RuntimeManifest:
    version: str
    channel: str
    module_name: str
    entrypoint: str
    package_sha256: str
    package_size: int
    generated_at: str
    expires_at: str
    server_salt: str
    key_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RuntimeManifest":
        return cls(**payload)


@dataclass(slots=True)
class LicenseCheckRequest:
    license_key: str
    hwid: str
    channel: str = "stable"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LicenseCheckResponse:
    valid: bool
    message: str
    manifest: Optional[Dict[str, Any]] = None
    signature: Optional[str] = None
    download_token: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LicenseCheckResponse":
        return cls(**payload)


@dataclass(slots=True)
class BootstrapConfigResponse:
    server_salt: str
    default_channel: str
    trusted_public_keys: Dict[str, str]
    latest_releases: Dict[str, Dict[str, Any]]

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "BootstrapConfigResponse":
        return cls(**payload)
