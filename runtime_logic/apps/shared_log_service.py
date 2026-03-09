"""
Спільний сервіс логів для всіх апок у runtime_logic/apps.
Пише в БД через передану функцію append_log або в консоль у debug-режимі.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional


def _format_line(message: str, level: str) -> str:
    if message.startswith("["):
        return message
    timestamp = datetime.now().strftime("%H:%M:%S")
    return f"[{timestamp}] [{level}] {message}"


class SharedLogService:
    def __init__(
        self,
        append_log_fn: Callable[..., None],
        callback: Optional[Callable[[str, str], None]] = None,
        debug: bool = False,
        **append_log_kwargs: str,
    ) -> None:
        self._append_log_fn = append_log_fn
        self._append_log_kwargs = append_log_kwargs
        self.callback = callback
        self.debug = debug

    def set_callback(self, callback: Callable[[str, str], None]) -> None:
        self.callback = callback

    def _append(self, level: str, message: str) -> None:
        if self.debug:
            print(message)
        else:
            self._append_log_fn(level, message, **self._append_log_kwargs)

    def log(self, message: str, level: str = "INFO") -> None:
        final_message = _format_line(message, level)
        self._append(level, final_message)
        if self.callback:
            self.callback(final_message, level)

    def log_with_details(
        self,
        user_message: str,
        detail_for_storage: str | None = None,
        level: str = "ERROR",
    ) -> None:
        """Пише в БД детальний лог (detail_for_storage), користувачу показує лише user_message. У debug — у консоль обидва."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        short_line = f"[{timestamp}] [{level}] {user_message}"
        if detail_for_storage:
            detail_line = f"[{timestamp}] [{level}] {user_message}\n{detail_for_storage}"
            self._append(level, detail_line)
            # У debug _append вже виводить detail_line — не дублюємо detail_for_storage
        else:
            self._append(level, short_line)
        if self.callback:
            self.callback(short_line, level)
