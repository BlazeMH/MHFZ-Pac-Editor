# MHFZ-Pac-Editor

Export and import string data from **Monster Hunter Frontier ZZ BIN/PAC** (mhfpac.bin) files.

This toolset provides a simple workflow:
- **Export** all null-terminated strings to a CSV.
- **Edit** the CSV with your translations/changes.
- **Import** the edited CSV back into a new BIN/PAC file, automatically appending new strings and repointing pointers safely.

---

## Features
- One self-contained executable: `mhfpac.exe`.
- Simple CLI with only two commands.
- Repointing avoids shifting binary structures: original data layout is preserved.
- Automatically creates a `.bak` backup when importing.

---

## Example Workflow

1. Export strings:
   ```cmd
   mhfpac.exe export mhfpac.bin strings.csv
   ```
2. Edit `strings.csv` in your editor of choice.
3. Import back:
   ```cmd
   mhfpac.exe import mhfpac.bin strings.csv mhfpac_patched.bin
   ```

Your `mhfpac_patched.bin` now contains the updated text.

---

## Development

If you want to build from source:

1. Clone this repo.
2. Install Python 3.10+ and dependencies.
3. Run directly:
   ```bash
   python pac_parser.py input.bin output.csv
   python mhfpac_import.py input.bin edits.csv output.bin
   ```
4. Build an `.exe` with PyInstaller:
   ```bash
   pyinstaller -F -n mhfpac mhfpac_cli.py
   ```

---

## Notes
- Strings are exported with absolute offsets. Import only changes rows where the CSV text differs from the original.
- New strings are appended to EOF and pointers are updated accordingly.
- The exporter reads from the pointer at `0x10C` to find the start of the string blob.

---

## Resources
Thanks to the resources below for providing details on the mhfpac.bin structure.
- Monster Hunter Frontier Patterns (ImHex patterns): https://github.com/var-username/Monster-Hunter-Frontier-Patterns
- 010 Editor Templates for MHF: https://github.com/Mezeporta/010Templates
---
