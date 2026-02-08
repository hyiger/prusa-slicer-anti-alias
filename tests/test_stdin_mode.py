import subprocess
import sys
from pathlib import Path

def test_stdin_mode_requires_stl(tmp_path):
    gcode = "; nozzle_diameter = 0.4\nG90\n"
    script = Path(__file__).resolve().parents[1] / "prusaslicer_anti_alias_z.py"
    p = subprocess.run([sys.executable, str(script)], input=gcode, text=True, capture_output=True)
    assert p.returncode == 2
    combined = (p.stderr or "") + (p.stdout or "")
    assert "STL path is required" in combined

def test_stdin_mode_with_stl_ok(tmp_path):
    stl = tmp_path / "plane.stl"
    stl.write_text("""solid p
facet normal 0 0 1
 outer loop
  vertex 0 0 1
  vertex 10 0 1
  vertex 0 10 1
 endloop
endfacet
endsolid
""", encoding="utf-8")

    gcode = """; nozzle_diameter = 0.4
;LAYER_CHANGE
;Z:0.45
;HEIGHT:0.25
G90
M83
;TYPE:External perimeter
G1 X0 Y0 Z0.45 F1200
G1 X10 Y0 E1.0 F1200
"""
    script = Path(__file__).resolve().parents[1] / "prusaslicer_anti_alias_z.py"
    p = subprocess.run([sys.executable, str(script), "--stl", str(stl)], input=gcode, text=True, capture_output=True)
    assert p.returncode == 0, (p.stderr or "") + (p.stdout or "")
    assert "G1" in (p.stdout or "")
