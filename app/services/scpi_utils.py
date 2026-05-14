from __future__ import annotations

import math
import re

_MEASUREMENT_RE = re.compile(
    r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
)

def _looks_like_textual_overload(normalized: str) -> bool:
    """Detecta tokens OL / O.L / OPEN na resposta textual do instrumento."""
    up = normalized.upper()
    if "OPEN" in up.replace(" ", ""):
        return True
    for part in re.split(r"[,;]", up):
        for tok in part.split():
            t = tok.strip("+-").strip()
            if t in {"OL", "O.L", "0.L"}:
                return True
    return False


# Valores acima disto são tratados como overload (ex.: 9.9E+37), não como medição.
_OVERLOAD_ABS_THRESHOLD = 1e20


class MeasurementOverloadError(ValueError):
    """Resposta indica overload / circuito aberto ou sentinel, não um valor finito utilizável."""

    __slots__ = ("raw",)

    def __init__(self, raw: str) -> None:
        super().__init__(f"Overload ou resposta invalida: {raw!r}")
        self.raw = raw


def parse_measurement_value(raw: str) -> float:
    normalized = raw.strip().replace(",", ".")
    if not normalized:
        raise MeasurementOverloadError(raw.strip())
    if _looks_like_textual_overload(normalized):
        raise MeasurementOverloadError(raw.strip())
    match = _MEASUREMENT_RE.search(normalized)
    if not match:
        raise ValueError(f"Resposta sem valor numerico: {raw!r}")
    value = float(match.group(0))
    if not math.isfinite(value):
        raise MeasurementOverloadError(raw.strip())
    if abs(value) >= _OVERLOAD_ABS_THRESHOLD:
        raise MeasurementOverloadError(raw.strip())
    return value
