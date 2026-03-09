"""Anti-debug checks for bootstrap. Windows only."""
from __future__ import annotations

import sys


def _is_debugger_present() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        return bool(kernel32.IsDebuggerPresent())
    except Exception:
        return False


def _is_debugger_process_running() -> bool:
    """Check for common debugger process names."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
        Process32FirstW = kernel32.Process32FirstW
        Process32NextW = kernel32.Process32NextW
        CloseHandle = kernel32.CloseHandle

        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE_VALUE = -1

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        debuggers = ("ollydbg", "x64dbg", "x32dbg", "ida", "ida64", "windbg", "devenv")
        h = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if h == INVALID_HANDLE_VALUE:
            return False
        try:
            pe = PROCESSENTRY32W()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            if not Process32FirstW(h, ctypes.byref(pe)):
                return False
            while True:
                name = pe.szExeFile.lower()
                if any(dbg in name for dbg in debuggers):
                    return True
                if not Process32NextW(h, ctypes.byref(pe)):
                    break
        finally:
            CloseHandle(h)
        return False
    except Exception:
        return False


def check_anti_debug() -> None:
    """Raise SystemExit if debugger is detected. Call early in main()."""
    if _is_debugger_present():
        sys.exit(1)
    if _is_debugger_process_running():
        sys.exit(1)
