"""
Windows DPAPI wrapper for machine/user-bound encryption.

When available (Windows), protects data so it can only be decrypted
on the same machine by the same Windows user. Copying .runtime_data
to another machine will not work.
"""
from __future__ import annotations

import base64
import sys
from typing import Optional

_DPAPI_AVAILABLE: Optional[bool] = None


def _init_dpapi() -> bool:
    global _DPAPI_AVAILABLE
    if _DPAPI_AVAILABLE is not None:
        return _DPAPI_AVAILABLE
    if sys.platform != "win32":
        _DPAPI_AVAILABLE = False
        return False
    try:
        from ctypes import POINTER, Structure, byref, c_char, cast, create_string_buffer
        from ctypes.wintypes import DWORD

        windll = __import__("ctypes").windll  # type: ignore[attr-defined]
        kernel32 = windll.kernel32

        class DATA_BLOB(Structure):
            _fields_ = [("cbData", DWORD), ("pbData", POINTER(c_char))]

        # Test protect/unprotect
        test = b"dpapi_test"
        buf = create_string_buffer(test)
        blob_in = DATA_BLOB(len(test), cast(buf, POINTER(c_char)))
        blob_out = DATA_BLOB()
        if not windll.crypt32.CryptProtectData(
            byref(blob_in),
            None,
            None,
            None,
            None,
            0x01,  # CRYPTPROTECT_UI_FORBIDDEN
            byref(blob_out),
        ):
            _DPAPI_AVAILABLE = False
            return False
        # Free and verify unprotect
        kernel32.LocalFree(blob_out.pbData)
        _DPAPI_AVAILABLE = True
        return True
    except Exception:
        _DPAPI_AVAILABLE = False
        return False


def is_available() -> bool:
    return _init_dpapi()


def protect(data: bytes) -> bytes:
    """Encrypt data with DPAPI. Only works on Windows, same machine + user."""
    if not _init_dpapi():
        return data
    from ctypes import POINTER, Structure, byref, c_char, cast, create_string_buffer
    from ctypes.wintypes import DWORD

    windll = __import__("ctypes").windll  # type: ignore[attr-defined]
    kernel32 = windll.kernel32

    class DATA_BLOB(Structure):
        _fields_ = [("cbData", DWORD), ("pbData", POINTER(c_char))]

    buf = create_string_buffer(data)
    blob_in = DATA_BLOB(len(data), cast(buf, POINTER(c_char)))
    blob_out = DATA_BLOB()
    if not windll.crypt32.CryptProtectData(
        byref(blob_in),
        None,
        None,
        None,
        None,
        0x01,
        byref(blob_out),
    ):
        raise RuntimeError("DPAPI CryptProtectData failed")
    try:
        from ctypes import string_at
        return bytes(string_at(blob_out.pbData, blob_out.cbData))
    finally:
        kernel32.LocalFree(blob_out.pbData)


def unprotect(data: bytes) -> bytes:
    """Decrypt DPAPI-protected data."""
    if not _init_dpapi():
        return data
    from ctypes import POINTER, Structure, byref, c_char, cast, create_string_buffer
    from ctypes.wintypes import DWORD

    windll = __import__("ctypes").windll  # type: ignore[attr-defined]
    kernel32 = windll.kernel32

    class DATA_BLOB(Structure):
        _fields_ = [("cbData", DWORD), ("pbData", POINTER(c_char))]

    buf = create_string_buffer(data)
    blob_in = DATA_BLOB(len(data), cast(buf, POINTER(c_char)))
    blob_out = DATA_BLOB()
    if not windll.crypt32.CryptUnprotectData(
        byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        byref(blob_out),
    ):
        raise ValueError("DPAPI CryptUnprotectData failed (wrong machine/user?)")
    try:
        from ctypes import string_at
        return bytes(string_at(blob_out.pbData, blob_out.cbData))
    finally:
        kernel32.LocalFree(blob_out.pbData)


def protect_b64(data: bytes) -> str:
    """Protect and return base64 string."""
    return base64.b64encode(protect(data)).decode("ascii")


def unprotect_b64(s: str) -> bytes:
    """Decode base64 and unprotect."""
    return unprotect(base64.b64decode(s))
