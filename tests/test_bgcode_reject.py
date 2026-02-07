
from prusaslicer_anti_alias_z import is_binary_gcode

def test_rejects_bgcode(tmp_path):
    p = tmp_path / "test.bgcode"
    p.write_bytes(b"\x00\x01\x02")
    assert is_binary_gcode(str(p)) is True
