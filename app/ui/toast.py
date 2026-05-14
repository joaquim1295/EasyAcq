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
    duration_ms: int = 5500,
) -> None:
    """Cartão temporário no canto inferior direito da janela principal (Tk).

    Em Windows, Toplevel com ``overrideredirect`` precisa de geometria explícita
    e ``deiconify``/``lift`` depois do layout; caso contrário pode ficar invisível.
    """
    top = tk.Toplevel(parent)
    top.withdraw()
    try:
        top.overrideredirect(True)
    except tk.TclError:
        pass
    try:
        top.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        if sys.platform == "win32":
            top.attributes("-alpha", 0.96)
    except tk.TclError:
        pass

    outer = ttk.Frame(top, relief="solid", borderwidth=1, padding=(14, 10))
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text=title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
    ttk.Label(outer, text=message, wraplength=300, justify="left").pack(anchor="w", pady=(6, 0))

    def _place_and_show() -> None:
        try:
            parent.update_idletasks()
            top.update_idletasks()
            pw = max(int(parent.winfo_width()), 240)
            ph = max(int(parent.winfo_height()), 200)
            px = int(parent.winfo_rootx())
            py = int(parent.winfo_rooty())
            tw = max(int(top.winfo_reqwidth()), 260)
            th = max(int(top.winfo_reqheight()), 72)
            margin = 16
            x = max(px, px + pw - tw - margin)
            y = max(py, py + ph - th - margin)
            top.geometry(f"{tw}x{th}+{x}+{y}")
            top.deiconify()
            top.lift()
            try:
                top.attributes("-topmost", True)
            except tk.TclError:
                pass
        except tk.TclError:
            try:
                top.destroy()
            except tk.TclError:
                pass

    top.after(1, _place_and_show)
    top.after(duration_ms, top.destroy)
