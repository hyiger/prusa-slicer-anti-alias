# PrusaSlicer Z Anti-Aliasing Post-Processor

This project provides a **PrusaSlicer post-processing script** that performs sub-layer Z
anti-aliasing by raycasting extrusion paths against the original STL geometry and
modulating Z within a single layer. The goal is to reduce visible stair-stepping on
sloped and curved surfaces without modifying the slicer itself.

The script is designed to run automatically during slicing and works cleanly with
**PrusaConnect**.

---

## Key features

- Sub-layer Z modulation (±½ layer height by default)
- PrusaSlicer-specific parsing (`;Z:`, `;HEIGHT:`, `;TYPE:`)
- Selective application by extrusion type (perimeters, top solid infill, etc.)
- Text G-code only (binary `.bgcode` is rejected safely)
- Single-file distribution, suitable for PrusaSlicer post-processing
- CI-tested on minimal Python environments (no SciPy required)

---

## Requirements

- Python 3.9+
- `trimesh`
- Text G-code output (disable binary G-code in PrusaSlicer)

---

## PrusaSlicer setup

### 1. Disable binary G-code

```
Printer Settings → General → Use binary G-code (disable)
```

This script operates on text G-code and will exit with a clear error if `.bgcode` is used.

---

### 2. Configure the post-processing script

Add the following line in:

```
Print Settings → Output options → Post-processing scripts
```

```bash
python3 /Users/rlewis/prusa-slicer-anti-alias-z/prusaslicer_anti_alias_z.py "${GCODE}" \
  --nozzle {nozzle_diameter}
```

Notes:
- Use an **absolute path** to the script
- Always use `python3`
- Keep `"${GCODE}"` quoted

PrusaSlicer expands placeholders before execution.

---

## Passing nozzle diameter from PrusaSlicer

The script can automatically receive the **current nozzle diameter** from PrusaSlicer.

### Placeholder used

```
{nozzle_diameter}
```

This expands to the numeric nozzle size (in millimeters) defined in:

```
Printer Settings → Extruder 1 → Nozzle diameter
```

Example expansion at slice time:

```bash
--nozzle 0.6
```

### Notes and limitations

- Comes from the **printer profile**, not the filament profile
- Updates automatically when switching nozzle presets
- Works with PrusaConnect and temporary G-code paths
- Single-extruder only (multi-tool nozzle changes are not exposed)

If `--nozzle` is not provided, the script falls back to its default value.

---

## STL requirement

This script requires access to the **original STL geometry** in order to raycast the
surface.

If the STL cannot be found, the script exits gracefully with a clear error message.

### Recommended workflow (PrusaConnect)

Because PrusaConnect uses temporary G-code paths, the most reliable setup is to pass the
STL explicitly:

```bash
python3 /Users/rlewis/prusa-slicer-anti-alias-z/prusaslicer_anti_alias_z.py "${GCODE}" \
  --stl "/Users/rlewis/path/to/exported_from_plate.stl" \
  --nozzle {nozzle_diameter}
```

Best practice:
- Right-click the object in PrusaSlicer → **Export STL**
- This bakes in all rotations, scaling, and transforms
- Reuse that STL for post-processing

---

## Failure modes (by design)

- `.bgcode` input → clear error, exit
- Missing STL → clear error, exit
- No Python / missing dependency → script fails before upload

In all cases, PrusaSlicer aborts the upload and the printer never receives partial or
invalid G-code.

---

## License

MIT
