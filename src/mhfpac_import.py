#!/usr/bin/env python3
"""
mhfpac_import.py
----------------
Import/patch strings back into an mhfpac-style BIN/PAC using a CSV produced by
`mhfpac_export.py`. Any row where the CSV "text" differs from the current file
string at "offset" will be applied by:
  1) Appending the new (null-terminated) string to EOF (Shift‑JIS by default)
  2) Repointing all 32-bit little-endian pointers that currently target that
     original offset to point to the new string

This avoids shifting any existing data.

CSV format (from exporter)
--------------------------
index,offset,text
0,0x00196780,Log
1,0x00196784,Chat Log
...

Usage
-----
python mhfpac_import.py input.bin edits.csv output.bin
# optional flags:
#   --encoding cp932        (default)
#   --no-backup             (skip input.bin.bak)
#   --validate-header       (check 0x1A636170/0x0000000A at 0x00/0x04)
#   --tables skills,skillActive,zskills,skillDesc  (limit which tables repoint)

Notes
-----
- Pointers are treated as ABSOLUTE 32-bit LE file offsets.
- Pointer tables are scanned at these absolute offsets (inclusive start, exclusive end):
    skills:       0x0A1C .. 0x0A20
    skillActive:  0x0A1C .. 0x0BC0
    zskills:      0x0FB0 .. 0x0FBC
    skillDesc:    0x00B8 .. 0x00C0
- The pointer at 0x010C (start of string blob) is NOT changed.
"""

from __future__ import annotations
import sys
import csv
from pathlib import Path
from typing import Dict, List, Tuple

EXPECTED_HDR1 = 0x1A636170
EXPECTED_HDR2 = 0x0000000A

# Pointer table ranges (absolute file offsets)
TABLES = {
    "skills":      (0x0A1C, 0x0A20),
    "skillActive": (0x0A1C, 0x0BC0),
    "zskills":     (0x0FB0, 0x0FBC),
    "skillDesc":   (0x00B8, 0x00C0),
}


def ru32(buf: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(buf):
        raise ValueError(f"u32 read OOB at 0x{off:X}")
    return int.from_bytes(buf[off:off+4], "little")


def wu32(buf: bytearray, off: int, val: int) -> None:
    if off < 0 or off + 4 > len(buf):
        raise ValueError(f"u32 write OOB at 0x{off:X}")
    buf[off:off+4] = val.to_bytes(4, "little")


def read_cstr(buf: bytes, off: int, enc: str) -> str:
    n = len(buf)
    i = off
    while i < n and buf[i] != 0:
        i += 1
    raw = buf[off:i]
    for codec in (enc, "latin-1", "utf-8"):
        try:
            return raw.decode(codec) if codec != "utf-8" else raw.decode(codec, errors="replace")
        except Exception:
            continue
    return ""


def write_cstr_append(buf: bytearray, text: str, enc: str) -> int:
    off = len(buf)
    data = text.encode(enc, errors="replace") + b"\x00"
    buf.extend(data)
    return off


def validate_header(buf: bytes) -> None:
    h1 = ru32(buf, 0x00)
    h2 = ru32(buf, 0x04)
    if h1 != EXPECTED_HDR1 or h2 != EXPECTED_HDR2:
        raise SystemExit(f"[!] Header mismatch: h1=0x{h1:08X} h2=0x{h2:08X} "
                         f"(expected 0x{EXPECTED_HDR1:08X} 0x{EXPECTED_HDR2:08X})")


def build_pointer_index(buf: bytes, which: List[str]) -> Dict[int, List[int]]:
    """
    Map: target_offset -> [pointer_slot_offsets...]
    where pointer_slot_offsets are file offsets of 4-byte pointer values.
    """
    idx: Dict[int, List[int]] = {}
    for name in which:
        start, end = TABLES[name]
        for slot in range(start, end, 4):
            if slot + 4 > len(buf):
                break
            val = ru32(buf, slot)
            idx.setdefault(val, []).append(slot)
    return idx


def parse_tables_arg(arg: str | None) -> List[str]:
    if not arg:
        return list(TABLES.keys())
    chosen = []
    for name in arg.split(","):
        name = name.strip()
        if not name:
            continue
        if name not in TABLES:
            raise SystemExit(f"Unknown table '{name}'. Valid: {', '.join(TABLES)}")
        chosen.append(name)
    return chosen


def read_export_csv(csv_path: Path) -> List[Tuple[int, str]]:
    """
    Accepts exporter CSV (index,offset,text). Returns list of (offset, new_text).
    Offset accepts '0x..' hex or decimal.
    """
    out: List[Tuple[int, str]] = []
    with csv_path.open("r", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r, None)
        # If header detected (index, offset, text)
        if header and len(header) >= 2 and header[0].lower().strip() == "index":
            for row in r:
                if not row or len(row) < 3:
                    continue
                off_s = row[1].strip()
                txt = row[2]
                off = int(off_s, 16) if off_s.lower().startswith("0x") else int(off_s)
                out.append((off, txt))
        else:
            # No header → assume (index,offset,text) anyway
            if header and len(header) >= 2:
                off_s = header[1].strip()
                txt = header[2] if len(header) > 2 else ""
                try:
                    off = int(off_s, 16) if off_s.lower().startswith("0x") else int(off_s)
                    out.append((off, txt))
                except Exception:
                    pass
            for row in r:
                if not row or len(row) < 2:
                    continue
                off_s = row[1].strip()
                txt = row[2] if len(row) > 2 else ""
                try:
                    off = int(off_s, 16) if off_s.lower().startswith("0x") else int(off_s)
                except Exception:
                    continue
                out.append((off, txt))
    return out


def patch(bin_in: Path, csv_in: Path, bin_out: Path, encoding: str, tables: List[str], backup: bool, validate: bool) -> int:
    data = bytearray(bin_in.read_bytes())
    if validate:
        validate_header(data)

    # Build pointer index BEFORE any modifications (original target offsets)
    ptr_index = build_pointer_index(bytes(data), tables)

    edits = read_export_csv(csv_in)

    changed_strings = 0
    updated_slots = 0

    for off, new_text in edits:
        if off < 0 or off >= len(data):
            continue
        current_text = read_cstr(bytes(data), off, encoding)
        if new_text == current_text:
            continue  # unchanged
        # which pointer slots currently point at this original offset?
        slots = ptr_index.get(off, [])
        if not slots:
            # No pointers currently referencing this string; skip
            continue
        # Append new string and repoint all slots
        new_off = write_cstr_append(data, new_text, encoding)
        for slot in slots:
            wu32(data, slot, new_off)
            updated_slots += 1
        changed_strings += 1

    if backup:
        bak = bin_in.with_suffix(bin_in.suffix + ".bak")
        if not bak.exists():
            bak.write_bytes(bin_in.read_bytes())

    bin_out.write_bytes(bytes(data))
    print(f"[OK] Patched: {bin_out}")
    print(f"    Strings changed: {changed_strings}")
    print(f"    Pointer slots updated: {updated_slots}")
    return 0


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Import/patch mhfpac strings from an exporter CSV (append + repoint).")
    ap.add_argument("input", help="Original BIN/PAC")
    ap.add_argument("csv", help="Edited CSV (from mhfpac_export.py)")
    ap.add_argument("output", help="Output patched BIN/PAC")
    ap.add_argument("--encoding", default="cp932", help="String encoding (default cp932 / Shift‑JIS)")
    ap.add_argument("--tables", default=None, help="Comma-separated list of tables to repoint (default: all)")
    ap.add_argument("--no-backup", action="store_true", help="Do not write input.bak")
    ap.add_argument("--validate-header", action="store_true", help="Check 0x1A636170/0x0000000A header")
    args = ap.parse_args(argv)

    try:
        return patch(
            bin_in=Path(args.input),
            csv_in=Path(args.csv),
            bin_out=Path(args.output),
            encoding=args.encoding,
            tables=parse_tables_arg(args.tables),
            backup=not args.no_backup,
            validate=args.validate_header,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
