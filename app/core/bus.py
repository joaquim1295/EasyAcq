from __future__ import annotations

import logging
import queue
from typing import Any

logger = logging.getLogger("acq.bus")


class EventBus:
    def __init__(self, maxsize: int = 5000) -> None:
        self.readings: "queue.Queue[Any]" = queue.Queue(maxsize=maxsize)
        self.status: "queue.Queue[Any]" = queue.Queue(maxsize=maxsize)
        self.readings_dropped = 0
        self.status_dropped = 0

    def publish_reading(self, event: Any) -> None:
        try:
            self.readings.put_nowait(event)
        except queue.Full:
            self.readings_dropped += 1
            if self.readings_dropped == 1 or self.readings_dropped % 250 == 0:
                logger.warning(
                    "Fila de leituras cheia; amostras descartadas (total=%s)",
                    self.readings_dropped,
                )
            _ = self.readings.get_nowait()
            self.readings.put_nowait(event)

    def publish_status(self, event: Any) -> None:
        try:
            self.status.put_nowait(event)
        except queue.Full:
            self.status_dropped += 1
            if self.status_dropped == 1 or self.status_dropped % 50 == 0:
                logger.warning(
                    "Fila de estado cheia; eventos descartados (total=%s)",
                    self.status_dropped,
                )
            _ = self.status.get_nowait()
            self.status.put_nowait(event)
