"""
Видаляє/перейменовує старі розширення Cython перед збіркою:
- Windows: .pyd (уникнення 'Access is denied')
- Linux (та ін.): .so
Якщо файл заблокований — спочатку перейменовує в .old (на Windows часто працює).
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TARGETS = [
    PROJECT / "client" / "src" / "security",
    PROJECT / "shared" / "crypto",
]
# Windows: .pyd; Linux/ін.: .so (Cython build_ext --inplace)
if sys.platform == "win32":
    PATTERNS = ["package_unwrap.*.pyd", "runtime_crypto.*.pyd"]
    OLD_PATTERNS = ["package_unwrap.*.pyd.old", "runtime_crypto.*.pyd.old"]
else:
    PATTERNS = ["package_unwrap.*.so", "runtime_crypto.*.so"]
    OLD_PATTERNS = ["package_unwrap.*.so.old", "runtime_crypto.*.so.old"]


def _clear_ext(p: Path) -> bool:
    """Повертає True якщо файл прибрано (видалено або перейменовано)."""
    try:
        p.unlink()
        return True
    except PermissionError:
        pass
    # Спробувати перейменувати — на Windows часто працює навіть при блокуванні
    old_name = p.with_suffix(p.suffix + ".old")
    try:
        p.rename(old_name)
        return True
    except OSError as e:
        print(
            f"ERROR: Cannot remove or rename {p}: {e}\n"
            "Close any running: bootstrap.exe, Python, Cursor/IDE, tests. Then retry.",
            file=sys.stderr,
        )
        return False


def main() -> int:
    # Спочатку видалити старі *.old (зазвичай не заблоковані)
    for base in TARGETS:
        if not base.exists():
            continue
        for pat in OLD_PATTERNS:
            for p in base.glob(pat):
                try:
                    p.unlink()
                except OSError:
                    pass
    cleared = []
    for base in TARGETS:
        if not base.exists():
            continue
        for pat in PATTERNS:
            for p in base.glob(pat):
                if _clear_ext(p):
                    cleared.append(str(p))
                else:
                    return 1
    if cleared:
        ext = "pyd" if sys.platform == "win32" else "so"
        print("Cleared old ." + ext + ":", ", ".join(cleared))
    return 0


if __name__ == "__main__":
    sys.exit(main())
