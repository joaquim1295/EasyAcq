from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from app.config import AppConfig

TERMINATOR_OPTIONS = {
    "CR (Enter)": "\r",
    "LF": "\n",
    "CRLF": "\r\n",
}


class SettingsPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        config: AppConfig,
        *,
        on_chart_resistance_log_changed: Callable[[], None] | None = None,
    ) -> None:
        self.config = config
        self._on_chart_resistance_log_changed = on_chart_resistance_log_changed
        self._widgets: list[tk.Widget | ttk.Widget] = []

        self.visa_resource_var = tk.StringVar(value=config.visa_resource)
        self.auto_discover_var = tk.BooleanVar(value=config.auto_discover_visa)
        self.sample_hz_var = tk.StringVar(value=str(config.sample_hz))
        self.acquisition_duration_var = tk.StringVar(
            value=""
            if config.acquisition_duration_seconds <= 0
            else str(config.acquisition_duration_seconds).rstrip("0").rstrip(".")
        )
        self.dyno_port_var = tk.StringVar(value=config.dyno_port)
        self.dyno_baud_var = tk.StringVar(value=str(config.dyno_baudrate))
        self.dyno_bytesize_var = tk.StringVar(value=str(config.dyno_bytesize))
        self.dyno_parity_var = tk.StringVar(value=config.dyno_parity)
        self.dyno_stopbits_var = tk.StringVar(value=str(int(config.dyno_stopbits)))
        self.dyno_rtscts_var = tk.BooleanVar(value=config.dyno_rtscts)
        self.dyno_assert_rts_var = tk.BooleanVar(value=config.dyno_assert_rts)
        self.dyno_assert_dtr_var = tk.BooleanVar(value=config.dyno_assert_dtr)
        self.dyno_stream_enabled_var = tk.BooleanVar(value=config.dyno_stream_enabled)
        self.dyno_start_command_var = tk.StringVar(value=config.dyno_start_command)
        self.dyno_stop_command_var = tk.StringVar(value=config.dyno_stop_command)
        self.dyno_stream_idle_var = tk.StringVar(value=str(config.dyno_stream_idle_seconds))
        self.dyno_force_unit_var = tk.StringVar(value=config.dyno_force_unit)
        self.chart_resistance_log_var = tk.BooleanVar(value=config.chart_resistance_log_scale)
        self.dyno_chart_max_abs_var = tk.StringVar(
            value="" if config.dyno_chart_max_abs_force <= 0 else str(config.dyno_chart_max_abs_force)
        )
        self.chart_window_var = tk.StringVar(value=str(int(config.chart_window_seconds)))

        terminator_label = self._terminator_label_for(config.dyno_command_terminator)
        self.dyno_command_terminator_var = tk.StringVar(value=terminator_label)

        self._build(parent)

    def _build(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        win_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def _sync_scroll_width(event: tk.Event) -> None:
            if int(event.width) > 1:
                canvas.itemconfigure(win_id, width=int(event.width))

        canvas.bind("<Configure>", _sync_scroll_width)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        scroll_frame.columnconfigure(0, weight=1)
        scroll_frame.columnconfigure(1, weight=1)

        left_col = ttk.Frame(scroll_frame)
        right_col = ttk.Frame(scroll_frame)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)
        left_col.columnconfigure(0, weight=1)
        right_col.columnconfigure(0, weight=1)

        sdm = ttk.LabelFrame(left_col, text="DMM (VISA)", padding=12)
        sdm.pack(fill="x", expand=False, pady=(0, 10))
        self._add_row(sdm, 0, "Recurso VISA (opcional)", self.visa_resource_var)
        self._add_check(sdm, 1, "Auto-discovery USB", self.auto_discover_var)

        dyno = ttk.LabelFrame(left_col, text="Dinamómetro (serial)", padding=12)
        dyno.pack(fill="x", expand=False, pady=(0, 0))
        self._add_row(dyno, 0, "Porta COM", self.dyno_port_var)
        self._add_row(dyno, 1, "Baudrate", self.dyno_baud_var)
        self._add_combo(dyno, 2, "Bytesize", self.dyno_bytesize_var, ["7", "8"])
        self._add_combo(dyno, 3, "Paridade", self.dyno_parity_var, ["N", "E", "O"])
        self._add_combo(dyno, 4, "Stop bits", self.dyno_stopbits_var, ["1", "2"])
        self._add_check(dyno, 5, "Controlo de fluxo RTS/CTS", self.dyno_rtscts_var)
        self._add_check(dyno, 6, "Manter RTS ativo (alimentacao)", self.dyno_assert_rts_var)
        self._add_check(dyno, 7, "Manter DTR ativo (alimentacao)", self.dyno_assert_dtr_var)
        self._add_combo(dyno, 8, "Unidade de força", self.dyno_force_unit_var, ["N", "kgf"])

        stream = ttk.LabelFrame(right_col, text="Stream do dinamómetro", padding=12)
        stream.pack(fill="x", expand=False, pady=(0, 10))
        self._add_check(stream, 0, "Ativar arranque por comando", self.dyno_stream_enabled_var)
        self._add_row(stream, 1, "Comando de arranque", self.dyno_start_command_var)
        self._add_row(stream, 2, "Comando de paragem (opcional)", self.dyno_stop_command_var)
        self._add_combo(
            stream,
            3,
            "Terminador",
            self.dyno_command_terminator_var,
            list(TERMINATOR_OPTIONS.keys()),
        )
        self._add_row(stream, 4, "Aviso sem dados (s)", self.dyno_stream_idle_var)

        acq = ttk.LabelFrame(right_col, text="Aquisição", padding=12)
        acq.pack(fill="x", expand=False, pady=(0, 10))
        self._add_row(acq, 0, "Taxa (Hz)", self.sample_hz_var)
        self._add_row(
            acq,
            1,
            "Duração máx. da sessão (s, 0 = até parar)",
            self.acquisition_duration_var,
        )
        log_check = ttk.Checkbutton(
            acq,
            text="Resistência no gráfico: escala log (modo R)",
            variable=self.chart_resistance_log_var,
            command=self._on_resistance_log_toggle,
        )
        log_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
        self._widgets.append(log_check)

        charts = ttk.LabelFrame(right_col, text="Gráficos", padding=12)
        charts.pack(fill="x", expand=False, pady=(0, 10))
        ttk.Label(
            charts,
            text="Tecto |força| dinamómetro (0 ou vazio = eixo só aos dados; mesma unidade que N/kgf)",
            wraplength=360,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self._add_row(charts, 1, "Valor máx. absoluto (0=auto)", self.dyno_chart_max_abs_var)
        self._add_row(
            charts,
            2,
            "Janela do gráfico (s, eixo X — últimos N s visíveis)",
            self.chart_window_var,
        )

        ttk.Label(
            right_col,
            text="Alterações aplicam-se ao clicar Iniciar. Pare a aquisição para editar.",
            wraplength=360,
        ).pack(fill="x", pady=(8, 0))

    def _add_row(
        self,
        parent: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=variable, width=36)
        entry.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=4)
        parent.columnconfigure(1, weight=1)
        self._widgets.append(entry)

    def _add_combo(
        self,
        parent: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
        values: list[str],
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        combo = ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            state="readonly",
            width=34,
        )
        combo.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=4)
        parent.columnconfigure(1, weight=1)
        self._widgets.append(combo)

    def _add_check(
        self,
        parent: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.BooleanVar,
    ) -> None:
        check = ttk.Checkbutton(parent, text=label, variable=variable)
        check.grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        self._widgets.append(check)

    def set_enabled(self, enabled: bool) -> None:
        entry_state = "normal" if enabled else "disabled"
        combo_state = "readonly" if enabled else "disabled"
        for widget in self._widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state=combo_state)
            elif isinstance(widget, ttk.Entry):
                widget.configure(state=entry_state)
            elif isinstance(widget, ttk.Checkbutton):
                widget.configure(state=entry_state)

    def apply_to_config(self) -> None:
        port = self.dyno_port_var.get().strip()
        if not port:
            raise ValueError("Indique a porta COM do dinamómetro.")

        parity = self.dyno_parity_var.get().strip().upper()
        if parity not in {"N", "E", "O"}:
            raise ValueError("Paridade inválida. Use N, E ou O.")

        terminator = TERMINATOR_OPTIONS.get(self.dyno_command_terminator_var.get())
        if terminator is None:
            raise ValueError("Terminador de comando inválido.")

        try:
            baudrate = int(self.dyno_baud_var.get())
            bytesize = int(self.dyno_bytesize_var.get())
            stopbits = float(self.dyno_stopbits_var.get())
            stream_idle = float(self.dyno_stream_idle_var.get())
            sample_hz = float(self.sample_hz_var.get())
        except ValueError as exc:
            raise ValueError("Valores numéricos inválidos na configuração.") from exc

        if baudrate <= 0:
            raise ValueError("Baudrate deve ser maior que zero.")
        if bytesize not in {7, 8}:
            raise ValueError("Bytesize deve ser 7 ou 8.")
        if stopbits not in {1.0, 2.0}:
            raise ValueError("Stop bits deve ser 1 ou 2.")
        if stream_idle <= 0:
            raise ValueError("Tempo sem dados deve ser maior que zero.")
        if sample_hz <= 0:
            raise ValueError("Taxa de aquisição deve ser maior que zero.")

        dur_raw = self.acquisition_duration_var.get().strip()
        if not dur_raw:
            duration_s = 0.0
        else:
            try:
                duration_s = float(dur_raw.replace(",", "."))
            except ValueError as exc:
                raise ValueError("Duração máxima da sessão inválida. Use número ≥ 0 ou 0 para ilimitada.") from exc
            if duration_s < 0:
                raise ValueError("Duração máxima da sessão não pode ser negativa.")

        force_unit = self.dyno_force_unit_var.get().strip()
        if force_unit not in {"N", "kgf"}:
            raise ValueError("Unidade de força inválida. Use N ou kgf.")

        self.config.visa_resource = self.visa_resource_var.get().strip()
        self.config.auto_discover_visa = self.auto_discover_var.get()
        self.config.dyno_port = port
        self.config.dyno_baudrate = baudrate
        self.config.dyno_bytesize = bytesize
        self.config.dyno_parity = parity
        self.config.dyno_stopbits = stopbits
        self.config.dyno_rtscts = self.dyno_rtscts_var.get()
        self.config.dyno_assert_rts = self.dyno_assert_rts_var.get()
        self.config.dyno_assert_dtr = self.dyno_assert_dtr_var.get()
        self.config.dyno_stream_enabled = self.dyno_stream_enabled_var.get()
        self.config.dyno_start_command = self.dyno_start_command_var.get()
        self.config.dyno_stop_command = self.dyno_stop_command_var.get().strip()
        self.config.dyno_command_terminator = terminator
        self.config.dyno_stream_idle_seconds = stream_idle
        self.config.dyno_force_unit = force_unit
        self.config.sample_hz = sample_hz
        self.config.acquisition_duration_seconds = duration_s
        self.config.chart_resistance_log_scale = self.chart_resistance_log_var.get()
        raw_cap = self.dyno_chart_max_abs_var.get().strip()
        if not raw_cap:
            self.config.dyno_chart_max_abs_force = 0.0
        else:
            try:
                cap = float(raw_cap.replace(",", "."))
            except ValueError as exc:
                raise ValueError(
                    "Tecto do gráfico de força inválido. Use número ≥ 0 ou deixe vazio."
                ) from exc
            if cap < 0:
                raise ValueError("Tecto do gráfico de força não pode ser negativo.")
            self.config.dyno_chart_max_abs_force = cap

        try:
            chart_window = int(self.chart_window_var.get().strip())
        except ValueError as exc:
            raise ValueError("Janela do gráfico inválida. Use um número inteiro (segundos).") from exc
        if chart_window < 5:
            raise ValueError("Janela do gráfico deve ser pelo menos 5 s.")
        if chart_window > 86400:
            raise ValueError("Janela do gráfico não pode exceder 86400 s (24 h).")
        self.config.chart_window_seconds = chart_window

    def _on_resistance_log_toggle(self) -> None:
        self.config.chart_resistance_log_scale = self.chart_resistance_log_var.get()
        if self._on_chart_resistance_log_changed is not None:
            self._on_chart_resistance_log_changed()

    @staticmethod
    def _terminator_label_for(value: str) -> str:
        for label, token in TERMINATOR_OPTIONS.items():
            if token == value:
                return label
        return "LF"
