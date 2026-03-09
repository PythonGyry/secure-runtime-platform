"""
Повна перезбірка: делегує до manager.py full.

Використання:
  python rebuild.py
  python rebuild.py -a wishlist -v 1.0.7
  python rebuild.py --all -v 1.0.8
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    project = Path(__file__).resolve().parent
    cmd = [sys.executable, str(project / "manager.py"), "full", *sys.argv[1:]]
    sys.exit(subprocess.run(cmd, cwd=project).returncode)
