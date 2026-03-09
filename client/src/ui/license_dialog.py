from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from client.src.ui.icon_resolver import get_verified_icon_path
from client.src.ui.input_shortcuts import StandardTextShortcuts

if TYPE_CHECKING:
    from client.src.bootstrap.license_client import LicenseClient


def ask_license_key(
    *,
    status_message: str = "",
    status_color: str = "#ff4444",
    license_client: "LicenseClient | None" = None,
) -> str | None:
    """Show license dialog. If license_client provided, fetches program names from key."""
    root = tk.Tk()
    result: str | None = None

    # Neutral palette: calm, professional before key entry
    bg_color = "#f5f5f5"
    text_color = "#374151"
    muted_color = "#6b7280"
    border_color = "#d1d5db"
    input_bg = "#ffffff"
    # Accent only when apps are shown
    success_color = "#0d9488"
    error_color = "#b91c1c"
    button_fg = "#4b5563"
    button_hover = "#374151"

    root.title("License Activation")
    root.geometry("462x220+100+100")
    icon_path = get_verified_icon_path()
    if icon_path:
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass
    root.resizable(False, False)
    root.configure(bg=bg_color)

    container = tk.Frame(root, bg=bg_color)
    container.pack(fill="both", expand=True, padx=14, pady=12)

    tk.Label(
        container,
        text="License Activation",
        bg=bg_color,
        fg=text_color,
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w", pady=(0, 6))
    tk.Label(
        container,
        text="Enter license key to download and run the program.",
        bg=bg_color,
        fg=text_color,
        font=("Segoe UI", 9),
    ).pack(anchor="w")

    input_entry = tk.Entry(
        container,
        width=42,
        bg=bg_color,
        fg=text_color,
        insertbackground=text_color,
        font=("Courier New", 11),
        relief="solid",
        borderwidth=1,
        highlightthickness=1,
        highlightcolor="#ffffff",
        highlightbackground="#ffffff",
    )
    input_entry.pack(fill="x", pady=(10, 4))
    apps_label = tk.Label(
        container,
        text="",
        bg=bg_color,
        fg=muted_color,
        font=("Segoe UI", 9),
        # Stays muted until apps are fetched, then success_color
        justify="left",
        anchor="w",
        wraplength=420,
    )
    apps_label.pack(fill="x", pady=(0, 4))
    status_label = tk.Label(
        container,
        text="",
        bg=bg_color,
        fg=error_color,
        font=("Segoe UI", 9),
        justify="left",
        anchor="w",
        wraplength=420,
    )
    status_label.pack(fill="x")

    def set_status(message: str, color: str | None = None) -> None:
        status_label.config(text=message, fg=color or error_color)

    def set_apps(apps: list[str]) -> None:
        if apps:
            names = [a.capitalize() for a in apps]
            apps_label.config(text=f"Programs: {', '.join(names)}", fg=success_color)
        else:
            apps_label.config(text="", fg=muted_color)

    _fetch_job: str | None = None

    def fetch_license_info() -> None:
        nonlocal _fetch_job
        key = input_entry.get().strip()
        if not key or not license_client:
            set_apps([])
            return
        if _fetch_job:
            root.after_cancel(_fetch_job)
        def do_fetch() -> None:
            nonlocal _fetch_job
            _fetch_job = None
            try:
                info = license_client.get_license_info(key)
                if info.get("valid") and info.get("apps"):
                    set_apps(info["apps"])
                else:
                    set_apps([])
            except Exception:
                set_apps([])
        _fetch_job = root.after(400, do_fetch)

    def on_key_change(*_args: object) -> None:
        key = input_entry.get().strip()
        if not key:
            set_apps([])
            return
        fetch_license_info()

    input_entry.bind("<KeyRelease>", on_key_change)
    input_entry.bind("<FocusOut>", lambda e: fetch_license_info())

    def submit() -> None:
        nonlocal result
        value = input_entry.get().strip()
        if not value:
            set_status("License key cannot be empty.")
            input_entry.focus_set()
            return
        result = value
        root.destroy()

    def cancel() -> None:
        nonlocal result
        result = None
        root.destroy()

    buttons = tk.Frame(container, bg=bg_color)
    buttons.pack(anchor="e", pady=(12, 0))
    tk.Button(
        buttons,
        text="Verify",
        command=submit,
        bg=input_bg,
        fg=button_fg,
        activebackground=border_color,
        activeforeground=button_hover,
        font=("Segoe UI", 9),
        relief="solid",
        borderwidth=1,
        highlightthickness=1,
        highlightcolor=border_color,
        highlightbackground=border_color,
        cursor="hand2",
    ).grid(row=0, column=0, padx=5)
    tk.Button(
        buttons,
        text="Cancel",
        command=cancel,
        bg=input_bg,
        fg=muted_color,
        activebackground=border_color,
        activeforeground=button_hover,
        font=("Segoe UI", 9),
        relief="solid",
        borderwidth=1,
        highlightthickness=1,
        highlightcolor=border_color,
        highlightbackground=border_color,
        cursor="hand2",
    ).grid(row=0, column=1, padx=5)

    shortcuts = StandardTextShortcuts(root)
    shortcuts.install()

    if status_message:
        set_status(status_message, status_color)

    root.protocol("WM_DELETE_WINDOW", cancel)
    root.bind("<Return>", lambda _: submit(), add="+")
    input_entry.focus_set()

    root.lift()
    root.focus_force()
    root.attributes("-topmost", True)
    root.after(100, lambda: root.attributes("-topmost", False))

    root.mainloop()
    return result


def ask_app_choice(apps: list[str]) -> str | None:
    """Показати меню вибору апки кнопками. Повертає обрану апку або None при скасуванні."""
    if not apps:
        return None
    if len(apps) == 1:
        return apps[0]

    root = tk.Tk()
    result: str | None = None
    bg_color = "#f5f5f5"
    text_color = "#374151"
    muted_color = "#6b7280"
    border_color = "#d1d5db"
    accent = "#0d9488"

    root.title("Оберіть програму")
    root.geometry("360x120+150+150")
    root.resizable(False, False)
    root.configure(bg=bg_color)
    icon_path = get_verified_icon_path()
    if icon_path:
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass

    container = tk.Frame(root, bg=bg_color)
    container.pack(fill="both", expand=True, padx=16, pady=12)

    tk.Label(
        container,
        text="Ліцензія дає доступ до кількох програм. Оберіть, яку запустити:",
        bg=bg_color,
        fg=text_color,
        font=("Segoe UI", 9),
    ).pack(anchor="w", pady=(0, 10))

    buttons_frame = tk.Frame(container, bg=bg_color)
    buttons_frame.pack(fill="x")

    def make_choice(app_id: str) -> None:
        nonlocal result
        result = app_id
        root.destroy()

    for i, app_id in enumerate(apps):
        label = app_id.capitalize()
        btn = tk.Button(
            buttons_frame,
            text=label,
            command=lambda a=app_id: make_choice(a),
            bg="white",
            fg=text_color,
            activebackground=border_color,
            activeforeground=text_color,
            font=("Segoe UI", 10),
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
            highlightcolor=accent,
            highlightbackground=border_color,
            cursor="hand2",
            width=14,
        )
        btn.grid(row=0, column=i, padx=6, pady=0)

    tk.Button(
        buttons_frame,
        text="Скасувати",
        command=lambda: make_choice("__cancel__"),
        bg=bg_color,
        fg=muted_color,
        font=("Segoe UI", 9),
        relief="flat",
        cursor="hand2",
    ).grid(row=1, column=0, columnspan=len(apps), pady=(12, 0))

    shortcuts = StandardTextShortcuts(root)
    shortcuts.install()
    root.protocol("WM_DELETE_WINDOW", lambda: make_choice("__cancel__"))
    root.lift()
    root.focus_force()
    root.mainloop()
    return None if result == "__cancel__" else result
