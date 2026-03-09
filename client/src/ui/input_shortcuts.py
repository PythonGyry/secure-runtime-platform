from __future__ import annotations

import tkinter as tk
from typing import Callable


class StandardTextShortcuts:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.context_menu = tk.Menu(root, tearoff=0)
        self.context_menu.add_command(label="Вирізати (Ctrl+X)", command=lambda: self._dispatch(self._cut))
        self.context_menu.add_command(label="Копіювати (Ctrl+C)", command=lambda: self._dispatch(self._copy))
        self.context_menu.add_command(label="Вставити (Ctrl+V)", command=lambda: self._dispatch(self._paste))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Виділити все (Ctrl+A)", command=lambda: self._dispatch(self._select_all))

    def install(self) -> None:
        for widget_class in ("Entry", "TEntry", "Text"):
            for sequence in ("<Control-a>", "<Control-A>"):
                self.root.bind_class(widget_class, sequence, self._select_all, add="+")
            for sequence in ("<Control-c>", "<Control-C>", "<Control-Insert>"):
                self.root.bind_class(widget_class, sequence, self._copy, add="+")
            for sequence in ("<Control-v>", "<Control-V>", "<Shift-Insert>"):
                self.root.bind_class(widget_class, sequence, self._paste, add="+")
            for sequence in ("<Control-x>", "<Control-X>", "<Shift-Delete>"):
                self.root.bind_class(widget_class, sequence, self._cut, add="+")
            for sequence in ("<Button-3>", "<ButtonRelease-3>", "<Button-2>", "<ButtonRelease-2>"):
                self.root.bind_class(widget_class, sequence, self._show_context_menu, add="+")

    def _dispatch(self, handler: Callable[[tk.Event | None], str]) -> None:
        handler(None)

    def _focused_widget(self) -> tk.Misc | None:
        widget = self.root.focus_get()
        if widget is None:
            return None
        if widget.winfo_class() in {"Entry", "TEntry", "Text"}:
            return widget
        return None

    def _copy(self, _event: tk.Event | None) -> str:
        widget = self._focused_widget()
        if widget is None:
            return "break"
        widget.focus_set()
        widget.event_generate("<<Copy>>")
        return "break"

    def _paste(self, _event: tk.Event | None) -> str:
        widget = self._focused_widget()
        if widget is None:
            return "break"
        widget.focus_set()
        widget.event_generate("<<Paste>>")
        return "break"

    def _cut(self, _event: tk.Event | None) -> str:
        widget = self._focused_widget()
        if widget is None:
            return "break"
        widget.focus_set()
        widget.event_generate("<<Cut>>")
        return "break"

    def _select_all(self, _event: tk.Event | None) -> str:
        widget = self._focused_widget()
        if widget is None:
            return "break"
        widget.focus_set()
        if widget.winfo_class() == "Text":
            widget.tag_add(tk.SEL, "1.0", "end-1c")
            widget.mark_set(tk.INSERT, "end-1c")
            widget.see(tk.INSERT)
        else:
            widget.select_range(0, tk.END)
            widget.icursor(tk.END)
        return "break"

    def _show_context_menu(self, event: tk.Event) -> str:
        try:
            event.widget.focus_set()
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
        return "break"
