from __future__ import annotations

import base64
from pathlib import Path

from shared.crypto.runtime_crypto import derive_fernet_key, encrypt_bytes


class RuntimePackageService:
    def load_plain_package(self, package_record: dict) -> bytes:
        return Path(package_record["package_path"]).read_bytes()

    def encrypt_for_client(
        self,
        package_bytes: bytes,
        *,
        license_key: str,
        hwid: str,
        server_salt: str,
        version: str,
    ) -> str:
        k1 = derive_fernet_key(license_key, hwid, server_salt, version, layer="L1")
        k2 = derive_fernet_key(license_key, hwid, server_salt, version, layer="L2")
        inner = encrypt_bytes(package_bytes, key=k1)
        outer = encrypt_bytes(inner, key=k2)
        return base64.b64encode(outer).decode("ascii")
