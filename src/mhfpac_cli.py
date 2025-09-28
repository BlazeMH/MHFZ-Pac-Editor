# mhfpac_cli.py
from __future__ import annotations
import sys
from pathlib import Path

from pac_parser import main as export_main      # expects [input.bin, output.csv]
from mhfpac_import import main as import_main   # expects [--flags..., input.bin, edits.csv, output.bin]

VERSION = "mhfpac tools 1.0"

HELP_TEXT = r"""
MHF-PAC tools: export strings to CSV and import/patch them back.

Commands:
  1) Export strings to CSV
     - Use when you want to dump all null-terminated strings from a BIN/PAC into a CSV.
     - Syntax:
         mhfpac.exe export <input.bin> <output.csv>
    -Example: mhfpac.exe export mhfpac.bin stringdump.csv            

  2) Import patched strings (CSV → BIN/PAC)
     - Use when you want to write edited strings back into a new BIN/PAC.
     - NOTE: You must provide TWO .bin paths:
         • <input.bin>  = the original file you exported from
         • <output.bin> = the new file to write (will be created)
     - Syntax:
         mhfpac.exe import <input.bin> <edits.csv> <output.bin> 
    -Example: mhfpac.exe import mhfpac.bin stringdump.csv editedpac.bin

Other:
  -V, --version   Show version
  -h, --help      Show this help
""".strip()


def looks_bin(s: str) -> bool:
    s = s.lower()
    return s.endswith(".bin") or s.endswith(".pac")


def looks_csv(s: str) -> bool:
    return s.lower().endswith(".csv")


def print_help() -> int:
    print(HELP_TEXT)
    return 0


def print_version() -> int:
    print(VERSION)
    return 0


def extract_opt(argv: list[str], name: str, takes_value: bool = True):
    """
    Remove an option from argv and return (value or True, argv_without_option).
    Supports --name value  or  --name=value
    """
    out = []
    val = None
    i = 0
    while i < len(argv):
        tok = argv[i]
        if takes_value:
            if tok == f"--{name}":
                if i + 1 >= len(argv):
                    raise SystemExit(f"Missing value for --{name}")
                val = argv[i + 1]
                i += 2
                continue
            if tok.startswith(f"--{name}="):
                val = tok.split("=", 1)[1]
                i += 1
                continue
        else:
            if tok == f"--{name}":
                val = True
                i += 1
                continue
        out.append(tok)
        i += 1
    return val, out


def normalize_argv(argv: list[str]) -> list[str]:
    """
    Make CLI forgiving:
      - If 'export' or 'import' appears anywhere, move it to front.
      - If no command, infer:
          export: <bin> <csv>
          import: <bin> <csv> <bin>
    """
    if not argv:
        return argv

    # pull out known global flags before detecting command
    return argv


def main(raw_argv: list[str]) -> int:
    if not raw_argv or any(a in ("-h", "--help", "/?") for a in raw_argv):
        return print_help()
    if any(a in ("-V", "--version") for a in raw_argv):
        return print_version()

    encoding, argv = extract_opt(raw_argv, "encoding", takes_value=True)

    # Detect explicit command anywhere
    cmd = None
    if "export" in argv:
        i = argv.index("export")
        cmd = "export"
        argv = argv[:i] + argv[i+1:]
    elif "import" in argv:
        i = argv.index("import")
        cmd = "import"
        argv = argv[:i] + argv[i+1:]

    # Infer command if not given
    if cmd is None:
        # export: <bin> <csv>
        # import: <bin> <csv> <bin>
        if len(argv) >= 2 and looks_bin(argv[0]) and looks_csv(argv[1]):
            cmd = "export"
            if len(argv) >= 3 and looks_bin(argv[2]):
                cmd = "import"
        else:
            print_help()
            return 2

    # Dispatch
    if cmd == "export":
        if len(argv) != 2 or not looks_bin(argv[0]) or not looks_csv(argv[1]):
            print("Error: export requires: <input.bin> <output.csv>\n", file=sys.stderr)
            return print_help() or 2
        return export_main([argv[0], argv[1]])

    if cmd == "import":
        # Requires: <input.bin> <edits.csv> <output.bin>
        if len(argv) != 3 or not (looks_bin(argv[0]) and looks_csv(argv[1]) and looks_bin(argv[2])):
            print("Error: import requires: <input.bin> <edits.csv> <output.bin>\n", file=sys.stderr)
            return print_help() or 2
        fwd = []
        if encoding:
            fwd += ["--encoding", encoding]
        fwd += [argv[0], argv[1], argv[2]]
        return import_main(fwd)

    # Fallback
    return print_help() or 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
