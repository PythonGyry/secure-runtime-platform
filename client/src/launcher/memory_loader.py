"""
Load runtime modules from in-memory zip. No disk writes — code stays in RAM.
Makes extraction and decompilation significantly harder.
"""
from __future__ import annotations

import importlib.abc
import importlib.util
import marshal
import sys
import types
import zipfile
from io import BytesIO
from typing import Optional


def _find_pyc_in_zip(zf: zipfile.ZipFile, base_path: str, cache_tag: str) -> Optional[str]:
    """Find .pyc file for module. Tries cache_tag variant first, then .pyc."""
    candidates = [
        f"{base_path}.{cache_tag}.pyc",
        f"{base_path}.pyc",
    ]
    for name in candidates:
        try:
            zf.getinfo(name)
            return name
        except KeyError:
            pass
    return None


class ZipMemoryLoader(importlib.abc.Loader):
    def __init__(self, zip_bytes: bytes, cache_tag: str) -> None:
        self._zip_bytes = zip_bytes
        self._cache_tag = cache_tag
        self._zip = zipfile.ZipFile(BytesIO(zip_bytes), "r")

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> Optional[types.ModuleType]:
        return None  # Use default module creation

    def exec_module(self, module: types.ModuleType) -> None:
        # exec_module receives the module object, not the spec (PEP 451)
        module_name = getattr(module, "__name__", None) or getattr(
            getattr(module, "__spec__", None), "name", None
        )
        if not module_name:
            raise ImportError("Module has no __name__")
        is_package = getattr(module, "__path__", None) is not None
        if is_package:
            # Package __init__.py - empty in our build
            return
        base_path = module_name.replace(".", "/")
        pyc_name = _find_pyc_in_zip(self._zip, base_path, self._cache_tag)
        if not pyc_name:
            raise ImportError(f"Cannot find {module_name} in package")
        data = self._zip.read(pyc_name)
        # Python 3.7+ pyc header is 16 bytes
        if len(data) < 16:
            raise ImportError(f"Invalid pyc for {module_name}")
        code = marshal.loads(data[16:])
        exec(code, module.__dict__)


class ZipMemoryFinder(importlib.abc.MetaPathFinder):
    def __init__(self, zip_bytes: bytes) -> None:
        self._zip_bytes = zip_bytes
        self._zip = zipfile.ZipFile(BytesIO(zip_bytes), "r")
        self._cache_tag = sys.implementation.cache_tag
        self._names = {self._normalize(n) for n in self._zip.namelist()}

    def _normalize(self, name: str) -> str:
        return name.replace("\\", "/")

    def find_spec(
        self,
        fullname: str,
        path: Optional[list[str]],
        target: Optional[types.ModuleType] = None,
    ) -> Optional[importlib.machinery.ModuleSpec]:
        base_path = fullname.replace(".", "/")
        # Check for package (__init__.py)
        init_path = f"{base_path}/__init__.py"
        if self._normalize(init_path) in self._names:
            return importlib.util.spec_from_loader(
                fullname,
                ZipMemoryLoader(self._zip_bytes, self._cache_tag),
                origin="<memory>",
                is_package=True,
            )
        # Check for module (.pyc)
        pyc_name = _find_pyc_in_zip(self._zip, base_path, self._cache_tag)
        if pyc_name:
            return importlib.util.spec_from_loader(
                fullname,
                ZipMemoryLoader(self._zip_bytes, self._cache_tag),
                origin="<memory>",
                is_package=False,
            )
        return None


def install_memory_finder(zip_bytes: bytes) -> ZipMemoryFinder:
    """Add finder to sys.meta_path. Returns the finder for later removal."""
    finder = ZipMemoryFinder(zip_bytes)
    sys.meta_path.insert(0, finder)
    return finder


def uninstall_memory_finder(finder: ZipMemoryFinder) -> None:
    """Remove finder from sys.meta_path."""
    try:
        sys.meta_path.remove(finder)
    except ValueError:
        pass
