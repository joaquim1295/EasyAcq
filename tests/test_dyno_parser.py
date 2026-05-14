from __future__ import annotations

from app.services.dyno_parser import consume_stream_frames


def test_single_frame_9_chars() -> None:
    values, frames, carry = consume_stream_frames("", "-0123.456\n", preferred_frame_len=9)
    assert values == [-123.456]
    assert frames == ["-0123.456"]
    assert carry.strip() == ""


def test_frame_after_noise_prefix() -> None:
    values, frames, _carry = consume_stream_frames("", "noise-0123.456tail", preferred_frame_len=9)
    assert values == [-123.456]
    assert frames == ["-0123.456"]


def test_two_frames_concatenated() -> None:
    blob = "-0001.0000-0002.5000"
    values, frames, carry = consume_stream_frames("", blob, preferred_frame_len=9)
    assert len(values) == 2
    assert frames[0] == "-0001.0000"
    assert frames[1] == "-0002.5000"
    assert carry == ""


def test_carry_limits_remainder_size() -> None:
    long_noise = "x" * 200
    _, _, carry = consume_stream_frames("abc", long_noise, preferred_frame_len=9, max_remainder=50)
    assert len(carry) <= 50


def test_max_scan_preserves_unprocessed_tail() -> None:
    noise = "y" * 20000
    payload = "-001.0000" + noise
    values, frames, carry = consume_stream_frames("", payload, max_scan_chars=500)
    assert values == [-1.0]
    assert frames == ["-001.0000"]
    assert len(carry) <= 128


def test_dyno_concatenated_six_char_frames() -> None:
    blob = "-000.0-000.0-001.0-016.7-045.4"
    values, frames, carry = consume_stream_frames("", blob)
    assert frames == ["-000.0", "-000.0", "-001.0", "-016.7", "-045.4"]
    assert len(values) == 5
    assert carry == ""
