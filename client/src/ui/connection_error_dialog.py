"""Connection error window with contact info and clickable Telegram link."""
from __future__ import annotations

import webbrowser

import tkinter as tk

from client.src.ui.icon_resolver import get_verified_icon_path

TG_LINK = "https://t.me/inceglist"
TG_USERNAME = "inceglist"


def show_connection_error(server_url: str) -> None:
    """Show connection error window with contact info. Blocks until user closes."""
    root = tk.Tk()
    root.title("Немає підключення")
    root.geometry("420x220")
    root.resizable(False, False)

    icon_path = get_verified_icon_path()
    if icon_path:
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass

    bg = "#f5f5f5"
    text_color = "#374151"
    error_color = "#b91c1c"
    link_color = "#2563eb"

    root.configure(bg=bg)

    main = tk.Frame(root, bg=bg, padx=24, pady=20)
    main.pack(fill="both", expand=True)

    tk.Label(
        main,
        text="Не вдалося підключитися до сервера",
        bg=bg,
        fg=error_color,
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w", pady=(0, 4))

    tk.Label(
        main,
        text=server_url or "сервер",
        bg=bg,
        fg=text_color,
        font=("Segoe UI", 9),
    ).pack(anchor="w", pady=(0, 16))

    tk.Label(
        main,
        text="Зверніться до мене, якщо помилка не зникла після перезапуску чи перезавантаження ПК.",
        bg=bg,
        fg=text_color,
        font=("Segoe UI", 10),
        wraplength=360,
        justify="left",
    ).pack(anchor="w", pady=(0, 12))

    link_frame = tk.Frame(main, bg=bg)
    link_frame.pack(anchor="w", pady=(0, 20))

    tk.Label(
        link_frame,
        text="Telegram: ",
        bg=bg,
        fg=text_color,
        font=("Segoe UI", 10),
    ).pack(side="left")

    link_label = tk.Label(
        link_frame,
        text=TG_USERNAME,
        bg=bg,
        fg=link_color,
        font=("Segoe UI", 10, "underline"),
        cursor="hand2",
    )
    link_label.pack(side="left")

    def _open_tg() -> None:
        webbrowser.open(TG_LINK)

    link_label.bind("<Button-1>", lambda e: _open_tg())
    link_label.bind("<Enter>", lambda e: link_label.config(fg="#1d4ed8"))
    link_label.bind("<Leave>", lambda e: link_label.config(fg=link_color))

    tk.Button(
        main,
        text="OK",
        command=root.destroy,
        font=("Segoe UI", 10),
        width=10,
        bg="#e5e7eb",
        fg=text_color,
        relief="flat",
        padx=16,
        pady=6,
        cursor="hand2",
    ).pack(anchor="e")

    root.mainloop()
