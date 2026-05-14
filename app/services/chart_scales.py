from __future__ import annotations

import math
from collections.abc import Iterable

from app.services.units import NEWTON_PER_KGF, normalize_dyno_force_unit

MEG_OHM = 1_000_000.0
# Eixo do gráfico em modo R trabalha em MΩ (valores do deque já convertidos).
DMM_R_MOHM_MIN_POS = 1e-9
Y_PADDING_RATIO = 0.05


def dmm_chart_yscale(mode: str, resistance_log_scale: bool = True) -> str:
    if mode.strip().upper() == "R" and resistance_log_scale:
        return "log"
    return "linear"


def dmm_chart_ylabel(mode: str, resistance_log_scale: bool = True) -> str:
    selected = mode.strip().upper()
    if selected == "R":
        return "MΩ (log)" if resistance_log_scale else "MΩ (linear)"
    if selected in {"DCV", "ACV"}:
        return "V"
    if selected in {"DCI", "ACI"}:
        return "A"
    return ""


def dmm_chart_ylim(mode: str, values: Iterable[float]) -> tuple[float, float]:
    selected = mode.strip().upper()
    if selected == "R":
        return _resistance_chart_ylim_mohm(values)
    vals = list(values)
    if not vals:
        return 0.0, 1.0
    return _padded_linear_range(vals, floor=0.0)


def dyno_chart_ylabel(force_unit: str, max_abs_force: float = 0.0) -> str:
    selected = normalize_dyno_force_unit(force_unit)
    unit = "kgf" if selected == "kgf" else "N"
    cap = float(max_abs_force)
    if cap > 0.0:
        return f"{unit} ±{cap:g}"
    return unit


def dyno_chart_ylim(
    force_unit: str,
    values: Iterable[float],
    max_abs_force: float = 0.0,
) -> tuple[float, float]:
    selected = normalize_dyno_force_unit(force_unit)
    vals = list(values)
    cap = float(max_abs_force) if max_abs_force > 0.0 else 0.0

    if not vals:
        if cap > 0.0:
            return -cap, cap
        if selected == "kgf":
            return -0.3, 0.3
        return -5.0, 5.0

    ymin, ymax = _padded_linear_range(vals, floor=None)
    if cap > 0.0:
        ymin = max(ymin, -cap)
        ymax = min(ymax, cap)
        if ymin >= ymax:
            mid = 0.5 * (ymin + ymax)
            span = max(abs(cap) * 0.05, 1e-6)
            return mid - span, mid + span
    return ymin, ymax


def _padded_linear_range(
    values: list[float],
    *,
    floor: float | None = 0.0,
) -> tuple[float, float]:
    ymin = min(values)
    ymax = max(values)
    if ymin == ymax:
        margin = max(abs(ymax) * Y_PADDING_RATIO, 1e-9)
        lo, hi = ymin - margin, ymax + margin
    else:
        margin = (ymax - ymin) * Y_PADDING_RATIO
        lo, hi = ymin - margin, ymax + margin
    if floor is not None:
        lo = max(floor, lo)
    return lo, hi


def _resistance_chart_ylim_mohm(values: Iterable[float]) -> tuple[float, float]:
    positives = [value for value in values if value > DMM_R_MOHM_MIN_POS]
    if not positives:
        return DMM_R_MOHM_MIN_POS, 1.0
    ymin = min(positives)
    ymax = max(positives)
    if ymin == ymax:
        log_min = math.log10(ymin)
        log_max = log_min + 1.0
    else:
        log_min = math.log10(ymin)
        log_max = math.log10(ymax)
        span = max(log_max - log_min, 0.1)
        log_min -= span * Y_PADDING_RATIO
        log_max += span * Y_PADDING_RATIO
    lower = max(DMM_R_MOHM_MIN_POS, 10**log_min)
    upper = 10**log_max
    if lower >= upper:
        upper = lower * 10.0
    return lower, upper


def format_resistance_y_tick_engineering_mohm(value: float, pos: int) -> str:
    """Rótulos de eixo Y (matplotlib): valores em MΩ → Ω, kΩ ou MΩ."""
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        return ""
    ohms = float(value) * MEG_OHM
    if ohms >= 1e6:
        return f"{ohms / 1e6:g} MΩ"
    if ohms >= 1e3:
        return f"{ohms / 1e3:g} kΩ"
    return f"{ohms:g} Ω"
