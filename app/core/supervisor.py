from __future__ import annotations

import threading
from queue import Queue

from app.config import AppConfig
from app.core.bus import EventBus
from app.core.events import ReadingEvent
from app.services.csv_writer import CsvWriter
from app.workers.dyno_worker import DynoWorker
from app.workers.sdm3055_worker import SDM3055Worker


class Supervisor:
    def __init__(
        self,
        config: AppConfig,
        bus: EventBus,
        csv_queue: "Queue[ReadingEvent]",
        *,
        session_csv_id: str,
    ) -> None:
        self.config = config
        self.bus = bus
        self.stop_event = threading.Event()
        self.selected_mode: dict[str, str] = {"dmm": "DCV"}
        self.csv_writer = CsvWriter(
            config, csv_queue, self.stop_event, self.selected_mode, session_csv_id
        )
        self.dmm_worker = SDM3055Worker(config, bus, self.stop_event, self.selected_mode)
        self.dyno_worker = DynoWorker(config, bus, self.stop_event)

    def start(self) -> None:
        self.csv_writer.start()
        self.dmm_worker.start()
        self.dyno_worker.start()

    def stop(self) -> None:
        self.stop_event.set()
        timeout = self.config.worker_join_timeout_seconds
        self.dyno_worker.join(timeout=timeout)
        for t in (self.dmm_worker, self.csv_writer):
            t.join(timeout=timeout)

    def set_multimeter_mode(self, mode: str) -> None:
        self.selected_mode["dmm"] = mode
