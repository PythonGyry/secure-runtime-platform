from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from client.src.ui.icon_resolver import get_verified_icon_path
from client.src.ui.input_shortcuts import StandardTextShortcuts

if TYPE_CHECKING:
    from client.src.bootstrap.license_client import LicenseClient

TG_USERNAME = "inceglist"
TG_LINK = "https://t.me/inceglist"

_DEVICE_BOUND_MARKERS = (
    "DEVICE_BOUND",
    "already bound to another device",
    "прив'язана до іншого пристрою",
    "привʼязана до іншого пристрою",
)


def _is_device_bound_error(*, message: str = "", error_code: str = "") -> bool:
    code = (error_code or "").strip().upper()
    if code == "DEVICE_BOUND":
        return True
    text = (message or "").lower()
    return any(marker.lower() in text for marker in _DEVICE_BOUND_MARKERS)


def ask_license_key(
    *,
    status_message: str = "",
    status_color: str = "#ff4444",
    status_error_code: str = "",
    bound_device: str = "",
    initial_key: str = "",
    license_client: "LicenseClient | None" = None,
    hwid: str = "",
) -> str | None:
    """Показати діалог активації ліцензії (стиль NBU: чорний термінал)."""
    root = tk.Tk()
    result: str | None = None

    bg_color = "#000000"
    panel_color = "#0a0a0a"
    text_color = "#ffffff"
    muted_color = "#888888"
    border_color = "#333333"
    accent = "#00ff00"
    warn_color = "#ffaa00"
    error_color = "#ff4444"
    font_ui = ("Courier New", 10)
    font_title = ("Courier New", 12, "bold")
    font_input = ("Courier New", 12)

    root.title("Активація ліцензії")
    root.geometry("520x320+100+100")
    icon_path = get_verified_icon_path()
    if icon_path:
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass
    root.resizable(False, False)
    root.configure(bg=bg_color)

    outer = tk.Frame(root, bg=bg_color, highlightbackground=accent, highlightthickness=1)
    outer.pack(fill="both", expand=True, padx=10, pady=10)

    container = tk.Frame(outer, bg=bg_color)
    container.pack(fill="both", expand=True, padx=16, pady=14)

    tk.Label(
        container,
        text="NBU  ·  Активація ліцензії",
        bg=bg_color,
        fg=accent,
        font=font_title,
        anchor="w",
    ).pack(fill="x", pady=(0, 4))

    tk.Label(
        container,
        text="Введіть ліцензійний ключ, щоб завантажити та запустити програму.",
        bg=bg_color,
        fg=muted_color,
        font=font_ui,
        anchor="w",
        justify="left",
        wraplength=470,
    ).pack(fill="x", pady=(0, 12))

    tk.Label(
        container,
        text="Ключ",
        bg=bg_color,
        fg=muted_color,
        font=("Courier New", 8),
        anchor="w",
    ).pack(fill="x")

    input_wrap = tk.Frame(container, bg=border_color, padx=1, pady=1)
    input_wrap.pack(fill="x", pady=(2, 6))
    input_entry = tk.Entry(
        input_wrap,
        bg=panel_color,
        fg=text_color,
        insertbackground=accent,
        font=font_input,
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
    )
    input_entry.pack(fill="x", ipady=8, padx=8)
    if initial_key:
        input_entry.insert(0, initial_key.strip())

    apps_label = tk.Label(
        container,
        text="",
        bg=bg_color,
        fg=muted_color,
        font=font_ui,
        justify="left",
        anchor="w",
        wraplength=470,
    )
    apps_label.pack(fill="x", pady=(0, 4))

    status_label = tk.Label(
        container,
        text="",
        bg=bg_color,
        fg=error_color,
        font=font_ui,
        justify="left",
        anchor="w",
        wraplength=470,
    )
    status_label.pack(fill="x")

    rebind_frame = tk.Frame(container, bg=bg_color)
    rebind_frame.pack(fill="x", pady=(8, 0))
    rebind_hint = tk.Label(
        rebind_frame,
        text="",
        bg=bg_color,
        fg=warn_color,
        font=("Courier New", 9),
        justify="left",
        anchor="w",
        wraplength=470,
    )
    rebind_hint.pack(fill="x", pady=(0, 6))
    rebind_btn = tk.Button(
        rebind_frame,
        text="Відв'язати пристрій і прив'язати цей",
        bg=bg_color,
        fg=warn_color,
        activebackground="#1a1a1a",
        activeforeground=accent,
        font=("Courier New", 9, "bold"),
        relief="solid",
        borderwidth=1,
        highlightthickness=0,
        cursor="hand2",
        padx=10,
        pady=4,
    )

    def set_status(message: str, color: str | None = None) -> None:
        status_label.config(text=message, fg=color or error_color)

    def set_apps(apps: list[str]) -> None:
        if apps:
            names = [a.capitalize() for a in apps]
            apps_label.config(text=f"Доступні програми: {', '.join(names)}", fg=accent)
        else:
            apps_label.config(text="", fg=muted_color)

    def hide_rebind() -> None:
        rebind_hint.config(text="")
        rebind_btn.pack_forget()

    def show_rebind(*, device_hint: str = "") -> None:
        if device_hint:
            rebind_hint.config(
                text=(
                    f"Раніше була на пристрої: {device_hint}\n"
                    "Можна перенести ліцензію на цей ПК.\n"
                    f"Якщо не виходить — напишіть у Telegram @{TG_USERNAME}."
                )
            )
        else:
            rebind_hint.config(
                text=(
                    "Ліцензія була на іншому ПК — можна перенести сюди.\n"
                    f"Якщо не виходить — напишіть у Telegram @{TG_USERNAME}."
                )
            )
        rebind_btn.pack(anchor="w")

    def apply_bound_state(*, message: str = "", error_code: str = "", device_hint: str = "") -> None:
        text = message or "Ліцензія вже прив'язана до іншого пристрою"
        set_status(text, warn_color)
        if _is_device_bound_error(message=text, error_code=error_code):
            show_rebind(device_hint=device_hint)
        else:
            hide_rebind()

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
        hide_rebind()
        if status_label.cget("text"):
            set_status("")
        key = input_entry.get().strip()
        if not key:
            set_apps([])
            return
        fetch_license_info()

    input_entry.bind("<KeyRelease>", on_key_change)
    input_entry.bind("<FocusOut>", lambda _e: fetch_license_info())

    def submit() -> None:
        nonlocal result
        value = input_entry.get().strip()
        if not value:
            set_status("Ліцензійний ключ не може бути порожнім.")
            input_entry.focus_set()
            return
        result = value
        root.destroy()

    def cancel() -> None:
        nonlocal result
        result = None
        root.destroy()

    def do_rebind() -> None:
        key = input_entry.get().strip()
        if not key:
            set_status("Спочатку введіть ліцензійний ключ.")
            input_entry.focus_set()
            return
        if not license_client or not (hwid or "").strip():
            set_status("Неможливо відв'язати пристрій зараз. Спробуйте ще раз.")
            return
        rebind_btn.config(state="disabled", text="Відв'язую…")
        set_status("Відв'язую попередній пристрій…", muted_color)
        root.update_idletasks()
        try:
            response = license_client.rebind_license(key, hwid)
        except Exception as exc:
            rebind_btn.config(state="normal", text="Відв'язати пристрій і прив'язати цей")
            set_status(f"Помилка відв'язки: {exc}", error_color)
            return
        if not response.get("ok"):
            rebind_btn.config(state="normal", text="Відв'язати пристрій і прив'язати цей")
            set_status(response.get("message") or "Не вдалося відв'язати пристрій.", error_color)
            return
        hide_rebind()
        set_status(response.get("message") or "Пристрій відв'язано. Активуємо…", accent)
        root.after(250, submit)

    rebind_btn.config(command=do_rebind)

    buttons = tk.Frame(container, bg=bg_color)
    buttons.pack(anchor="e", side="bottom", pady=(16, 0))

    def _mk_btn(parent: tk.Misc, text: str, command, *, primary: bool = False) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg_color,
            fg=accent if primary else muted_color,
            activebackground="#1a1a1a",
            activeforeground=accent,
            font=("Courier New", 9, "bold" if primary else "normal"),
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
            cursor="hand2",
            padx=14,
            pady=5,
        )

    _mk_btn(buttons, "[ Перевірити ]", submit, primary=True).grid(row=0, column=0, padx=(0, 8))
    _mk_btn(buttons, "[ Скасувати ]", cancel).grid(row=0, column=1)

    shortcuts = StandardTextShortcuts(root)
    shortcuts.install()

    if status_message or status_error_code:
        apply_bound_state(
            message=status_message,
            error_code=status_error_code,
            device_hint=bound_device,
        )
        if not _is_device_bound_error(message=status_message, error_code=status_error_code):
            set_status(status_message, status_color)
    elif initial_key:
        fetch_license_info()

    root.protocol("WM_DELETE_WINDOW", cancel)
    root.bind("<Return>", lambda _: submit(), add="+")
    input_entry.focus_set()
    if initial_key:
        input_entry.selection_range(0, "end")
        input_entry.icursor("end")

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
    bg_color = "#000000"
    text_color = "#ffffff"
    muted_color = "#888888"
    border_color = "#333333"
    accent = "#00ff00"

    root.title("Оберіть програму")
    root.geometry("420x160+150+150")
    root.resizable(False, False)
    root.configure(bg=bg_color)
    icon_path = get_verified_icon_path()
    if icon_path:
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass

    outer = tk.Frame(root, bg=bg_color, highlightbackground=accent, highlightthickness=1)
    outer.pack(fill="both", expand=True, padx=10, pady=10)
    container = tk.Frame(outer, bg=bg_color)
    container.pack(fill="both", expand=True, padx=14, pady=12)

    tk.Label(
        container,
        text="Ліцензія дає доступ до кількох програм.\nОберіть, яку запустити:",
        bg=bg_color,
        fg=text_color,
        font=("Courier New", 9),
        justify="left",
        anchor="w",
    ).pack(anchor="w", pady=(0, 12))

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
            text=f"[ {label} ]",
            command=lambda a=app_id: make_choice(a),
            bg=bg_color,
            fg=accent,
            activebackground="#1a1a1a",
            activeforeground=accent,
            font=("Courier New", 10, "bold"),
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
            cursor="hand2",
            width=14,
        )
        btn.grid(row=0, column=i, padx=6, pady=0)

    tk.Button(
        buttons_frame,
        text="[ Скасувати ]",
        command=lambda: make_choice("__cancel__"),
        bg=bg_color,
        fg=muted_color,
        activebackground="#1a1a1a",
        activeforeground=muted_color,
        font=("Courier New", 9),
        relief="flat",
        cursor="hand2",
        highlightthickness=0,
    ).grid(row=1, column=0, columnspan=len(apps), pady=(14, 0))

    shortcuts = StandardTextShortcuts(root)
    shortcuts.install()
    root.protocol("WM_DELETE_WINDOW", lambda: make_choice("__cancel__"))
    root.lift()
    root.focus_force()
    root.mainloop()
    return None if result == "__cancel__" else result
