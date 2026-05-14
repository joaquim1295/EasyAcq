from __future__ import annotations

import pytest

from app.services.scpi_utils import MeasurementOverloadError, parse_measurement_value
from app.services.chart_scales import format_resistance_y_tick_engineering_mohm


def test_parse_normal() -> None:
    assert parse_measurement_value("  +1.23456E-3 \n") == pytest.approx(0.00123456)


def test_parse_overload_sentinel() -> None:
    with pytest.raises(MeasurementOverloadError):
        parse_measurement_value("9.90000000E+37")


def test_parse_overload_ol_tokens() -> None:
    for raw in ("OL", "+OL", "O.L", "0.L", "OPEN", "  OPEN CIRCUIT "):
        with pytest.raises(MeasurementOverloadError):
            parse_measurement_value(raw)


def test_parse_no_numeric() -> None:
    with pytest.raises(ValueError):
        parse_measurement_value("COLUMN")


def test_engineering_tick_labels() -> None:
    assert "Ω" in format_resistance_y_tick_engineering_mohm(1e-6, 0)
    assert "kΩ" in format_resistance_y_tick_engineering_mohm(0.001, 0)
    assert "MΩ" in format_resistance_y_tick_engineering_mohm(1.0, 0)
    assert format_resistance_y_tick_engineering_mohm(0.0, 0) == ""
    assert format_resistance_y_tick_engineering_mohm(-1.0, 0) == ""
