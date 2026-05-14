"""Verificacoes antes de importar a UI (matplotlib): runtime VC++ e backend VISA."""
from __future__ import annotations

import ctypes
import os
import sys


def _message_box(msg: str, title: str, *, warning: bool) -> None:
    if sys.platform != "win32":
        return
    MB_OK = 0
    MB_ICONWARNING = 0x30
    MB_ICONINFORMATION = 0x40
    flags = MB_OK | (MB_ICONWARNING if warning else MB_ICONINFORMATION)
    ctypes.windll.user32.MessageBoxW(None, msg, title, flags)


def check_vcruntime_loadable() -> tuple[bool, str]:
    """Garante que as DLL do MSVC usadas pelo Python empacotado podem ser carregadas."""
    if sys.platform != "win32":
        return True, ""
    try:
        ctypes.WinDLL("vcruntime140.dll")
    except OSError as e:
        return False, str(e)
    try:
        ctypes.WinDLL("vcruntime140_1.dll")
    except OSError:
        pass
    return True, ""


def check_pyvisa_backend() -> tuple[bool, str]:
    """Tenta abrir o Resource Manager VISA (NI-VISA / IVI)."""
    try:
        import pyvisa  # noqa: PLC0415

        rm = pyvisa.ResourceManager()
        try:
            rm.close()
        except Exception:
            pass
        return True, ""
    except Exception as e:
        return False, repr(e)


def warn_missing_prerequisites() -> None:
    """Avisos bloqueantes (VC++) ou informativos (VISA). So Windows."""
    if sys.platform != "win32":
        return

    ok_vc, vc_err = check_vcruntime_loadable()
    if not ok_vc:
        _message_box(
            "Nao foi possivel carregar o Microsoft Visual C++ Runtime (DLL em falta).\n\n"
            "Instale o pacote oficial «Visual C++ Redistributable 2015-2022 (x64)».\n"
            "Pagina:\n"
            "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist\n\n"
            f"Detalhe: {vc_err}",
            "EasyAcq — Visual C++",
            warning=True,
        )
        raise SystemExit(1)

    ok_visa, visa_err = check_pyvisa_backend()
    if not ok_visa:
        _message_box(
            "O NI-VISA (ou o backend VISA) nao esta acessivel neste computador.\n\n"
            "O multimetro SDM3055 (USB/GPIB-VISA) requer o NI-VISA instalado.\n"
            "Pagina:\n"
            "https://www.ni.com/en/support/downloads/drivers.download-ni-visa.html\n\n"
            "Pode continuar a usar apenas o dinamometro (porta serie) sem o multimetro.\n\n"
            f"Detalhe: {visa_err}",
            "EasyAcq — NI-VISA",
            warning=True,
        )
