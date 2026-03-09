from __future__ import annotations

import base64
import hashlib
import importlib
import io
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict

_KEY = hashlib.sha256(b"wishlist_bootstrap_salt_v1").digest()
_M = bytes([189, 137, 255, 55, 60, 139, 17, 170, 113, 139, 168, 236, 0, 121, 193, 80, 184, 90, 174, 12, 120, 167, 223, 68, 117, 40, 87, 212])


def _d(b: bytes) -> str:
    return bytes(b[i] ^ _KEY[i % 32] for i in range(len(b))).decode("utf-8", errors="replace")


def _l() -> Any:
    return importlib.import_module(_d(_M))


def _r(m: Any, n: bytes) -> Any:
    return getattr(m, _d(n))


def _p(a: str, b: str, c: str, d: str, e: str = "") -> bytes:
    fn = _r(_l(), bytes([170, 132, 236, 44, 47, 138, 96, 175, 102, 128, 182, 253, 27, 8, 216, 64, 175]))
    return fn(a, b, c, d) if not e else fn(a, b, c, d, layer=e)


def _u(raw: bytes, k: bytes) -> bytes:
    return _r(_l(), bytes([170, 132, 253, 55, 32, 159, 75, 150, 97, 139, 172, 253, 28]))(raw, key=k)


def _c(data: bytes) -> str:
    return _r(_l(), bytes([189, 137, 255, 119, 108, 217, 96, 171, 122, 134, 189, 235]))(data)


def _unwrap_payload(
    *,
    encrypted_b64: str,
    license_key: str,
    hwid: str,
    server_salt: str,
    version: str,
    expected_sha256: str,
) -> bytes:
    """Decrypt and verify. Returns raw zip bytes. No disk I/O."""
    k2 = _p(license_key, hwid, server_salt, version, "L2")
    k1 = _p(license_key, hwid, server_salt, version, "L1")
    k0 = _p(license_key, hwid, server_salt, version)
    raw = base64.b64decode(encrypted_b64)
    try:
        inner = _u(raw, k2)
        payload = _u(inner, k1)
    except (ValueError, Exception):
        payload = _u(raw, k0)
    actual = _c(payload)
    if actual != expected_sha256:
        raise RuntimeError("Integrity check failed")
    return payload


def unwrap_to_memory(
    *,
    encrypted_b64: str,
    license_key: str,
    hwid: str,
    server_salt: str,
    version: str,
    expected_sha256: str,
) -> bytes:
    """Decrypt package to memory. Returns zip bytes. No disk write."""
    return _unwrap_payload(
        encrypted_b64=encrypted_b64,
        license_key=license_key,
        hwid=hwid,
        server_salt=server_salt,
        version=version,
        expected_sha256=expected_sha256,
    )


def unwrap_and_extract(
    *,
    encrypted_b64: str,
    license_key: str,
    hwid: str,
    server_salt: str,
    version: str,
    expected_sha256: str,
    target_dir: Path,
) -> Path:
    payload = _unwrap_payload(
        encrypted_b64=encrypted_b64,
        license_key=license_key,
        hwid=hwid,
        server_salt=server_salt,
        version=version,
        expected_sha256=expected_sha256,
    )
    extract_dir = target_dir / version
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        z.extractall(extract_dir)
    return extract_dir
