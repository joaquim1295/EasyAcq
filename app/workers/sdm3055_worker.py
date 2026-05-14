from __future__ import annotations

import logging
import math
import threading
import time
from typing import Optional

import pyvisa

from app.config import AppConfig
from app.core.bus import EventBus
from app.core.events import ReadingEvent, StatusEvent, now_iso_ms
from app.services.scpi_utils import MeasurementOverloadError, parse_measurement_value
from app.services.visa_discovery import open_multimeter

logger = logging.getLogger("acq.dmm")

MODE_MAP = {
    "DCV": ("V", ["MEAS:VOLT:DC?", "READ?"], ["CONF:VOLT:DC", "CONF:VOLT:DC AUTO"]),
    "ACV": ("V", ["MEAS:VOLT:AC?", "READ?"], ["CONF:VOLT:AC", "CONF:VOLT:AC AUTO"]),
    "DCI": ("A", ["MEAS:CURR:DC?", "READ?"], ["CONF:CURR:DC", "CONF:CURR:DC AUTO"]),
    "ACI": ("A", ["MEAS:CURR:AC?", "READ?"], ["CONF:CURR:AC", "CONF:CURR:AC AUTO"]),
    "R": ("OHM", ["MEAS:RES?", "READ?"], ["CONF:RES", "CONF:RES AUTO"]),
}


class SDM3055Worker(threading.Thread):
    def __init__(
        self,
        config: AppConfig,
        bus: EventBus,
        stop_event: threading.Event,
        selected_mode: "dict[str, str]",
    ) -> None:
        super().__init__(daemon=True, name="SDM3055Worker")
        self.config = config
        self.bus = bus
        self.stop_event = stop_event
        self.selected_mode = selected_mode
        self._resolved_resource: str = ""

    def run(self) -> None:
        backoff = self.config.reconnect_backoff_initial
        rm = pyvisa.ResourceManager()
        try:
            while not self.stop_event.is_set():
                inst: Optional[pyvisa.resources.MessageBasedResource] = None
                try:
                    inst, resource, idn = open_multimeter(
                        rm,
                        configured_resource=self.config.visa_resource,
                        auto_discover=self.config.auto_discover_visa,
                        idn_hints=self.config.visa_idn_hints,
                        vendor_id=self.config.visa_vendor_id,
                        product_id=self.config.visa_product_id,
                    )
                    self._resolved_resource = resource
                    self.config.visa_resource = resource
                    self.config.last_dmm_idn = idn.strip() if isinstance(idn, str) else str(idn)
                    logger.info("Ligacao VISA em %s (%s)", resource, idn)

                    self.bus.publish_status(
                        StatusEvent(
                            ts=now_iso_ms(),
                            source="dmm",
                            state="CONNECTED",
                            detail=f"{idn} @ {resource}",
                        )
                    )
                    backoff = self.config.reconnect_backoff_initial
                    self._acquire_loop(inst)
                except Exception as exc:
                    logger.exception("Erro no worker SDM3055: %s", exc)
                    detail = str(exc)
                    if self._resolved_resource:
                        detail = f"{detail} (ultimo recurso: {self._resolved_resource})"
                    self.bus.publish_status(
                        StatusEvent(
                            ts=now_iso_ms(),
                            source="dmm",
                            state="ERROR",
                            detail=detail,
                        )
                    )
                    self.bus.publish_status(
                        StatusEvent(
                            ts=now_iso_ms(),
                            source="dmm",
                            state="RECONNECTING",
                            detail=f"Nova tentativa em {backoff:.1f}s",
                        )
                    )
                    time.sleep(backoff)
                    backoff = min(backoff * 2.0, self.config.reconnect_backoff_max)
                finally:
                    if inst is not None:
                        try:
                            inst.close()
                        except Exception:
                            logger.debug("Falha ao fechar sessao VISA", exc_info=True)
        finally:
            try:
                rm.close()
            except Exception:
                logger.debug("Falha ao fechar ResourceManager", exc_info=True)

    def _acquire_loop(self, inst: pyvisa.resources.MessageBasedResource) -> None:
        period = 1.0 / max(self.config.sample_hz, 0.1)
        last_mode: Optional[str] = None
        while not self.stop_event.is_set():
            mode = self.selected_mode.get("dmm", "DCV")
            unit, measure_cmds, config_cmds = MODE_MAP.get(mode, MODE_MAP["DCV"])
            try:
                if mode != last_mode:
                    self._configure_mode(inst, config_cmds)
                    last_mode = mode
                    time.sleep(0.15)
                raw = self._read_value(inst, measure_cmds)
                value = parse_measurement_value(raw)
                if mode == "R":
                    if not math.isfinite(value) or value <= 0.0:
                        raise ValueError("Resistencia nao positiva ou nao finita")
                self.bus.publish_reading(
                    ReadingEvent(
                        ts=now_iso_ms(),
                        source="dmm",
                        mode=mode,
                        value=value,
                        unit=unit,
                        status="OK",
                        raw=raw.strip(),
                    )
                )
            except MeasurementOverloadError as exc:
                self.bus.publish_reading(
                    ReadingEvent(
                        ts=now_iso_ms(),
                        source="dmm",
                        mode=mode,
                        value=float("nan"),
                        unit=unit,
                        status="OVERLOAD",
                        raw=exc.raw[:500],
                    )
                )
            except pyvisa.errors.VisaIOError as exc:
                logger.exception("Falha de comunicacao SDM3055 no modo %s: %s", mode, exc)
                self.bus.publish_status(
                    StatusEvent(
                        ts=now_iso_ms(),
                        source="dmm",
                        state="ERROR",
                        detail=str(exc),
                    )
                )
                raise
            except Exception as exc:
                logger.warning("Leitura SDM3055 invalida no modo %s: %s", mode, exc)
                self.bus.publish_reading(
                    ReadingEvent(
                        ts=now_iso_ms(),
                        source="dmm",
                        mode=mode,
                        value=0.0,
                        unit=unit,
                        status="STALE",
                        raw=str(exc),
                    )
                )
            time.sleep(period)

    @staticmethod
    def _configure_mode(inst: pyvisa.resources.MessageBasedResource, config_cmds: list[str]) -> None:
        accepted = 0
        for cmd in config_cmds:
            try:
                logger.info("A enviar configuracao SCPI: %s", cmd)
                inst.write(cmd)
                accepted += 1
            except Exception as exc:
                logger.warning("Comando %s falhou: %s", cmd, exc)
        if accepted == 0:
            logger.warning(
                "Nenhum comando de configuracao SCPI aceite; a continuar com leitura direta"
            )

    @staticmethod
    def _read_value(inst: pyvisa.resources.MessageBasedResource, measure_cmds: list[str]) -> str:
        last_exc: Optional[Exception] = None
        for cmd in measure_cmds:
            try:
                return inst.query(cmd)
            except Exception as exc:
                last_exc = exc
                logger.warning("Comando %s falhou: %s", cmd, exc)
        raise RuntimeError(f"Nenhum comando de leitura respondeu: {last_exc}")
