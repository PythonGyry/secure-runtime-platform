from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, Union

from client.src.launcher.memory_loader import install_memory_finder, uninstall_memory_finder


class RuntimeLauncher:
    def launch(
        self,
        runtime_source: Union[Path, bytes],
        module_name: str,
        entrypoint: str,
        context: Dict[str, Any],
    ) -> None:
        if isinstance(runtime_source, bytes):
            self._launch_from_memory(runtime_source, module_name, entrypoint, context)
        else:
            self._launch_from_disk(runtime_source, module_name, entrypoint, context)

    def _launch_from_memory(
        self,
        zip_bytes: bytes,
        module_name: str,
        entrypoint: str,
        context: Dict[str, Any],
    ) -> None:
        finder = install_memory_finder(zip_bytes)
        try:
            module = importlib.import_module(module_name)
            target = getattr(module, entrypoint)
            target(context)
        finally:
            uninstall_memory_finder(finder)

    def _launch_from_disk(
        self,
        runtime_dir: Path,
        module_name: str,
        entrypoint: str,
        context: Dict[str, Any],
    ) -> None:
        runtime_path = str(runtime_dir)
        if runtime_path not in sys.path:
            sys.path.insert(0, runtime_path)

        module = importlib.import_module(module_name)
        target = getattr(module, entrypoint)
        target(context)
