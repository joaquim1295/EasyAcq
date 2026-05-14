from __future__ import annotations

import csv
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

from app.config import AppConfig
from app.core.events import ReadingEvent
from app.services.csv_format import (
    SAMPLE_CSV_HEADERS_PUBLIC,
    acquisition_metadata_lines,
    is_sample_reading,
    parse_event_timestamp,
    sample_row,
    write_comment_lines,
)


class CsvWriter(threading.Thread):
    def __init__(
        self,
        config: AppConfig,
        input_queue: "Queue[ReadingEvent]",
        stop_event: threading.Event,
        selected_mode: dict[str, str],
        session_csv_id: str,
    ) -> None:
        super().__init__(daemon=True, name="CsvWriter")
        self.config = config
        self.input_queue = input_queue
        self.stop_event = stop_event
        self.selected_mode = selected_mode
        self.session_csv_id = session_csv_id
        self._buffer: list[ReadingEvent] = []
        self._last_flush = time.monotonic()
        self._current_path: Optional[Path] = None
        self._next_sequence = 0
        self._origin_ts: Optional[datetime] = None

    def run(self) -> None:
        while not self.stop_event.is_set():
            self._collect_burst()
            self._flush_if_needed(force=False)
        self._drain_remaining_queue()
        self._flush_if_needed(force=True)

    def _collect_burst(self) -> None:
        try:
            event = self.input_queue.get(timeout=0.05)
        except Empty:
            return
        if is_sample_reading(event):
            self._buffer.append(event)
        self.input_queue.task_done()
        while True:
            try:
                event = self.input_queue.get_nowait()
            except Empty:
                break
            if is_sample_reading(event):
                self._buffer.append(event)
            self.input_queue.task_done()

    def _drain_remaining_queue(self) -> None:
        while True:
            try:
                event = self.input_queue.get_nowait()
            except Empty:
                break
            if is_sample_reading(event):
                self._buffer.append(event)
            try:
                self.input_queue.task_done()
            except ValueError:
                pass

    def _flush_if_needed(self, force: bool) -> None:
        if not self._buffer:
            return

        elapsed = time.monotonic() - self._last_flush
        if not force and len(self._buffer) < self.config.csv_batch_size:
            if elapsed < self.config.csv_flush_interval_seconds:
                return

        path = self._session_csv_path()
        is_new = not path.exists()
        with path.open("a", newline="", encoding="utf-8-sig") as handle:
            if is_new:
                write_comment_lines(
                    handle,
                    acquisition_metadata_lines(
                        self.config,
                        dmm_mode=self.selected_mode.get("dmm", "DCV"),
                        created=datetime.now(),
                    ),
                )
            writer = csv.writer(handle, delimiter=";")
            if is_new:
                writer.writerow(SAMPLE_CSV_HEADERS_PUBLIC)
            for event in self._buffer:
                if self._origin_ts is None:
                    self._origin_ts = parse_event_timestamp(event.ts)
                writer.writerow(
                    sample_row(
                        event,
                        sequence=self._next_sequence,
                        origin=self._origin_ts,
                    )
                )
                self._next_sequence += 1

        self._buffer.clear()
        self._last_flush = time.monotonic()
        self._current_path = path

    def _session_csv_path(self) -> Path:
        return self.config.csv_dir / f"dados_{self.session_csv_id}.csv"
