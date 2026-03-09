from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from client.src.security.package_unwrap import unwrap_and_extract, unwrap_to_memory
from shared.crypto.runtime_crypto import verify_signature


class PackageVerifier:
    def __init__(self, trusted_public_keys: dict[str, str] | None = None) -> None:
        self.trusted_public_keys = trusted_public_keys or {}

    def set_trusted_public_keys(self, trusted_public_keys: dict[str, str]) -> None:
        self.trusted_public_keys = trusted_public_keys

    def verify_manifest(self, manifest: Dict[str, Any], signature: str) -> None:
        key_id = manifest.get("key_id")
        public_key_b64 = self.trusted_public_keys.get(key_id or "")
        if not public_key_b64:
            raise RuntimeError("No trusted public key available for manifest verification")
        if not verify_signature(manifest, signature, public_key_b64):
            raise RuntimeError("Manifest signature verification failed")

    def decrypt_to_memory(
        self,
        *,
        encrypted_package_b64: str,
        license_key: str,
        hwid: str,
        server_salt: str,
        version: str,
        expected_sha256: str,
    ) -> bytes:
        """Decrypt package to memory. No disk write."""
        return unwrap_to_memory(
            encrypted_b64=encrypted_package_b64,
            license_key=license_key,
            hwid=hwid,
            server_salt=server_salt,
            version=version,
            expected_sha256=expected_sha256,
        )

    def decrypt_and_extract(
        self,
        *,
        encrypted_package_b64: str,
        license_key: str,
        hwid: str,
        server_salt: str,
        version: str,
        expected_sha256: str,
        target_dir: Path,
    ) -> Path:
        return unwrap_and_extract(
            encrypted_b64=encrypted_package_b64,
            license_key=license_key,
            hwid=hwid,
            server_salt=server_salt,
            version=version,
            expected_sha256=expected_sha256,
            target_dir=target_dir,
        )
