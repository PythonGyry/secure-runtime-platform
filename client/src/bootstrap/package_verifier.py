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
        legacy_hwid: str | None = None,
    ) -> bytes:
        """Decrypt package to memory. No disk write."""
        hwid_candidates = [hwid]
        legacy = (legacy_hwid or "").strip()
        if legacy and legacy not in hwid_candidates:
            hwid_candidates.append(legacy)

        last_error: Exception | None = None
        for candidate in hwid_candidates:
            try:
                return unwrap_to_memory(
                    encrypted_b64=encrypted_package_b64,
                    license_key=license_key,
                    hwid=candidate,
                    server_salt=server_salt,
                    version=version,
                    expected_sha256=expected_sha256,
                )
            except (ValueError, RuntimeError) as exc:
                last_error = exc
                if "Failed to decrypt payload" not in str(exc) and "Integrity check failed" not in str(exc):
                    raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("Package decryption failed")

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
