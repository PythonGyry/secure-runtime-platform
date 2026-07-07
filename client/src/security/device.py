from __future__ import annotations

import hashlib
import subprocess
import sys
import uuid
from functools import lru_cache
from pathlib import Path

_STABLE_PREFIX = "s1:"


def _normalize_stable_id(value: str) -> str:
    return (value or "").strip().lower()


def _windows_machine_guid() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
        if value:
            return _normalize_stable_id(str(value))
    except Exception:
        return None
    return None


def _mac_platform_uuid() -> str | None:
    if sys.platform != "darwin":
        return None
    try:
        proc = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode != 0:
            return None
        for line in proc.stdout.splitlines():
            if "IOPlatformUUID" not in line:
                continue
            parts = line.split('"')
            if len(parts) >= 4:
                candidate = _normalize_stable_id(parts[3])
                if candidate:
                    return candidate
    except Exception:
        return None
    return None


def _linux_machine_id() -> str | None:
    if sys.platform not in ("linux", "linux2"):
        return None
    for path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            if path.is_file():
                text = path.read_text(encoding="utf-8").strip()
                if text:
                    return _normalize_stable_id(text)
        except Exception:
            continue
    return None


def _read_stable_machine_id() -> str | None:
    for reader in (_windows_machine_guid, _mac_platform_uuid, _linux_machine_id):
        value = reader()
        if value:
            return value
    return None


@lru_cache(maxsize=1)
def get_legacy_hwid() -> str:
    """MAC-based HWID (v0). Kept for license/DB migration from older builds."""
    return str(uuid.getnode())


@lru_cache(maxsize=1)
def get_hwid() -> str:
    """
    Stable machine id (v1): Windows MachineGuid, macOS IOPlatformUUID, Linux machine-id.
    Falls back to legacy MAC id if OS-specific id is unavailable.
    """
    stable = _read_stable_machine_id()
    if stable:
        return f"{_STABLE_PREFIX}{stable}"
    return get_legacy_hwid()


def is_stable_hwid(hwid: str) -> bool:
    return (hwid or "").startswith(_STABLE_PREFIX)


def hwid_fingerprint(hwid: str) -> str:
    """Short stable label for logs/meta (not secret)."""
    digest = hashlib.sha256((hwid or "").encode("utf-8")).hexdigest()
    return digest[:16]
