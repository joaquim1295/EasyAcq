from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import serial

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.dyno_parser import consume_stream_frames

COMMON_BAUDS = [2400, 9600, 19200, 38400, 57600, 115200]
PARITIES = [serial.PARITY_NONE, serial.PARITY_EVEN, serial.PARITY_ODD]
STOPBITS = [serial.STOPBITS_ONE, serial.STOPBITS_TWO]
BYTESIZES = [serial.EIGHTBITS, serial.SEVENBITS]


def now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def probe_stream(
    port: str,
    baud: int,
    parity: str,
    stopbits: float,
    bytesize: int,
    seconds: float,
    *,
    frame_chars: int,
) -> tuple[list[str], int]:
    """Lê a porta em blocos (como o worker), agregando tramas com o mesmo parser."""
    lines: list[str] = []
    frame_count = 0
    with serial.Serial(
        port=port,
        baudrate=baud,
        parity=parity,
        stopbits=stopbits,
        bytesize=bytesize,
        timeout=0.1,
    ) as ser:
        carry = ""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            first = ser.read(ser.in_waiting or 1)
            if not first:
                time.sleep(0.02)
                continue
            chunks: list[bytes] = [first]
            while ser.in_waiting:
                chunks.append(ser.read(ser.in_waiting))
            text = b"".join(chunks).decode(errors="ignore")
            _values, frames, carry = consume_stream_frames(
                carry, text, preferred_frame_len=frame_chars
            )
            for raw_frame in frames:
                frame_count += 1
                hex_dump = raw_frame.encode("ascii", errors="replace").hex(" ")
                lines.append(f"{now()} | frame={raw_frame!r} | hex={hex_dump}")
    return lines, frame_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover serial settings for dynamometer.")
    parser.add_argument("--port", default="COM6")
    parser.add_argument("--seconds", type=float, default=3.0, help="Capture window per configuration")
    parser.add_argument("--frame-chars", type=int, default=6, help="Comprimento preferido (legado; o parser usa regex)")
    parser.add_argument("--out", default="docs/dyno_discovery_report.md")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report: list[str] = [
        "# Dyno discovery report",
        "",
        f"- Port: `{args.port}`",
        f"- Generated: `{now()}`",
        f"- Stream parser: `consume_stream_frames` (regex; arg frame_chars={args.frame_chars} legado)",
        "",
        "## Attempts",
        "",
    ]
    best = None
    best_count = -1

    for baud in COMMON_BAUDS:
        for parity in PARITIES:
            for stopbits in STOPBITS:
                for bytesize in BYTESIZES:
                    key = (baud, parity, stopbits, bytesize)
                    report.append(f"### {key}")
                    try:
                        lines, n_frames = probe_stream(
                            port=args.port,
                            baud=baud,
                            parity=parity,
                            stopbits=stopbits,
                            bytesize=bytesize,
                            seconds=args.seconds,
                            frame_chars=args.frame_chars,
                        )
                        report.append(f"- Frames parsed: **{n_frames}** (sample lines: {len(lines)})")
                        for line in lines[:8]:
                            report.append(f"  - `{line}`")
                        if len(lines) > 8:
                            report.append(f"  - `... ({len(lines) - 8} more lines)`")
                        if n_frames > best_count:
                            best_count = n_frames
                            best = key
                    except Exception as exc:
                        report.append(f"- Error: `{exc}`")
                    report.append("")

    report.append("## Suggested baseline")
    report.append("")
    if best:
        report.append(f"- Best frame count: `{best}` with `{best_count}` frames.")
        report.append("- Use this tuple in `app/config.py` as starting point.")
    else:
        report.append("- No readable frames captured. Check cable, drivers, and instrument output mode.")
    report.append("")
    report.append("## Parser hint")
    report.append("")
    report.append("- Same framing logic as `DynoWorker` / `consume_stream_frames` in the app.")

    out_path.write_text("\n".join(report), encoding="utf-8")
    print(f"Report generated at: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
