from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

import pyvisa

logger = logging.getLogger("acq.visa")

_USB_RESOURCE_RE = re.compile(r"^USB\d*::", re.IGNORECASE)


def list_visa_resources(rm: pyvisa.ResourceManager) -> list[str]:
    try:
        resources = list(rm.list_resources())
        logger.info("Recursos VISA listados: %s", resources)
        return resources
    except Exception as exc:
        logger.exception("Falha ao listar recursos VISA: %s", exc)
        return []


def _is_usb_instrument(resource: str) -> bool:
    return bool(_USB_RESOURCE_RE.match(resource)) and resource.upper().endswith("::INSTR")


def _resource_candidates(resources: Iterable[str], preferred: str) -> list[str]:
    ordered: list[str] = []
    if preferred:
        ordered.append(preferred)
    for resource in resources:
        if resource not in ordered and _is_usb_instrument(resource):
            ordered.append(resource)
    return ordered


def _matches_idn(idn: str, hints: tuple[str, ...]) -> bool:
    upper = idn.upper()
    return any(hint.upper() in upper for hint in hints)


def _matches_vendor_product(resource: str, vendor_id: Optional[int], product_id: Optional[int]) -> bool:
    upper = resource.upper()
    if vendor_id is not None and f"0x{vendor_id:X}" not in upper and f"0x{vendor_id:x}" not in upper:
        return False
    if product_id is not None and f"0x{product_id:X}" not in upper and f"0x{product_id:x}" not in upper:
        return False
    return vendor_id is not None or product_id is not None


def _configure_instrument(inst: pyvisa.resources.MessageBasedResource) -> None:
    inst.timeout = 5000
    inst.write_termination = "\n"
    inst.read_termination = "\n"


def open_multimeter(
    rm: pyvisa.ResourceManager,
    *,
    configured_resource: str,
    auto_discover: bool,
    idn_hints: tuple[str, ...],
    vendor_id: Optional[int],
    product_id: Optional[int],
) -> tuple[pyvisa.resources.MessageBasedResource, str, str]:
    resources = list_visa_resources(rm)
    if not resources:
        raise RuntimeError("Nenhum recurso VISA encontrado. Verifique NI-VISA e ligacao USB.")

    preferred = configured_resource.strip()
    candidates = _resource_candidates(resources, preferred) if auto_discover or not preferred else [preferred]
    failures: list[str] = []

    for resource in candidates:
        inst: Optional[pyvisa.resources.MessageBasedResource] = None
        try:
            logger.info("A abrir recurso VISA: %s", resource)
            inst = rm.open_resource(resource)
            _configure_instrument(inst)
            idn = inst.query("*IDN?").strip()
            logger.info("Recurso %s respondeu *IDN?: %s", resource, idn)
            if not auto_discover or _matches_idn(idn, idn_hints) or _matches_vendor_product(
                resource, vendor_id, product_id
            ):
                logger.info("Multimetro selecionado: %s (%s)", resource, idn)
                return inst, resource, idn
            failures.append(f"{resource}: IDN inesperado ({idn})")
            inst.close()
            inst = None
        except Exception as exc:
            failures.append(f"{resource}: {exc}")
            logger.warning("Falha ao abrir recurso %s: %s", resource, exc)
            if inst is not None:
                try:
                    inst.close()
                except Exception:
                    logger.debug("Falha ao fechar recurso %s", resource, exc_info=True)

    detail = "; ".join(failures) if failures else ", ".join(resources)
    raise RuntimeError(f"Nenhum multimetro compativel encontrado. Detalhes: {detail}")
