import sys
import traceback
from pathlib import Path

from client.src.bootstrap.application import BootstrapApplication
from client.src.security.anti_debug import check_anti_debug


def _log_error(msg: str) -> None:
    if getattr(sys, "frozen", False):
        log_path = Path(sys.executable).parent / "bootstrap_error.log"
        try:
            log_path.write_text(msg, encoding="utf-8")
        except Exception:
            pass
    print(msg, file=sys.stderr)


def main() -> None:
    if getattr(sys, "frozen", False):
        check_anti_debug()
    try:
        BootstrapApplication().run()
    except Exception:
        msg = traceback.format_exc()
        _log_error(msg)
        traceback.print_exc()
        if getattr(sys, "frozen", False):
            try:
                input("Натисніть Enter для виходу...")
            except (RuntimeError, OSError, EOFError):
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
