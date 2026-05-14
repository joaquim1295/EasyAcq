"""Notificação leve («toast») na janela principal + alerta sonoro (Windows)."""
from __future__ import annotations

import sys
import threading
import tkinter as tk
from tkinter import ttk


def play_timer_finished_chime() -> None:
    """Sinal sonoro curto; só em Windows (winsound). Falhas são ignoradas."""
    if sys.platform != "win32":
        return
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONASTERISK)

        def _beep() -> None:
            try:
                winsound.Beep(1000, 120)
                winsound.Beep(800, 120)
            except Exception:
                pass

        threading.Thread(target=_beep, daemon=True).start()
    except Exception:
        pass


def show_toast(
    parent: tk.Misc,
    title: str,
    message: str,
    *,
    duration_ms: int = 5000,
) -> None:
    """Mostra um cartão temporário no canto inferior direito do ecrã do parent."""
    top = tk.Toplevel(parent)
    top.overrideredirect(True)
    try:
        top.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        top.attributes("-alpha", 0.94)
    except tk.TclError:
        pass

    frame = ttk.Frame(top, padding=(14, 10))
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
    ttk.Label(frame, text=message, wraplength=320, justify="left").pack(anchor="w", pady=(6, 0))

    def _place() -> None:
        parent.update_idletasks()
        top.update_idletasks()
        pw = int(parent.winfo_width()) or 800
        ph = int(parent.winfo_height()) or 600
        px = int(parent.winfo_rootx())
        py = int(parent.winfo_rooty())
        tw = top.winfo_reqwidth()
        th = top.winfo_reqheight()
        margin = 16
        x = px + pw - tw - margin
        y = py + ph - th - margin
        top.geometry(f"+{max(px, x)}+{max(py, y)}")

    top.after_idle(_place)
    top.after(duration_ms, top.destroy)
