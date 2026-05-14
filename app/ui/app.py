from __future__ import annotations

import bisect
import logging
import math
import threading
import time
import tkinter as tk
from collections import deque
from datetime import datetime
from pathlib import Path
from queue import Empty, Full, Queue
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, Optional

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, ScalarFormatter

from app.config import AppConfig
from app.core.bus import EventBus
from app.core.events import ReadingEvent, StatusEvent
from app.core.supervisor import Supervisor
from app.services.chart_scales import (
    DMM_R_MOHM_MIN_POS,
    dmm_chart_ylabel,
    dmm_chart_yscale,
    dmm_chart_ylim,
    dyno_chart_ylabel,
    dyno_chart_ylim,
    format_resistance_y_tick_engineering_mohm,
)
from app.__version__ import __version__
from app.services.export import ExportResult, export_session, session_acquisition_path
from app.services.user_settings import save_user_settings
from app.services.units import format_reading_with_unit
from app.ui.settings import SettingsPanel
from app.ui.toast import play_timer_finished_chime, show_toast

_MAX_STATUS_EVENTS_PER_TICK = 120
_MAX_READINGS_PER_TICK = 400

# Official bench test name (multimeter + dynamometer), used for window title and chart branding.
OFFICIAL_TEST_NAME = "Multimeter-dynamometer combined acquisition test"

_ABOUT_TAB_TITLE = "EasyAcq — Aquisição multímetro e dinamómetro"
_ABOUT_TAB_BODY = """Esta aplicação de bancada integra a aquisição sincronizada de grandezas elétricas (multímetro digital, via NI-VISA) com a medição de força mecânica (dinamómetro, via porta série). Oferece visualização em tempo real, registo estruturado por sessão em CSV e exportação de séries e gráficos para análise e arquivo.

Finalidade e enquadramento
O software foi desenvolvido para suportar processos internos de controlo de qualidade e caracterização de produtos da Nanopaint, Lda., fornecendo um canal homogéneo de obtenção das medições necessárias a ensaios, verificação de conformidade e elaboração de evidências técnicas. Os dados recolhidos destinam-se a uso disciplinado em testes de qualidade e decisões alinhadas com os requisitos da organização."""


class MainWindow:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.bus = EventBus(maxsize=config.queue_maxsize)
        self.csv_queue: "Queue[ReadingEvent]" = Queue(maxsize=config.queue_maxsize)
        self.supervisor: Optional[Supervisor] = None
        self.running = False
        self.session_logger = logging.getLogger("acq.sessao")
        self.session_csv_id: str = ""
        self.csv_dropped = 0
        self._dmm_ok_samples = 0
        self._dyno_ok_samples = 0

        self.root = tk.Tk()
        self.root.title(OFFICIAL_TEST_NAME)
        self.root.geometry("980x760")
        self.root.minsize(720, 580)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.mode_var = tk.StringVar(value="DCV")
        self.dmm_reading_var = tk.StringVar(value="--")
        self.dmm_mode_var = tk.StringVar(value="DCV")
        self.dmm_state_var = tk.StringVar(value="DISCONNECTED")
        self.dmm_detail_var = tk.StringVar(value="")
        self.dyno_reading_var = tk.StringVar(value="--")
        self.dyno_state_var = tk.StringVar(value="DISCONNECTED")
        self.dyno_detail_var = tk.StringVar(value="")

        self.dmm_times: deque[float] = deque(maxlen=config.chart_window_seconds * 10)
        self.dmm_values: deque[float] = deque(maxlen=config.chart_window_seconds * 10)
        self.dyno_times: deque[float] = deque(maxlen=config.chart_window_seconds * 10)
        self.dyno_values: deque[float] = deque(maxlen=config.chart_window_seconds * 10)
        self._session_start: Optional[float] = None
        self._session_deadline: Optional[float] = None
        # Duração programada (s) quando acquisition_duration_seconds > 0; limpo em stop().
        self._session_timer_seconds: Optional[float] = None
        self._last_stats_wall: float = 0.0
        self._prev_dmm_ok = 0
        self._prev_dyno_ok = 0
        self._chart_dirty = False

        self._build_layout()
        self.root.bind("<Configure>", self._on_root_configure, add="+")

    def _build_layout(self) -> None:
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Modo DMM:").pack(side="left")
        mode_combo = ttk.Combobox(
            top,
            textvariable=self.mode_var,
            values=["DCV", "ACV", "DCI", "ACI", "R"],
            state="readonly",
            width=8,
        )
        mode_combo.pack(side="left", padx=8)
        mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        self.btn_start = ttk.Button(top, text="Iniciar", command=self.start)
        self.btn_start.pack(side="left", padx=5)
        self.btn_stop = ttk.Button(top, text="Parar", command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", padx=5)
        self.btn_export = ttk.Button(top, text="Exportar", command=self.export_data)
        self.btn_export.pack(side="left", padx=5)

        self.stats_var = tk.StringVar(value="")
        self._stats_label = ttk.Label(
            top,
            textvariable=self.stats_var,
            font=("Consolas", 9),
            wraplength=420,
            justify="left",
        )
        self._stats_label.pack(side="left", padx=(16, 0), fill="x", expand=True)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        display_tab = ttk.Frame(notebook, padding=16)
        graphs_tab = ttk.Frame(notebook, padding=8)
        settings_tab = ttk.Frame(notebook, padding=8)
        about_tab = ttk.Frame(notebook, padding=16)
        notebook.add(display_tab, text="Valores atuais")
        notebook.add(graphs_tab, text="Gráficos")
        notebook.add(settings_tab, text="Configurações")
        notebook.add(about_tab, text="Sobre")

        self._build_display_tab(display_tab)
        self._build_graphs_tab(graphs_tab)
        self.settings_panel = SettingsPanel(
            settings_tab,
            self.config,
            on_chart_resistance_log_changed=self._on_chart_resistance_scale_changed,
        )
        self._build_about_tab(about_tab)

        log_frame = ttk.LabelFrame(self.root, text="Diagnóstico")
        log_frame.pack(fill="both", expand=False, padx=10, pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=6,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_display_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        dmm_card = ttk.LabelFrame(parent, text="Multímetro (digital)", padding=20)
        dmm_card.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        dmm_card.columnconfigure(0, weight=1)

        ttk.Label(
            dmm_card,
            textvariable=self.dmm_reading_var,
            font=("Segoe UI", 42, "bold"),
            anchor="center",
        ).grid(row=0, column=0, sticky="nsew", pady=(8, 12))
        ttk.Label(
            dmm_card,
            textvariable=self.dmm_mode_var,
            font=("Segoe UI", 14),
            anchor="center",
        ).grid(row=1, column=0, sticky="ew")
        ttk.Label(
            dmm_card,
            textvariable=self.dmm_state_var,
            font=("Segoe UI", 11),
            anchor="center",
        ).grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self._dmm_detail = ttk.Label(
            dmm_card,
            textvariable=self.dmm_detail_var,
            wraplength=640,
            anchor="center",
            justify="center",
        )
        self._dmm_detail.grid(row=3, column=0, sticky="ew", pady=(4, 0))

        dyno_card = ttk.LabelFrame(parent, text="Dinamómetro", padding=20)
        dyno_card.grid(row=1, column=0, sticky="nsew")
        dyno_card.columnconfigure(0, weight=1)

        ttk.Label(
            dyno_card,
            textvariable=self.dyno_reading_var,
            font=("Segoe UI", 42, "bold"),
            anchor="center",
        ).grid(row=0, column=0, sticky="nsew", pady=(8, 12))
        ttk.Label(
            dyno_card,
            textvariable=self.dyno_state_var,
            font=("Segoe UI", 11),
            anchor="center",
        ).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self._dyno_detail = ttk.Label(
            dyno_card,
            textvariable=self.dyno_detail_var,
            wraplength=640,
            anchor="center",
            justify="center",
        )
        self._dyno_detail.grid(row=2, column=0, sticky="ew", pady=(4, 0))

    def _build_about_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text=_ABOUT_TAB_TITLE,
            font=("Segoe UI", 13, "bold"),
            wraplength=720,
            justify="left",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text=f"Versão {__version__}",
            font=("Segoe UI", 10),
            foreground="#444444",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        ttk.Separator(parent, orient="horizontal").grid(row=1, column=0, sticky="ew", pady=(12, 8))

        body = scrolledtext.ScrolledText(
            parent,
            height=18,
            wrap="word",
            font=("Segoe UI", 10),
            state="normal",
            padx=4,
            pady=4,
        )
        body.grid(row=2, column=0, sticky="nsew")
        body.insert("1.0", _ABOUT_TAB_BODY.strip())
        body.configure(state="disabled")

    def _build_graphs_tab(self, parent: ttk.Frame) -> None:
        self._graphs_parent = parent
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))
        self.chart_integrated_var = tk.BooleanVar(value=self.config.chart_show_integrated)
        ttk.Checkbutton(
            toolbar,
            text="Gráfico integrado multímetro + dinamómetro (tempo real)",
            variable=self.chart_integrated_var,
            command=self._on_chart_integrated_toggle,
        ).pack(side="left")

        self._graphs_scroll = tk.Canvas(parent, highlightthickness=0)
        graphs_vscroll = ttk.Scrollbar(parent, orient="vertical", command=self._graphs_scroll.yview)
        self._graphs_scroll.configure(yscrollcommand=graphs_vscroll.set)
        self._graphs_scroll.grid(row=1, column=0, sticky="nsew")
        graphs_vscroll.grid(row=1, column=1, sticky="ns")

        inner = ttk.Frame(self._graphs_scroll)
        self._graphs_inner = inner
        inner.columnconfigure(0, weight=1)
        _graphs_inner_id = self._graphs_scroll.create_window((0, 0), window=inner, anchor="nw")

        def _sync_graphs_inner_width(event: tk.Event) -> None:
            if event.widget is self._graphs_scroll and int(event.width) > 1:
                self._graphs_scroll.itemconfigure(_graphs_inner_id, width=int(event.width))

        def _graphs_update_scrollregion(_event: tk.Event | None = None) -> None:
            self._graphs_scroll.update_idletasks()
            self._graphs_scroll.configure(scrollregion=self._graphs_scroll.bbox("all"))

        self._graphs_scroll.bind("<Configure>", _sync_graphs_inner_width)
        inner.bind("<Configure>", lambda _e: _graphs_update_scrollregion())

        chart_container = ttk.Frame(inner)
        chart_container.grid(row=0, column=0, sticky="nsew")

        self.fig = Figure(figsize=(9.0, 5.0), dpi=100)
        try:
            self.fig.set_layout_engine("constrained")
        except Exception:
            self.fig.subplots_adjust(left=0.11, right=0.98, top=0.94, bottom=0.12, hspace=0.38)
        self.ax1 = self.fig.add_subplot(2, 1, 1)
        self.ax2 = self.fig.add_subplot(2, 1, 2)
        self.ax1.set_title("Multimeter")
        self.ax2.set_title("Dynamometer")
        self.ax1.set_xlabel("Relative time (s)")
        self.ax2.set_xlabel("Relative time (s)")
        for ax in (self.ax1, self.ax2):
            ax.tick_params(axis="both", labelsize=9)
            ax.xaxis.label.set_size(10)
            ax.yaxis.label.set_size(10)
        (self.line1,) = self.ax1.plot([], [])
        (self.line2,) = self.ax2.plot([], [])

        canvas = FigureCanvasTkAgg(self.fig, master=chart_container)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill="both", expand=True)
        self.canvas = canvas
        self._graph_resize_timer = None
        canvas_widget.bind("<Configure>", self._on_graph_canvas_configure, add="+")

        self.combo_outer = ttk.LabelFrame(inner, text="Integrado (multímetro + dinamómetro)", padding=4)
        self.combo_outer.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        inner.rowconfigure(1, weight=0)
        self.fig_combo = Figure(figsize=(9.0, 1.85), dpi=100)
        try:
            self.fig_combo.set_layout_engine("constrained")
        except Exception:
            pass
        self.ax_combo = self.fig_combo.add_subplot(111)
        self.ax_combo_twin = self.ax_combo.twinx()
        self.ax_combo.set_xlabel("Relative time (s)")
        self.ax_combo.set_title("Multimeter + dynamometer (real time)")
        dyno_u = self.config.dyno_force_unit.strip().upper()
        (self.line_combo_dmm,) = self.ax_combo.plot([], [], color="C0", label="Multimeter")
        (self.line_combo_dyno,) = self.ax_combo_twin.plot([], [], color="C1", label=dyno_u)
        self.ax_combo.grid(True, which="major", alpha=0.35)
        self.ax_combo.grid(False, which="minor")
        self.canvas_combo = FigureCanvasTkAgg(self.fig_combo, master=self.combo_outer)
        combo_widget = self.canvas_combo.get_tk_widget()
        combo_widget.pack(fill="both", expand=True)

        self._bind_graphs_scroll_mousewheel(self._graphs_scroll)
        self._bind_graphs_scroll_mousewheel(inner)
        self._bind_graphs_scroll_mousewheel(chart_container)
        self._bind_graphs_scroll_mousewheel(canvas_widget)
        self._bind_graphs_scroll_mousewheel(combo_widget)

        self._setup_chart_hover_tooltips(canvas_widget, combo_widget)

        self._update_chart_labels()

        if not self.config.chart_show_integrated:
            self.combo_outer.grid_remove()

        _graphs_update_scrollregion()

    def _bind_graphs_scroll_mousewheel(self, widget: tk.Widget) -> None:
        c = self._graphs_scroll

        def _win_wheel(e: tk.Event) -> None:
            if getattr(e, "delta", 0):
                c.yview_scroll(int(-1 * (e.delta / 120)), "units")

        def _x11_up(_e: tk.Event) -> None:
            c.yview_scroll(-1, "units")

        def _x11_down(_e: tk.Event) -> None:
            c.yview_scroll(1, "units")

        widget.bind("<MouseWheel>", _win_wheel, add="+")
        widget.bind("<Button-4>", _x11_up, add="+")
        widget.bind("<Button-5>", _x11_down, add="+")

    def _on_chart_integrated_toggle(self) -> None:
        self.config.chart_show_integrated = self.chart_integrated_var.get()
        if self.config.chart_show_integrated:
            self.combo_outer.grid()
        else:
            self.combo_outer.grid_remove()
        self._graphs_scroll.update_idletasks()
        self._graphs_scroll.configure(scrollregion=self._graphs_scroll.bbox("all"))
        save_user_settings(self.config)
        self._chart_dirty = True
        self._refresh_plot()

    def _on_root_configure(self, event: Any) -> None:
        if event.widget is not self.root:
            return
        try:
            rw = int(self.root.winfo_width())
        except tk.TclError:
            return
        if rw < 200:
            return
        wrap = max(160, rw - 72)
        if hasattr(self, "_dmm_detail"):
            self._dmm_detail.configure(wraplength=wrap)
            self._dyno_detail.configure(wraplength=wrap)
        if hasattr(self, "_stats_label"):
            self._stats_label.configure(wraplength=max(140, rw - 280))

    def _on_graph_canvas_configure(self, event: Any) -> None:
        if not hasattr(self, "canvas"):
            return
        if event.widget is not self.canvas.get_tk_widget():
            return
        tid = self._graph_resize_timer
        if tid is not None:
            try:
                self.root.after_cancel(tid)
            except Exception:
                pass
        w, h = event.width, event.height
        self._graph_resize_timer = self.root.after(
            90, lambda: self._apply_graph_canvas_size(w, h)
        )

    def _apply_graph_canvas_size(self, w: int, h: int) -> None:
        self._graph_resize_timer = None
        if w < 80 or h < 80:
            return
        dpi = float(self.fig.get_dpi())
        nw, nh = w / dpi, h / dpi
        cur = self.fig.get_size_inches()
        if abs(cur[0] - nw) < 0.1 and abs(cur[1] - nh) < 0.1:
            return
        self.fig.set_size_inches(nw, nh, forward=True)
        tick = max(7, min(10, int(6 + nw)))
        for ax in (self.ax1, self.ax2):
            ax.tick_params(axis="both", labelsize=tick)
        self.canvas.draw_idle()

    def start(self) -> None:
        if self.running:
            return
        try:
            self.settings_panel.apply_to_config()
        except ValueError as exc:
            messagebox.showerror("Configuração inválida", str(exc))
            return
        self._append_log(
            "A iniciar aquisicao. VISA auto-discovery: "
            f"{'ativo' if self.config.auto_discover_visa else 'desativo'}"
        )
        if self.config.visa_resource:
            self._append_log(f"Recurso VISA preferido: {self.config.visa_resource}")
        self._append_log(
            "Dinamómetro: "
            f"{self.config.dyno_port} @ {self.config.dyno_baudrate} baud, "
            f"stream={'ativo' if self.config.dyno_stream_enabled else 'passivo'}, "
            f"arranque={self.config.dyno_start_command!r}, "
            f"unidade={self.config.dyno_force_unit}"
        )
        self._update_chart_labels()
        self._session_start = time.monotonic()
        tlim = float(self.config.acquisition_duration_seconds)
        if tlim > 0.0:
            self._session_deadline = self._session_start + tlim
            self._session_timer_seconds = float(tlim)
            self._append_log(f"Duracao maxima da sessao: {tlim:g} s (paragem automatica ao fim do tempo).")
        else:
            self._session_deadline = None
            self._session_timer_seconds = None
        self.session_csv_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.csv_dropped = 0
        self._dmm_ok_samples = 0
        self._dyno_ok_samples = 0
        self._prev_dmm_ok = 0
        self._prev_dyno_ok = 0
        self._last_stats_wall = time.monotonic()
        self.bus.readings_dropped = 0
        self.bus.status_dropped = 0
        win_s = max(5, int(self.config.chart_window_seconds))
        self.dmm_times = deque(maxlen=win_s * 10)
        self.dmm_values = deque(maxlen=win_s * 10)
        self.dyno_times = deque(maxlen=win_s * 10)
        self.dyno_values = deque(maxlen=win_s * 10)
        self._chart_dirty = False
        self.supervisor = Supervisor(
            self.config,
            self.bus,
            self.csv_queue,
            session_csv_id=self.session_csv_id,
        )
        self.supervisor.set_multimeter_mode(self.mode_var.get())
        self.supervisor.start()
        self.running = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.settings_panel.set_enabled(False)
        self._schedule_poll()

    def stop(self) -> None:
        if not self.running:
            return
        if self.supervisor is not None:
            self.supervisor.stop()
            self.supervisor = None
        self.running = False
        self._session_deadline = None
        self._session_timer_seconds = None
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.settings_panel.set_enabled(True)

    def export_data(self) -> None:
        if not self.dmm_values and not self.dyno_values:
            messagebox.showwarning(
                "Exportação",
                "Não há dados nos gráficos para exportar. Inicie uma aquisição primeiro.",
            )
            return

        default_dir = self.config.csv_dir / "exports"
        dest_dir = filedialog.askdirectory(
            title="Escolher pasta de exportação",
            initialdir=str(default_dir if default_dir.exists() else self.config.csv_dir),
        )
        if not dest_dir:
            return

        if self.running:
            self.stop()
            self._append_log("Exportação: aquisição parada para libertar a COM6 e gravar ficheiros.")

        dlg = tk.Toplevel(self.root)
        dlg.title("Opções de exportação")
        dlg.transient(self.root)
        dlg.grab_set()
        var_dmm = tk.BooleanVar(value=True)
        var_dyno = tk.BooleanVar(value=True)
        var_merged = tk.BooleanVar(value=False)
        var_integrated_png = tk.BooleanVar(value=True)
        body = ttk.Frame(dlg, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(
            body,
            text="Será criada uma pasta com data e sessão; dentro: «resultado» (CSV/PNG para relatório), LEIAME.txt. O registo bruto continua na pasta de dados da aplicação (dados_<sessão>.csv).",
            wraplength=420,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))
        ttk.Checkbutton(body, text="Incluir multímetro (gráfico)", variable=var_dmm).grid(
            row=1, column=0, sticky="w"
        )
        ttk.Checkbutton(body, text="Incluir dinamómetro (gráfico)", variable=var_dyno).grid(
            row=2, column=0, sticky="w"
        )
        merged_cb = ttk.Checkbutton(
            body,
            text="Gerar CSV combinado (forward-fill por instante)",
            variable=var_merged,
        )
        merged_cb.grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            body,
            text="Guardar também gráfico integrado (PNG)",
            variable=var_integrated_png,
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))

        def sync_merged_state(*_: Any) -> None:
            ok = var_dmm.get() and var_dyno.get()
            merged_cb.configure(state="normal" if ok else "disabled")
            if not ok:
                var_merged.set(False)

        var_dmm.trace_add("write", sync_merged_state)
        var_dyno.trace_add("write", sync_merged_state)
        sync_merged_state()

        btns = ttk.Frame(dlg, padding=(12, 0, 12, 12))
        btns.pack(fill="x")
        status_lbl = ttk.Label(btns, text="")
        status_lbl.pack(side="left", fill="x", expand=True)

        def run_export() -> None:
            if not var_dmm.get() and not var_dyno.get():
                messagebox.showwarning("Exportação", "Selecione pelo menos um instrumento.", parent=dlg)
                return
            session_csv: Path | None = None
            if self.session_csv_id:
                p = session_acquisition_path(self.config.csv_dir, self.session_csv_id)
                if p.exists():
                    session_csv = p
            dest = Path(dest_dir)
            snap_dmm_t = list(self.dmm_times)
            snap_dmm_v = list(self.dmm_values)
            snap_dyno_t = list(self.dyno_times)
            snap_dyno_v = list(self.dyno_values)
            dmm_mode = self.mode_var.get()
            dyno_unit = self.config.dyno_force_unit
            incl_dmm = var_dmm.get()
            incl_dyno = var_dyno.get()
            do_merge = var_merged.get()
            save_int = var_integrated_png.get()
            cfg = self.config
            fig = self.fig
            fig_i = self.fig_combo if save_int else None

            btn_run.configure(state="disabled")
            btn_cancel.configure(state="disabled")
            status_lbl.configure(text="A exportar…")

            def finish_error(exc: BaseException) -> None:
                try:
                    if dlg.winfo_exists():
                        btn_run.configure(state="normal")
                        btn_cancel.configure(state="normal")
                        status_lbl.configure(text="")
                        messagebox.showerror(
                            "Exportação", f"Não foi possível exportar os dados.\n\n{exc}", parent=dlg
                        )
                except tk.TclError:
                    pass

            def finish_ok(result: ExportResult) -> None:
                try:
                    if not dlg.winfo_exists():
                        return
                    dlg.destroy()
                except tk.TclError:
                    return
                self._show_export_done(result)

            def work() -> None:
                try:
                    result = export_session(
                        dest,
                        config=cfg,
                        figure=fig,
                        dmm_times=snap_dmm_t,
                        dmm_values=snap_dmm_v,
                        dmm_mode=dmm_mode,
                        dyno_times=snap_dyno_t,
                        dyno_values=snap_dyno_v,
                        dyno_force_unit=dyno_unit,
                        session_acquisition_csv=session_csv,
                        session_csv_id=self.session_csv_id or "",
                        include_dmm=incl_dmm,
                        include_dyno=incl_dyno,
                        write_merged=do_merge,
                        figure_integrated=fig_i,
                        save_integrated_png=bool(save_int and fig_i is not None),
                    )
                except (OSError, ValueError) as exc:
                    self.root.after(0, lambda e=exc: finish_error(e))
                else:
                    self.root.after(0, lambda r=result: finish_ok(r))

            threading.Thread(target=work, daemon=True, name="ExportSession").start()

        btn_cancel = ttk.Button(btns, text="Cancelar", command=dlg.destroy)
        btn_cancel.pack(side="right", padx=(8, 0))
        btn_run = ttk.Button(btns, text="Exportar", command=run_export)
        btn_run.pack(side="right")

    def _show_export_done(self, result: ExportResult) -> None:
        files = result.all_files()
        extra = ""
        if result.chart_png_integrated is not None:
            extra = f", integrado {result.chart_png_integrated.name}"
        self._append_log(
            "Exportação concluída: "
            f"{result.chart_rows} linhas em {result.chart_csv.relative_to(result.directory)}, "
            f"imagem {result.chart_png.name}{extra} | pasta {result.directory.name}"
        )
        messagebox.showinfo(
            "Exportação",
            "Pacote criado (resultado):\n- "
            + "\n- ".join(files)
            + f"\n\nPasta da sessão:\n{result.directory}\n\nContém a subpasta «resultado» e o ficheiro LEIAME.txt.",
        )

    def _on_close(self) -> None:
        self.stop()
        try:
            self.settings_panel.apply_to_config()
        except ValueError:
            pass
        save_user_settings(self.config)
        self.root.destroy()

    def _on_chart_resistance_scale_changed(self) -> None:
        self._update_chart_labels()
        self._refresh_plot()

    def _on_mode_change(self, _: Any) -> None:
        self.dmm_times.clear()
        self.dmm_values.clear()
        self._chart_dirty = True
        self._update_chart_labels()
        if self.supervisor is not None:
            self.supervisor.set_multimeter_mode(self.mode_var.get())
        self._refresh_plot()

    def _schedule_poll(self) -> None:
        if not self.running:
            return
        self._poll_events()
        delay_ms = int(1000 / max(self.config.ui_refresh_hz, 1))
        self.root.after(delay_ms, self._schedule_poll)

    def _poll_events(self) -> None:
        reschedule = False

        n_status = 0
        for _ in range(_MAX_STATUS_EVENTS_PER_TICK):
            try:
                status: StatusEvent = self.bus.status.get_nowait()
            except Empty:
                break
            self._apply_status(status)
            n_status += 1
        if n_status >= _MAX_STATUS_EVENTS_PER_TICK:
            reschedule = True

        last_dmm: Optional[ReadingEvent] = None
        last_dyno: Optional[ReadingEvent] = None
        n_readings = 0
        for _ in range(_MAX_READINGS_PER_TICK):
            try:
                ev: ReadingEvent = self.bus.readings.get_nowait()
            except Empty:
                break
            try:
                if ev.status == "OK":
                    self.csv_queue.put_nowait(ev)
            except Full:
                self.csv_dropped += 1
                _ = self.csv_queue.get_nowait()
                self.csv_queue.put_nowait(ev)
            elapsed = 0.0
            if self._session_start is not None:
                elapsed = time.monotonic() - self._session_start
            if ev.source == "dmm":
                last_dmm = ev
                if ev.status == "OK":
                    self._dmm_ok_samples += 1
                    mode_u = self.mode_var.get().strip().upper()
                    y_plot: float | None = ev.value
                    if mode_u == "R":
                        y_plot = ev.value / 1_000_000.0
                        if not math.isfinite(y_plot) or y_plot <= DMM_R_MOHM_MIN_POS:
                            y_plot = None
                    elif not math.isfinite(y_plot):
                        y_plot = None
                    if y_plot is not None:
                        self.dmm_times.append(elapsed)
                        self.dmm_values.append(y_plot)
                        self._chart_dirty = True
            elif ev.source == "dyno":
                last_dyno = ev
                if ev.status == "OK":
                    self._dyno_ok_samples += 1
                    self.dyno_times.append(elapsed)
                    self.dyno_values.append(ev.value)
                    self._chart_dirty = True
            n_readings += 1
        if n_readings >= _MAX_READINGS_PER_TICK:
            reschedule = True

        if last_dmm is not None:
            if last_dmm.status == "OVERLOAD":
                self.dmm_reading_var.set("O.L (fora de escala)")
            elif last_dmm.status != "OK":
                self.dmm_reading_var.set("—")
            else:
                self.dmm_reading_var.set(
                    format_reading_with_unit(
                        last_dmm.source, last_dmm.value, last_dmm.unit, last_dmm.mode
                    )
                )
            self.dmm_mode_var.set(f"Modo: {last_dmm.mode or '--'} | Estado: {last_dmm.status}")
        if last_dyno is not None:
            self.dyno_reading_var.set(
                format_reading_with_unit(
                    last_dyno.source, last_dyno.value, last_dyno.unit, last_dyno.mode
                )
            )

        self._update_stats_line()
        if self._chart_dirty:
            self._refresh_plot()
            self._chart_dirty = False

        if self.running and self._session_deadline is not None:
            if time.monotonic() >= self._session_deadline:
                planned = float(self._session_timer_seconds or 0.0)
                self._append_log("Aquisicao: tempo maximo da sessao atingido — paragem automatica.")
                play_timer_finished_chime()
                toast_msg = (
                    f"A amostragem terminou após {planned:g} s."
                    if planned > 0.0
                    else "A amostragem terminou (tempo programado)."
                )
                self.stop()
                self.root.after(
                    80,
                    lambda m=toast_msg: show_toast(self.root, "EasyAcq — Tempo de aquisição", m),
                )

        if reschedule and self.running:
            self.root.after(0, self._poll_events)

    def _apply_status(self, status: StatusEvent) -> None:
        detail = status.detail.strip()
        if status.source == "dmm":
            self.dmm_state_var.set(status.state)
            self.dmm_detail_var.set(detail)
        elif status.source == "dyno":
            self.dyno_state_var.set(status.state)
            self.dyno_detail_var.set(detail)

        message = f"[{status.source}] {status.state}"
        if detail:
            message = f"{message} - {detail}"
        self._append_log(message)

    def _append_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"{stamp} | {message}"
        self.session_logger.info(message)
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{line}\n")
        while int(float(self.log_text.index("end-1c").split(".")[0])) > 300:
            self.log_text.delete("1.0", "2.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_stats_line(self) -> None:
        now = time.monotonic()
        dt = now - self._last_stats_wall
        if dt < 0.5:
            return
        d_dmm = self._dmm_ok_samples - self._prev_dmm_ok
        d_dyn = self._dyno_ok_samples - self._prev_dyno_ok
        self._prev_dmm_ok = self._dmm_ok_samples
        self._prev_dyno_ok = self._dyno_ok_samples
        self._last_stats_wall = now
        hz_dmm = d_dmm / dt if dt > 0 else 0.0
        hz_dyn = d_dyn / dt if dt > 0 else 0.0
        rest_s = ""
        if self.running and self._session_deadline is not None:
            rest = max(0.0, self._session_deadline - now)
            rest_s = f" | Tempo restante ~{rest:.0f} s"
        self.stats_var.set(
            f"Filas: leituras descartadas={self.bus.readings_dropped} "
            f"estado descartados={self.bus.status_dropped} "
            f"CSV descartadas={self.csv_dropped} | "
            f"~Hz multímetro {hz_dmm:.1f} | Dyno {hz_dyn:.1f}"
            f"{rest_s}"
        )

    def _update_chart_labels(self) -> None:
        log_r = self.config.chart_resistance_log_scale
        self.ax1.set_ylabel(dmm_chart_ylabel(self.mode_var.get(), log_r))
        if hasattr(self, "ax_combo"):
            self.ax_combo.set_ylabel(dmm_chart_ylabel(self.mode_var.get(), log_r), color="C0")
            self.ax_combo.tick_params(axis="y", labelcolor="C0")
            self.ax_combo_twin.set_ylabel(
                dyno_chart_ylabel(self.config.dyno_force_unit, self.config.dyno_chart_max_abs_force),
                color="C1",
            )
            self.ax_combo_twin.tick_params(axis="y", labelcolor="C1")
            self.line_combo_dyno.set_label(self.config.dyno_force_unit.strip().upper())
        self.ax2.set_ylabel(
            dyno_chart_ylabel(self.config.dyno_force_unit, self.config.dyno_chart_max_abs_force)
        )

    def _refresh_plot(self) -> None:
        dmm_x = list(self.dmm_times)
        dmm_y = list(self.dmm_values)
        dyno_x = list(self.dyno_times)
        dyno_y = list(self.dyno_values)
        self.line1.set_data(dmm_x, dmm_y)
        self.line2.set_data(dyno_x, dyno_y)

        window = float(self.config.chart_window_seconds)
        dmm_mode = self.mode_var.get()
        dmm_ymin, dmm_ymax = dmm_chart_ylim(dmm_mode, dmm_y)
        dyno_ymin, dyno_ymax = dyno_chart_ylim(
            self.config.dyno_force_unit,
            dyno_y,
            self.config.dyno_chart_max_abs_force,
        )

        if dmm_x:
            xmax = max(dmm_x)
            self.ax1.set_xlim(max(0.0, xmax - window), max(window, xmax + 0.5))
        else:
            self.ax1.set_xlim(0.0, window)
        self.ax1.set_yscale(dmm_chart_yscale(dmm_mode, self.config.chart_resistance_log_scale))
        self.ax1.set_ylim(dmm_ymin, dmm_ymax)
        if dmm_mode.strip().upper() == "R":
            self.ax1.yaxis.set_major_formatter(
                FuncFormatter(format_resistance_y_tick_engineering_mohm)
            )
            if self.config.chart_resistance_log_scale:
                self.ax1.grid(True, which="major", alpha=0.45)
                self.ax1.grid(True, which="minor", alpha=0.28, linestyle=":")
            else:
                self.ax1.grid(True, which="major", alpha=0.35)
                self.ax1.grid(False, which="minor")
        else:
            self.ax1.yaxis.set_major_formatter(ScalarFormatter())
            self.ax1.grid(True, which="major", alpha=0.35)
            self.ax1.grid(False, which="minor")

        if dyno_x:
            xmax = max(dyno_x)
            self.ax2.set_xlim(max(0.0, xmax - window), max(window, xmax + 0.5))
        else:
            self.ax2.set_xlim(0.0, window)
        self.ax2.set_yscale("linear")
        self.ax2.set_ylim(dyno_ymin, dyno_ymax)
        self.ax2.grid(True, which="major", alpha=0.35)
        self.ax2.grid(False, which="minor")

        self.canvas.draw_idle()

        if self.config.chart_show_integrated and hasattr(self, "ax_combo"):
            self.line_combo_dmm.set_data(dmm_x, dmm_y)
            self.line_combo_dyno.set_data(dyno_x, dyno_y)
            xmax_c = 0.0
            if dmm_x:
                xmax_c = max(xmax_c, max(dmm_x))
            if dyno_x:
                xmax_c = max(xmax_c, max(dyno_x))
            if xmax_c > 0.0:
                self.ax_combo.set_xlim(max(0.0, xmax_c - window), max(window, xmax_c + 0.5))
            else:
                self.ax_combo.set_xlim(0.0, window)
            self.ax_combo.set_yscale(dmm_chart_yscale(dmm_mode, self.config.chart_resistance_log_scale))
            self.ax_combo.set_ylim(dmm_ymin, dmm_ymax)
            if dmm_mode.strip().upper() == "R":
                self.ax_combo.yaxis.set_major_formatter(
                    FuncFormatter(format_resistance_y_tick_engineering_mohm)
                )
                if self.config.chart_resistance_log_scale:
                    self.ax_combo.grid(True, which="major", alpha=0.45)
                    self.ax_combo.grid(True, which="minor", alpha=0.28, linestyle=":")
                else:
                    self.ax_combo.grid(True, which="major", alpha=0.35)
                    self.ax_combo.grid(False, which="minor")
            else:
                self.ax_combo.yaxis.set_major_formatter(ScalarFormatter())
                self.ax_combo.grid(True, which="major", alpha=0.35)
                self.ax_combo.grid(False, which="minor")
            self.ax_combo_twin.set_ylim(dyno_ymin, dyno_ymax)
            self.canvas_combo.draw_idle()
            self._graphs_scroll.update_idletasks()
            self._graphs_scroll.configure(scrollregion=self._graphs_scroll.bbox("all"))

    def _setup_chart_hover_tooltips(self, main_widget: tk.Widget, combo_widget: tk.Widget) -> None:
        self._hover_annot_ax1 = self._create_chart_hover_annotation(self.ax1)
        self._hover_annot_ax2 = self._create_chart_hover_annotation(self.ax2)
        self._hover_annot_combo = self.ax_combo.annotate(
            "",
            xy=(0.5, 1.0),
            xycoords="axes fraction",
            xytext=(0, -4),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=8,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="cornsilk", edgecolor="gray", alpha=0.94),
            visible=False,
            zorder=200,
            clip_on=False,
        )
        self._hover_last_main: tuple[Any, ...] | None = None
        self._hover_last_combo: str | None = None
        self.canvas.mpl_connect("motion_notify_event", self._on_motion_hover_main)
        self.canvas_combo.mpl_connect("motion_notify_event", self._on_motion_hover_combo)
        main_widget.bind("<Leave>", self._on_leave_hover_main, add="+")
        combo_widget.bind("<Leave>", self._on_leave_hover_combo, add="+")

    def _create_chart_hover_annotation(self, ax: Any) -> Any:
        return ax.annotate(
            "",
            xy=(0.0, 0.0),
            xytext=(12, 12),
            textcoords="offset points",
            ha="left",
            va="bottom",
            fontsize=8,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="cornsilk", edgecolor="gray", alpha=0.94),
            visible=False,
            zorder=200,
            clip_on=False,
        )

    @staticmethod
    def _nearest_time_index(times: list[float], x: float) -> int | None:
        if not times:
            return None
        i = bisect.bisect_left(times, x)
        candidates: list[int] = []
        if i < len(times):
            candidates.append(i)
        if i > 0:
            candidates.append(i - 1)
        return min(candidates, key=lambda j: abs(times[j] - x))

    def _hover_time_within_span(self, x: float, t_sample: float, ax: Any, *, span_frac: float = 0.14) -> bool:
        lo, hi = ax.get_xlim()
        span = max(hi - lo, 1e-9)
        return abs(t_sample - x) <= span * span_frac

    def _format_hover_dmm(self, y: float) -> str:
        m = self.mode_var.get().strip().upper()
        if m == "R":
            return f"{y:.8g} MΩ"
        if m in {"DCV", "ACV"}:
            return f"{y:.6f} V"
        if m in {"DCI", "ACI"}:
            return f"{y:.6f} A"
        return f"{y:.8g}"

    def _format_hover_dyno(self, y: float) -> str:
        u = self.config.dyno_force_unit.strip().upper()
        return f"{y:+.6f} {u}"

    def _hide_hover_main(self) -> None:
        self._hover_annot_ax1.set_visible(False)
        self._hover_annot_ax2.set_visible(False)
        self._hover_last_main = None
        self.canvas.draw_idle()

    def _hide_hover_combo(self) -> None:
        self._hover_annot_combo.set_visible(False)
        self._hover_last_combo = None
        self.canvas_combo.draw_idle()

    def _on_leave_hover_main(self, _event: tk.Event) -> None:
        self._hide_hover_main()

    def _on_leave_hover_combo(self, _event: tk.Event) -> None:
        self._hide_hover_combo()

    def _on_motion_hover_main(self, event: Any) -> None:
        if event.inaxes is None or event.xdata is None:
            self._hide_hover_main()
            return
        x = float(event.xdata)
        signature: tuple[Any, ...]
        if event.inaxes is self.ax1:
            times = list(self.dmm_times)
            vals = list(self.dmm_values)
            idx = self._nearest_time_index(times, x)
            if idx is None:
                self._hide_hover_main()
                return
            tx, y = times[idx], vals[idx]
            if not self._hover_time_within_span(x, tx, self.ax1):
                self._hide_hover_main()
                return
            txt = f"t = {tx:.4f} s\n{self._format_hover_dmm(y)}"
            self._hover_annot_ax1.xy = (tx, y)
            self._hover_annot_ax1.set_text(txt)
            self._hover_annot_ax1.set_visible(True)
            self._hover_annot_ax2.set_visible(False)
            signature = ("ax1", idx, round(tx, 6), round(y, 9))
        elif event.inaxes is self.ax2:
            times = list(self.dyno_times)
            vals = list(self.dyno_values)
            idx = self._nearest_time_index(times, x)
            if idx is None:
                self._hide_hover_main()
                return
            tx, y = times[idx], vals[idx]
            if not self._hover_time_within_span(x, tx, self.ax2):
                self._hide_hover_main()
                return
            txt = f"t = {tx:.4f} s\n{self._format_hover_dyno(y)}"
            self._hover_annot_ax2.xy = (tx, y)
            self._hover_annot_ax2.set_text(txt)
            self._hover_annot_ax2.set_visible(True)
            self._hover_annot_ax1.set_visible(False)
            signature = ("ax2", idx, round(tx, 6), round(y, 9))
        else:
            self._hide_hover_main()
            return
        if signature != self._hover_last_main:
            self._hover_last_main = signature
            self.canvas.draw_idle()

    def _on_motion_hover_combo(self, event: Any) -> None:
        if event.inaxes not in (self.ax_combo, self.ax_combo_twin) or event.xdata is None:
            self._hide_hover_combo()
            return
        x = float(event.xdata)
        ax_ref = self.ax_combo
        lo, hi = ax_ref.get_xlim()
        span = max(hi - lo, 1e-9)
        lines: list[str] = []
        dmm_t = list(self.dmm_times)
        dmm_v = list(self.dmm_values)
        dyn_t = list(self.dyno_times)
        dyn_v = list(self.dyno_values)
        ok = False
        if dmm_t:
            i = self._nearest_time_index(dmm_t, x)
            if i is not None:
                tx, y = dmm_t[i], dmm_v[i]
                if abs(tx - x) <= span * 0.14:
                    lines.append(f"Multímetro: t={tx:.4f} s\n  {self._format_hover_dmm(y)}")
                    ok = True
        if dyn_t:
            i = self._nearest_time_index(dyn_t, x)
            if i is not None:
                tx, y = dyn_t[i], dyn_v[i]
                if abs(tx - x) <= span * 0.14:
                    lines.append(f"Dinamómetro: t={tx:.4f} s\n  {self._format_hover_dyno(y)}")
                    ok = True
        if not ok:
            self._hide_hover_combo()
            return
        txt = "\n".join(lines)
        if txt != self._hover_last_combo:
            self._hover_last_combo = txt
            self._hover_annot_combo.set_text(txt)
            self._hover_annot_combo.set_visible(True)
            self.canvas_combo.draw_idle()

    def run(self) -> None:
        self.root.mainloop()
