# PrusaSlicer Z Anti-Aliasing Post-Processor

Implements a practical version of sub-layer toolpath Z "anti-aliasing" by vertically raycasting into the original STL
and adding small Z offsets to extrusion moves. Inspired by *Anti-aliasing for fused filament deposition* (Song et al., 2017). fileciteturn0file0

## Usage (PrusaSlicer)

In **Print Settings → Output options → Post-processing scripts**, add:

```bash
python3 /path/to/prusaslicer_anti_alias_z.py "$GCODE"
```

Place the STL next to the G-code, or pass it explicitly:

```bash
python3 /path/to/prusaslicer_anti_alias_z.py "$GCODE" --stl /path/to/model.stl
```

### Options

- `--nozzle 0.4` resampling step (mm), default 0.4
- `--max-dz-frac 0.5` clamps dz to ±(layer HEIGHT * frac), default 0.5 (±h/2)
- `--include-type "External perimeter"` (repeatable) to control which PrusaSlicer `;TYPE:` regions are modified
- `--include-infill` also modifies `Solid infill` and `Infill`
- `--enable-first-layer` enables modification on first layer (off by default)

## Notes

- This script assumes the STL is in the same coordinate frame as the G-code (no rotation/translation in the slicer).
- Works best on `External perimeter`, `Perimeter`, and `Top solid infill` (defaults).
- Does **not** reorder paths or do overlap compensation (kept intentionally simple).

## Dev

```bash
pip install -r requirements.txt
pytest -q
```

## Binary G-code (.bgcode)

This script **does not support Prusa binary G-code (.bgcode)**.

If binary G-code is enabled, the script will exit with a clear error message.
Disable **Printer Settings → General → Use binary G-code**, then re-slice
to generate standard text G-code before using this post-processing script.
