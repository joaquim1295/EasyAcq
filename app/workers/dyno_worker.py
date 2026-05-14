from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import serial

from app.config import AppConfig
from app.core.bus import EventBus
from app.core.events import ReadingEvent, StatusEvent, now_iso_ms
from app.services.dyno_parser import consume_stream_frames
from app.services.units import convert_force_from_newton, dyno_force_mode

logger = logging.getLogger("acq.dyno")


class DynoWorker(threading.Thread):
    def __init__(self, config: AppConfig, bus: EventBus, stop_event: threading.Event) -> None:
        super().__init__(daemon=True, name="DynoWorker")
        self.config = config
        self.bus = bus
        self.stop_event = stop_event

    def run(self) -> None:
        backoff = self.config.reconnect_backoff_initial
        while not self.stop_event.is_set():
            ser: Optional[serial.Serial] = None
            try:
                serial_kwargs = self._serial_kwargs()
                logger.info("A abrir serial: %s", serial_kwargs)
                ser = serial.Serial(**serial_kwargs)
                self._reset_serial_buffers(ser)
                self._prepare_serial_lines(ser)
                mode = "stream" if self.config.dyno_stream_enabled else "passivo"
                start_label = ""
                if self.config.dyno_stream_enabled:
                    start_label = (
                        f" | arranque {self.config.dyno_start_command!r}"
                        f"{self.config.dyno_command_terminator!r}"
                    )
                self.bus.publish_status(
                    StatusEvent(
                        ts=now_iso_ms(),
                        source="dyno",
                        state="CONNECTED",
                        detail=(
                            f"{self.config.dyno_port} @ {self.config.dyno_baudrate} baud"
                            f" | modo {mode}{start_label}"
                        ),
                    )
                )
                backoff = self.config.reconnect_backoff_initial
                if self.config.dyno_stream_enabled:
                    time.sleep(self.config.dyno_serial_settle_seconds)
                    self._send_command(ser, self.config.dyno_start_command)
                    self._read_loop(ser, idle_detail="Sem dados no stream; verifique baudrate e comando de arranque")
                else:
                    self._read_loop(ser, idle_detail="Sem dados na serial; a aguardar stream")
            except Exception as exc:
                logger.exception("Erro no worker do dinamometro: %s", exc)
                self.bus.publish_status(
                    StatusEvent(
                        ts=now_iso_ms(), source="dyno", state="ERROR", detail=str(exc)
                    )
                )
                if not self.stop_event.is_set():
                    self.bus.publish_status(
                        StatusEvent(
                            ts=now_iso_ms(),
                            source="dyno",
                            state="RECONNECTING",
                            detail=f"Nova tentativa em {backoff:.1f}s",
                        )
                    )
                    time.sleep(backoff)
                    backoff = min(backoff * 2.0, self.config.reconnect_backoff_max)
            finally:
                if ser is not None:
                    self._release_serial(ser)

    def _serial_kwargs(self) -> dict:
        parity_map = {
            "N": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
        }
        stopbits = (
            serial.STOPBITS_ONE
            if int(self.config.dyno_stopbits) == 1
            else serial.STOPBITS_TWO
        )
        return {
            "port": self.config.dyno_port,
            "baudrate": self.config.dyno_baudrate,
            "bytesize": self.config.dyno_bytesize,
            "parity": parity_map.get(self.config.dyno_parity.upper(), serial.PARITY_NONE),
            "stopbits": stopbits,
            "rtscts": self.config.dyno_rtscts,
            "timeout": 0.1,
            "write_timeout": 2.0,
        }

    def _prepare_serial_lines(self, ser: serial.Serial) -> None:
        if self.config.dyno_assert_rts:
            ser.rts = True
        if self.config.dyno_assert_dtr:
            ser.dtr = True
        logger.info(
            "Linhas seriais preparadas: rtscts=%s rts=%s dtr=%s",
            self.config.dyno_rtscts,
            ser.rts,
            ser.dtr,
        )

    def _reset_serial_buffers(self, ser: serial.Serial) -> None:
        if not ser.is_open:
            return
        ser.reset_input_buffer()
        ser.reset_output_buffer()

    def _send_command(self, ser: serial.Serial, command: str) -> None:
        if not command:
            return
        payload = f"{command}{self.config.dyno_command_terminator}".encode(
            "ascii", errors="ignore"
        )
        ser.write(payload)
        ser.flush()
        logger.info("Comando enviado ao dinamometro: %r", payload)

    def _release_serial(self, ser: serial.Serial) -> None:
        if not ser.is_open:
            return
        try:
            self._send_command(ser, self.config.dyno_stop_command)
            time.sleep(self.config.dyno_serial_settle_seconds)
            self._reset_serial_buffers(ser)
        finally:
            ser.close()
            logger.info("Porta serial fechada: %s", self.config.dyno_port)

    def _read_loop(self, ser: serial.Serial, *, idle_detail: str) -> None:
        period = 1.0 / max(self.config.sample_hz, 0.1)
        carry = ""
        last_publish = 0.0
        last_data_at = time.monotonic()
        while not self.stop_event.is_set():
            chunks: list[bytes] = []
            first = ser.read(ser.in_waiting or 1)
            if first:
                chunks.append(first)
                while ser.in_waiting:
                    chunks.append(ser.read(ser.in_waiting))
                text = b"".join(chunks).decode(errors="ignore")
                values, frames, carry = consume_stream_frames(
                    carry,
                    text,
                    preferred_frame_len=self.config.dyno_frame_chars,
                )
                if values:
                    last_data_at = time.monotonic()
                    now = time.monotonic()
                    if now - last_publish >= period:
                        self._publish_value(values[-1], frames[-1])
                        last_publish = now
                continue

            if time.monotonic() - last_data_at > self.config.dyno_stream_idle_seconds:
                self.bus.publish_status(
                    StatusEvent(
                        ts=now_iso_ms(),
                        source="dyno",
                        state="CONNECTED",
                        detail=idle_detail,
                    )
                )
                last_data_at = time.monotonic()
            time.sleep(0.02)

    def _publish_value(self, value: float, raw_frame: str) -> None:
        converted, unit = convert_force_from_newton(value, self.config.dyno_force_unit)
        self.bus.publish_reading(
            ReadingEvent(
                ts=now_iso_ms(),
                source="dyno",
                mode=dyno_force_mode(unit),
                value=converted,
                unit=unit,
                status="OK",
                raw=raw_frame,
            )
        )
