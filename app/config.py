from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    visa_resource: str = ""
    auto_discover_visa: bool = True
    visa_idn_hints: tuple[str, ...] = ("SDM3055", "SIGLENT", "SDM30")
    visa_vendor_id: int = 0xF4EC
    visa_product_id: int = 0xEE38
    verbose_logging: bool = True
    last_dmm_idn: str = ""
    dyno_port: str = "COM6"
    dyno_baudrate: int = 2400
    dyno_bytesize: int = 8
    dyno_parity: str = "N"
    dyno_stopbits: float = 1.0
    dyno_rtscts: bool = True
    dyno_assert_rts: bool = True
    dyno_assert_dtr: bool = True
    dyno_stream_enabled: bool = True
    dyno_start_command: str = "p"
    dyno_stop_command: str = ""
    dyno_command_terminator: str = "\n"
    dyno_stream_idle_seconds: float = 5.0
    dyno_frame_chars: int = 6
    dyno_force_unit: str = "N"
    # 0 = eixo Y só aos dados (+margem); >0 = |força| limitada a este valor (mesma unidade que dyno_force_unit).
    dyno_chart_max_abs_force: float = 0.0
    dyno_serial_settle_seconds: float = 0.35
    chart_resistance_log_scale: bool = False
    chart_show_integrated: bool = False
    worker_join_timeout_seconds: float = 8.0
    sample_hz: float = 10.0
    # 0 = sessão até premir Parar; >0 = paragem automática ao fim deste tempo (segundos).
    acquisition_duration_seconds: float = 0.0
    ui_refresh_hz: float = 3.0
    chart_window_seconds: int = 60
    queue_maxsize: int = 5000
    csv_dir: Path = field(default_factory=lambda: Path("data"))
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    csv_flush_interval_seconds: float = 1.0
    csv_batch_size: int = 20
    reconnect_backoff_initial: float = 1.0
    reconnect_backoff_max: float = 30.0

    def ensure_dirs(self) -> None:
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
