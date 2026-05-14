from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


def now_iso_ms() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


@dataclass(slots=True)
class ReadingEvent:
    ts: str
    source: str
    value: float
    unit: str
    status: str = "OK"
    mode: Optional[str] = None
    raw: str = ""


@dataclass(slots=True)
class StatusEvent:
    ts: str
    source: str
    state: str
    detail: str = ""
