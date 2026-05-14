from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import AppConfig

SETTINGS_PATH = Path("data") / "user_settings.json"

_PERSIST_KEYS = (
    "visa_resource",
    "auto_discover_visa",
    "dyno_port",
    "dyno_baudrate",
    "dyno_bytesize",
    "dyno_parity",
    "dyno_stopbits",
    "dyno_rtscts",
    "dyno_assert_rts",
    "dyno_assert_dtr",
    "dyno_stream_enabled",
    "dyno_start_command",
    "dyno_stop_command",
    "dyno_command_terminator",
    "dyno_stream_idle_seconds",
    "dyno_frame_chars",
    "dyno_force_unit",
    "dyno_chart_max_abs_force",
    "sample_hz",
    "acquisition_duration_seconds",
    "chart_window_seconds",
    "chart_resistance_log_scale",
    "chart_show_integrated",
    "last_dmm_idn",
    "ui_refresh_hz",
    "verbose_logging",
)


def load_user_settings(config: AppConfig, path: Path | None = None) -> None:
    target = path or SETTINGS_PATH
    if not target.exists():
        return
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(raw, dict):
        return
    # Migração: identificação do multímetro em ficheiros antigos
    if "last_sdm_idn" in raw and not getattr(config, "last_dmm_idn", ""):
        setattr(config, "last_dmm_idn", str(raw["last_sdm_idn"]))
    for key in _PERSIST_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if not hasattr(config, key):
            continue
        current = getattr(config, key)
        if isinstance(current, Path):
            setattr(config, key, Path(str(value)))
        elif isinstance(current, bool):
            setattr(config, key, bool(value))
        elif isinstance(current, int) and not isinstance(current, bool):
            setattr(config, key, int(value))
        elif isinstance(current, float):
            setattr(config, key, float(value))
        elif isinstance(current, tuple):
            if isinstance(value, list):
                setattr(config, key, tuple(str(x) for x in value))
        else:
            setattr(config, key, value)


def save_user_settings(config: AppConfig, path: Path | None = None) -> None:
    target = path or SETTINGS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {}
    for key in _PERSIST_KEYS:
        value = getattr(config, key, None)
        if isinstance(value, Path):
            payload[key] = str(value)
        elif isinstance(value, tuple):
            payload[key] = list(value)
        else:
            payload[key] = value
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
