#!/usr/bin/env python3
"""
mhfpac_export.py
----------------
Export null-terminated strings from an mhfpac-style BIN/PAC.

- Reads a 32-bit LE pointer at 0x10C to find the start of the string blob
- Decodes text as Shift-JIS (cp932) with safe fallbacks
- Writes CSV: index, offset, text

Usage:
    python pac_parser.py input.bin output.csv
"""

from __future__ import annotations
import sys
from pathlib import Path
import csv


POINTER_OFFSET = 0x10C  # file offset containing the uint32 LE pointer to the string blob


def ru32(buf: bytes, off: int) -> int:
    """Read little-endian uint32 at off."""
    if off < 0 or off + 4 > len(buf):
        raise ValueError(f"u32 read out of bounds at 0x{off:X}")
    return int.from_bytes(buf[off:off + 4], "little")


def decode_bytes(bs: bytes, enc: str = "cp932") -> str:
    """Decode with Shift-JIS first, then safe fallbacks."""
    try:
        return bs.decode(enc)
    except Exception:
        try:
            return bs.decode("latin-1")
        except Exception:
            return bs.decode("utf-8", errors="replace")


def read_cstr(buf: bytes, off: int, enc: str = "cp932") -> tuple[str, int]:
    """
    Read a null-terminated string starting at off.
    Returns (text, next_offset_after_terminator).
    """
    n = len(buf)
    i = off
    while i < n and buf[i] != 0:
        i += 1
    text = decode_bytes(buf[off:i], enc)
    # advance past the 0x00 terminator
    i = min(i + 1, n)
    return text, i


def export_strings(bin_path: Path, csv_path: Path) -> int:
    data = bin_path.read_bytes()
    start = ru32(data, POINTER_OFFSET)

    rows: list[tuple[int, str, str]] = []
    idx = 0
    i = start
    n = len(data)

    while i < n:
        text, nxt = read_cstr(data, i)
        rows.append((idx, f"0x{i:08X}", text))
        idx += 1
        if nxt <= i:  # safety
            break
        i = nxt

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "offset", "text"])
        w.writerows(rows)

    print(f"Exported {len(rows)} strings to {csv_path}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python pac_parser.py input.bin output.csv", file=sys.stderr)
        return 1

    in_path = Path(argv[0])
    out_path = Path(argv[1])

    if not in_path.is_file():
        print(f"Input not found: {in_path}", file=sys.stderr)
        return 1

    try:
        return export_strings(in_path, out_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
