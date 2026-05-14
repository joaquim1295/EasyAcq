from __future__ import annotations

import re

# Trama tipo dinamómetro: opcionalmente '-', dígitos, ponto, dígitos (ex.: -000.0, -016.7, 001.0).
_FRAME_PATTERN = re.compile(r"^-?\d{1,6}\.\d{1,6}$")
_FRAME_SCAN = re.compile(r"-?\d{1,6}\.\d{1,6}")


def consume_stream_frames(
    carry: str,
    text: str,
    *,
    preferred_frame_len: int = 9,
    max_remainder: int = 128,
    max_scan_chars: int = 16384,
) -> tuple[list[float], list[str], str]:
    """Extrai valores numéricos de um fluxo contínuo (tramas coladas sem separador).

    Usa correspondência por regex em vez de comprimento fixo, para formatos como
    ``-000.0-000.0-016.7`` que o alinhamento por janela de N bytes desvirtuava.
    O parâmetro ``preferred_frame_len`` mantém-se por compatibilidade com chamadas
    existentes; é ignorado na extração actual.
    """
    _ = preferred_frame_len  # API legada; ver docstring.
    data = f"{carry}{text}"
    tail = ""
    if len(data) > max_scan_chars:
        chunk = data[:max_scan_chars]
        tail = data[max_scan_chars:]
    else:
        chunk = data

    values: list[float] = []
    frames: list[str] = []
    last_end = 0
    for match in _FRAME_SCAN.finditer(chunk):
        token = match.group(0)
        if _FRAME_PATTERN.fullmatch(token):
            values.append(float(token))
            frames.append(token)
            last_end = match.end()

    remainder = chunk[last_end:] + tail
    if len(remainder) > max_remainder:
        remainder = remainder[-max_remainder:]
    return values, frames, remainder
