from __future__ import annotations

from datetime import datetime, timedelta

from shared.contracts.runtime_manifest import RuntimeManifest
from shared.crypto.runtime_crypto import sign_payload


class ManifestService:
    def create(self, package_record: dict, *, key_record: dict, server_salt: str) -> tuple[dict, str]:
        manifest = RuntimeManifest(
            version=package_record["version"],
            channel=package_record.get("channel", "stable"),
            module_name=package_record["module_name"],
            entrypoint=package_record["entrypoint"],
            package_sha256=package_record["package_sha256"],
            package_size=int(package_record["package_size"]),
            generated_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(minutes=10)).isoformat(),
            server_salt=server_salt,
            key_id=key_record["key_id"],
        ).to_dict()
        signature = sign_payload(manifest, key_record["private_key_b64"])
        return manifest, signature
