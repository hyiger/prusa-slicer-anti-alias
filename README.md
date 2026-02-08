# PrusaSlicer Z Anti-Aliasing Post-Processor

A PrusaSlicer post-processing script that reduces visible stair-stepping on sloped and curved surfaces by **modulating Z height within a single layer**, using vertical raycasts against the original STL geometry.

Designed for **PrusaSlicer + PrusaConnect** workflows and tested on macOS.

---

## What this does (and what it doesn’t)

**What it does**
- Adjusts Z during selected extrusion moves *within a layer*
- Uses the original STL to compute a local surface height
- Clamps Z adjustments to a fraction of the current layer height (safety)
- Can split long extrusion moves into smaller segments so Z can vary smoothly
- Works as a PrusaSlicer post-processing script (supports file and stdin modes)

**What it does not**
- It does **not** change the slice geometry PrusaSlicer generated (it only rewrites G-code)
- It does **not** work with Binary G-code (`.bgcode`)
- It does **not** replace variable layer height when that’s the correct tool

---

## Requirements

- Python 3.9+
- Python packages:
  - `numpy`
  - `trimesh`

Install once (inside your venv, recommended):

```bash
pip install numpy trimesh
```

---

## Binary G-code (important)

This script **does not support `.bgcode`**.

In PrusaSlicer:

```
Printer Settings → General → Output file
☐ Use binary G-code
```

If binary G-code is detected, the script will print an error and exit.

---

## How PrusaSlicer runs post-processing scripts (important)

PrusaSlicer may invoke post-processing scripts in a hybrid mode:

- The generated G-code may be **piped to stdin**
- One or more temporary filenames (for example `.gcode.pp`) may also be passed as command-line arguments

This script supports both invocation styles:

- If a G-code path is provided, it reads from disk and overwrites that file by default
- If no G-code path is provided, it reads from **stdin** and writes to **stdout**
- If multiple paths are provided, the first path is used and extra paths are ignored safely

---

## About `${GCODE}` (why it’s still used)

`${GCODE}` is **not required**, but it is still **recommended**.

- When available, it gives the script a real on-disk G-code path
- This enables automatic STL resolution and in-place file rewriting
- If PrusaSlicer instead pipes G-code via stdin, the script falls back automatically

Removing `${GCODE}` forces stdin-only mode, which:
- Requires `--stl` every time
- Disables automatic STL discovery

**Bottom line:** `${GCODE}` is optional, but keeping it makes the setup more robust.

---

## STL requirement

The script needs access to the **original STL** used for slicing.

### If a G-code file path is available
The script will attempt to auto-resolve the STL using metadata in the G-code and the filesystem.

### If G-code is provided via stdin
You **must** pass the STL explicitly:

```bash
--stl /path/to/model.stl
```

If the STL cannot be found, the script prints a clear error and exits without modifying the G-code.

---

## Nozzle diameter detection

The script auto-detects nozzle diameter from the PrusaSlicer G-code header:

```gcode
; nozzle_diameter = 0.4
```

Manual override (optional):

```bash
--nozzle 0.6
```

---

## PrusaSlicer setup (macOS)

### Recommended (most users)

Create a dedicated venv once and install deps:

```bash
/opt/homebrew/bin/python3 -m venv ~/prusaslicer-pp-venv
source ~/prusaslicer-pp-venv/bin/activate
pip install numpy trimesh
deactivate
```

Then set PrusaSlicer → **Printer Settings → Custom G-code → Post-processing scripts** to:

```bash
/Users/rlewis/prusaslicer-pp-venv/bin/python \
  /Users/rlewis/prusa-slicer-anti-alias-z/prusaslicer_anti_alias_z.py "${GCODE}"
```

---

## Preview note (PrusaSlicer limitation)

PrusaSlicer’s Preview (including “Color by height”) often **does not visualize mid-layer Z changes** correctly.  
Even if the script is working, Preview may still display a single “layer height color”.

To verify the script is active, inspect the rewritten G-code and confirm that **multiple distinct `Z...` values appear within the same `;Z:` layer**.

---

## Key options

| Option | Description |
|------|------------|
| `--stl PATH` | Explicit STL path (required for stdin mode) |
| `--nozzle MM` | Override nozzle diameter |
| `--max-dz-frac` | Clamp Z offset to ±(layer_height × frac) (default `0.5`) |
| `--include-type TYPE` | Limit to specific PrusaSlicer `;TYPE:` regions (repeatable) |
| `--include-infill` | Also process infill |
| `--enable-first-layer` | Allow first-layer modification (not recommended) |
| `--out PATH` | Write output to a separate file |

---

## Notes on where this helps most

This approach tends to be most visible on **large planar slopes** (chamfers, drafted faces, ramps) where toolpaths contain longer segments that can be subdivided.  
On highly tessellated curved meshes, the slicer may already approximate the surface well, and the visible improvement can be subtle.

---

## Status

- ✅ Unit-tested
- ✅ PrusaSlicer-compatible
- ✅ stdin + argv tolerant
- ❌ Binary G-code unsupported (by design)
