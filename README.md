# PrusaSlicer Z Anti-Aliasing Post-Processor

A PrusaSlicer post-processing script that reduces visible stair-stepping on sloped and curved surfaces by **modulating Z height within a single layer**, based on ray-casting against the original STL geometry.

Designed for **PrusaSlicer + PrusaConnect** workflows and tested on macOS.

---

## What this does (and what it doesn’t)

**What it does**
- Adjusts Z during extrusion moves *within a layer*
- Uses the original STL to compute local surface height
- Preserves total extrusion (E) when splitting moves
- Works automatically as a PrusaSlicer post-processing script

**What it does not**
- It does **not** modify slicer geometry
- It does **not** work with Binary G-code (`.bgcode`)
- It does **not** replace proper layer height selection

---

## Requirements

- Python 3.9+
- Python packages:
  - `numpy`
  - `trimesh`
- PrusaSlicer **Binary G-code disabled**

Install dependencies once:

```bash
pip3 install numpy trimesh
```

---

## Binary G-code (important)

This script **does not support `.bgcode`**.

In PrusaSlicer:

```
Printer Settings → General → Output file
☐ Use binary G-code
```

If binary G-code is detected, the script will **emit a clear error and exit**.

---

## How PrusaSlicer runs post-processing scripts (important)

PrusaSlicer may invoke post-processing scripts in a **hybrid mode**:

- The generated G-code may be **piped to stdin**
- One or more temporary filenames (for example `.gcode.pp`) may also be passed as command-line arguments

This script supports **both** invocation styles:

- If a G-code path is provided, it reads from disk
- If no G-code path is provided, it reads from **stdin**
- Extra filenames passed by PrusaSlicer are ignored safely

---

## About `${GCODE}` (why it’s still used)

`${GCODE}` is **not required**, but it is still **recommended**.

- When available, it gives the script a real on-disk G-code path
- This enables automatic STL resolution and in-place file rewriting
- If PrusaSlicer instead pipes G-code via stdin, the script falls back automatically

Removing `${GCODE}` forces the script into stdin-only mode, which:
- Requires `--stl` every time
- Disables automatic STL discovery
- Provides no real benefit

**Bottom line:** `${GCODE}` is optional, but keeping it makes the setup more robust.

---

## STL requirement

The script needs access to the **original STL** used for slicing.

### If a G-code file path is available
The script will attempt to **auto-resolve the STL** from the G-code metadata and filesystem.

### If G-code is provided via stdin
You **must** pass the STL explicitly:

```bash
--stl /path/to/model.stl
```

If the STL cannot be found, the script:
- Prints a clear error message
- Exits gracefully without modifying the G-code

---

## Nozzle diameter detection

The script **automatically detects nozzle diameter** from the PrusaSlicer G-code header:

```gcode
; nozzle_diameter = 0.4
```

### Manual override (optional)

For testing or unusual cases:

```bash
--nozzle 0.6
```

If neither auto-detection nor `--nozzle` succeeds, the script exits with an error.

---

## PrusaSlicer setup (macOS)

### Recommended command (most users)

```bash
/opt/homebrew/bin/python3 \
  /Users/rlewis/prusa-slicer-anti-alias-z/prusaslicer_anti_alias_z.py "${GCODE}"
```

This works for:
- PrusaSlicer
- PrusaConnect
- File-based and stdin-based invocation

### Stdin-only mode (advanced / debugging)

```bash
/opt/homebrew/bin/python3 \
  /Users/rlewis/prusa-slicer-anti-alias-z/prusaslicer_anti_alias_z.py --stl "/full/path/to/model.stl"
```

Use this only if you intentionally want stdin-only operation.

---

## Key options

| Option | Description |
|------|------------|
| `--stl PATH` | Explicit STL path (required for stdin mode) |
| `--nozzle MM` | Override nozzle diameter |
| `--max-dz-frac` | Clamp Z offset to ±(layer_height × frac) (default `0.5`) |
| `--include-type TYPE` | Limit to specific PrusaSlicer `;TYPE:` regions |
| `--include-infill` | Also process infill |
| `--enable-first-layer` | Allow first-layer modification (not recommended) |
| `--out PATH` | Write output to a separate file |

---

## Safety defaults

- First layer **disabled by default**
- Z offsets are **clamped**
- Unsupported modes exit safely
- Extrusion totals are preserved

---

## Status

- ✅ Unit-tested
- ✅ PrusaSlicer-compatible
- ✅ PrusaConnect-safe
- ✅ stdin + argv tolerant
- ❌ Binary G-code unsupported (by design)
