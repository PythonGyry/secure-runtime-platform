"""
Створює client/icons/verified.ico для exe. Джерело: apps/<app>/icon.ico.
Якщо Pillow є — multi-size (16..256). Інакше — копія.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", "-a", help="Апка (напр. wishlist) — іконка з runtime_logic/apps/<app>/icon.ico")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    icons_dir = project_root / "client" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)
    out_path = icons_dir / "verified.ico"

    if args.app:
        src = project_root / "runtime_logic" / "apps" / args.app / "icon.ico"
    else:
        wishlist_icon = project_root / "runtime_logic" / "apps" / "wishlist" / "icon.ico"
        src = out_path if out_path.exists() else (wishlist_icon if wishlist_icon.exists() else None)

    if not src or not src.exists():
        return 0

    try:
        from PIL import Image

        img = Image.open(src)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(out_path, format="ICO", sizes=sizes)
    except ImportError:
        shutil.copy2(src, out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
