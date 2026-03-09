# -*- mode: python ; coding: utf-8 -*-
# exe_name задається через client/build_config.py (записує build_client_exe.py --name)

import sys
from pathlib import Path

project_root = Path.cwd().resolve()
sys.path.insert(0, str(project_root))
try:
    from client.build_config import exe_name
except ImportError:
    exe_name = "bootstrap"

client_entry = project_root / "client" / "src" / "main.py"
icons_dir = project_root / "client" / "icons"

# Іконка: build_icon.txt (якщо -a app) > verified.ico > wishlist. БЕЗ -a — тільки verified.ico
_icon_file = project_root / "client" / "build_icon.txt"
_icon_path = _icon_file.read_text(encoding="utf-8").strip() if _icon_file.exists() else ""
if _icon_path and Path(_icon_path).exists():
    verified_ico = Path(_icon_path).resolve()
else:
    verified_ico = (icons_dir / "verified.ico").resolve()
    if not verified_ico.exists():
        verified_ico = (project_root / "runtime_logic" / "apps" / "wishlist" / "icon.ico").resolve()

a = Analysis(
    [str(client_entry)],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(verified_ico), "icons")] if verified_ico.exists() else [],
    hiddenimports=[
        "requests",
        "urllib3",
        "certifi",
        "charset_normalizer",
        "client.src.bootstrap.application",
        "client.src.bootstrap.license_client",
        "client.src.bootstrap.package_downloader",
        "client.src.bootstrap.package_verifier",
        "client.src.bootstrap.state_store",
        "client.src.config.bootstrap_settings",
        "client.src.launcher.runtime_launcher",
        "client.src.launcher.memory_loader",
        "client.src.security.device",
        "client.src.security.dpapi",
        "client.src.security.package_unwrap",
        "client.src.ui.connection_error_dialog",
        "client.src.ui.icon_resolver",
        "client.src.ui.input_shortcuts",
        "client.src.ui.license_dialog",
        "shared.contracts.runtime_manifest",
        "shared.crypto.runtime_crypto",
        "socks",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.scrolledtext",
        "tkinter.ttk",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exe_name,
    icon=str(verified_ico) if verified_ico.exists() else None,  # client/icons/verified.ico
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
