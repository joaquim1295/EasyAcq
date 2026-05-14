from __future__ import annotations

import math
import re

NEWTON_PER_KGF = 9.80665

DYNO_FORCE_UNITS = ("N", "kgf")

INSTRUMENT_LABELS = {
    "dmm": "Multímetro",
    "dyno": "Dinamómetro",
}

_INSTRUMENT_CANONICAL = {
    "sdm3055": "dmm",
    "dmm": "dmm",
    "multimetro": "dmm",
    "multímetro": "dmm",
    "dyno": "dyno",
    "dinamometro": "dyno",
    "dinamómetro": "dyno",
}

_OHM_UNIT_RE = re.compile(r"^O(HM|HMS)$", re.IGNORECASE)


def instrument_canonical(source: str) -> str:
    x = (source or "").strip().lower()
    return _INSTRUMENT_CANONICAL.get(x, x)


def normalize_dyno_force_unit(unit: str) -> str:
    normalized = unit.strip().lower()
    if normalized == "kgf":
        return "kgf"
    if normalized == "n":
        return "N"
    raise ValueError("Unidade de força inválida. Use N ou kgf.")


def convert_force_from_newton(value_newton: float, unit: str) -> tuple[float, str]:
    selected = normalize_dyno_force_unit(unit)
    if selected == "kgf":
        return value_newton / NEWTON_PER_KGF, "kgf"
    return value_newton, "N"


def dyno_force_mode(unit: str) -> str:
    selected = normalize_dyno_force_unit(unit)
    if selected == "kgf":
        return "FORCE_KGF"
    return "FORCE_N"


def instrument_label(source: str) -> str:
    key = instrument_canonical(source)
    return INSTRUMENT_LABELS.get(key, source)


def format_dyno_force(value: float, unit: str) -> str:
    normalize_dyno_force_unit(unit)
    return f"{value:+.4f}"


def format_sdm_value(value: float) -> str:
    return f"{value:.6f}"


def is_sdm_resistance_si_ohm_unit(unit: str) -> bool:
    """Unidade SI em ohm vinda do instrumento (ex.: OHM), antes de conversão para MΩ."""
    u = (unit or "").strip()
    if not u:
        return False
    if "Ω" in u or "Ω" in u:
        return True
    return bool(_OHM_UNIT_RE.match(u))


def is_sdm_resistance_megohm_display_unit(unit: str) -> bool:
    """Valor já expresso em megaohm (ex.: coluna de exportação do gráfico)."""
    u = (unit or "").strip()
    if not u:
        return False
    ul = u.upper().replace(" ", "")
    if ul in {"MOHM", "MEGOHM", "MEGOHMS"}:
        return True
    return u.startswith("M") and ("Ω" in u or "\u03a9" in u)


def _format_megohm_scalar(megohms: float) -> str:
    mv = float(megohms)
    if mv == 0.0:
        return "0"
    a = abs(mv)
    if a >= 1000:
        return f"{mv:.4g}"
    if a >= 100:
        return f"{mv:.3f}"
    if a >= 10:
        return f"{mv:.4f}"
    if a >= 1:
        return f"{mv:.5f}"
    if a >= 0.01:
        return f"{mv:.6f}"
    return f"{mv:.6g}"


def format_reading_value(source: str, value: float, unit: str) -> str:
    key = instrument_canonical(source)
    if key == "dyno":
        return format_dyno_force(value, unit)
    if key == "dmm":
        if is_sdm_resistance_megohm_display_unit(unit):
            return _format_megohm_scalar(value)
        if is_sdm_resistance_si_ohm_unit(unit):
            return _format_megohm_scalar(value / 1_000_000.0)
    return format_sdm_value(value)


def format_reading_value_csv(source: str, value: float, unit: str, mode: str | None = None) -> str:
    """CSV: dinamómetro com 2 casas decimais; multímetro com a mesma precisão que format_reading_value."""
    key = instrument_canonical(source)
    if key == "dyno":
        normalize_dyno_force_unit(unit)
        if not math.isfinite(value):
            return ""
        return f"{value:+.2f}"
    if key == "dmm":
        return format_reading_value(source, value, unit)
    try:
        x = float(value)
    except (TypeError, ValueError):
        return ""
    return format_sdm_value(x) if math.isfinite(x) else ""


def format_reading_display_unit(source: str, unit: str, mode: str | None) -> str:
    """Unidade mostrada em CSV/UI (MΩ para resistência em modo R)."""
    key = instrument_canonical(source)
    if key == "dmm" and (mode or "").strip().upper() == "R" and is_sdm_resistance_si_ohm_unit(unit):
        return "MΩ"
    return unit


def format_reading_with_unit(source: str, value: float, unit: str, mode: str | None = None) -> str:
    """Texto completo valor + unidade para painel (evita duplicar Ω)."""
    num = format_reading_value(source, value, unit)
    u = format_reading_display_unit(source, unit, mode)
    return f"{num} {u}".strip()
