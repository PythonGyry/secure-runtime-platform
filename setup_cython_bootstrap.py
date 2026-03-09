"""
Build Cython extensions for bootstrap (package_unwrap, runtime_crypto).
Run from project root: python setup_cython_bootstrap.py build_ext --inplace

Requires: pip install cython, and a C compiler:
  - Linux: gcc (apt install build-essential / yum groupinstall "Development Tools")
  - macOS: Xcode Command Line Tools (xcode-select --install)
  - Windows: Microsoft C++ Build Tools (MSVC) or MSYS2 + MinGW (client\\build_cython_with_msys2.bat)
If build fails, bootstrap falls back to .py sources (XOR obfuscation + double encryption).
"""
from __future__ import annotations

from pathlib import Path

from setuptools import Extension, setup

try:
    from Cython.Build import cythonize
except ImportError:
    raise SystemExit("Install Cython: pip install cython")

root = Path(__file__).resolve().parent
extensions = [
    Extension(
        "client.src.security.package_unwrap",
        [str(root / "client" / "src" / "security" / "package_unwrap.py")],
    ),
    Extension(
        "shared.crypto.runtime_crypto",
        [str(root / "shared" / "crypto" / "runtime_crypto.py")],
    ),
]

setup(
    name="bootstrap_cython",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
        },
    ),
)
