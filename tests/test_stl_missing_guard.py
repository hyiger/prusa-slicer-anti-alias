
import subprocess
import sys
from pathlib import Path

def test_missing_stl_exits_gracefully(tmp_path):
    g = tmp_path / "test.gcode"
    g.write_text("; dummy\nG90\n", encoding="utf-8")
    missing = tmp_path / "missing.stl"

    script = Path(__file__).resolve().parents[1] / "prusaslicer_anti_alias_z.py"
    p = subprocess.run([sys.executable, str(script), str(g), "--stl", str(missing)],
                       capture_output=True, text=True)
    assert p.returncode == 2
    combined = (p.stderr or "") + (p.stdout or "")
    assert "ERROR: STL file not found." in combined
    assert str(missing) in combined
