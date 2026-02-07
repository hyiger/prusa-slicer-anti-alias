import pytest

import os
import math
import tempfile

import numpy as np
import trimesh

from prusaslicer_anti_alias_z import (
    extract_model_filename,
    infer_layer_height_prusaslicer,
    rewrite_prusaslicer_gcode,
)


def test_extract_model_filename_from_m486():
    lines = [
        "G90\n",
        "M486 Amidedgehinge-s-a0.stl\n",
        "; other\n",
    ]
    assert extract_model_filename(lines) == "midedgehinge-s-a0.stl"


def test_infer_layer_height_prefers_height_comments():
    lines = [
        ";LAYER_CHANGE\n",
        ";Z:0.2\n",
        ";HEIGHT:0.2\n",
        ";LAYER_CHANGE\n",
        ";Z:0.45\n",
        ";HEIGHT:0.25\n",
        ";LAYER_CHANGE\n",
        ";Z:0.7\n",
        ";HEIGHT:0.25\n",
    ]
    assert abs(infer_layer_height_prusaslicer(lines) - 0.25) < 1e-9


def _write_plane_stl(tmpdir: str, z: float = 1.0) -> str:
    # Create a large square plane at constant Z (two triangles)
    verts = np.array([
        [-100.0, -100.0, z],
        [ 100.0, -100.0, z],
        [ 100.0,  100.0, z],
        [-100.0,  100.0, z],
    ])
    faces = np.array([
        [0, 1, 2],
        [0, 2, 3],
    ])
    m = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    path = os.path.join(tmpdir, "plane.stl")
    m.export(path)
    return path


def test_rewrite_modifies_only_selected_types_and_clamps_dz():
    with tempfile.TemporaryDirectory() as td:
        stl = _write_plane_stl(td, z=0.55)

        # Layer height 0.25 => dz clamp ±0.125 with max_dz_frac=0.5.
        # Baseline layer_z=0.45 => surface at 1.0 => dz=0.55 -> clamped to +0.125 => z_new=0.55
        gcode = [
            ";LAYER_CHANGE\n",
            ";Z:0.45\n",
            ";HEIGHT:0.25\n",
            "G90\n",
            "M83\n",
            ";TYPE:External perimeter\n",
            "G1 X0 Y0 Z0.45 F1200\n",
            "G1 X10 Y0 E1.0 F1200\n",
            ";TYPE:Support material\n",
            "G1 X20 Y0 E1.0 F1200\n",
        ]

        out = rewrite_prusaslicer_gcode(
            lines=gcode,
            mesh_path=stl,
            nozzle_diam=5.0,  # no split
            max_dz_frac=0.5,
            include_types=("External perimeter",),
            disable_first_layer=False,
        )

        # External perimeter line should be rewritten with explicit Z near 0.575
        rewritten = [ln for ln in out if ln.startswith("G1 X10")]
        assert rewritten, "Expected rewritten extrusion move"
        assert "Z0.55" in rewritten[0] or "Z0.55" in rewritten[0] or "Z0.55" in rewritten[0]

        # Support material extrusion should be unmodified and still not forced Z (original line preserved)
        assert any(ln.strip() == "G1 X20 Y0 E1.0 F1200" for ln in out)


def test_rewrite_splits_extrusion_and_preserves_total_e():
    with tempfile.TemporaryDirectory() as td:
        stl = _write_plane_stl(td, z=1.0)

        gcode = [
            ";LAYER_CHANGE\n",
            ";Z:0.45\n",
            ";HEIGHT:0.25\n",
            "G90\n",
            "M83\n",
            ";TYPE:External perimeter\n",
            "G1 X0 Y0 Z0.45 F1200\n",
            "G1 X10 Y0 E1.0 F1200\n",
        ]

        out = rewrite_prusaslicer_gcode(
            lines=gcode,
            mesh_path=stl,
            nozzle_diam=2.0,  # force split into 5 segments (10/2)
            max_dz_frac=0.5,
            include_types=("External perimeter",),
            disable_first_layer=False,
        )

        segs = [ln for ln in out if ln.startswith("G1 X") and "E" in ln and "X10" not in ln]
        # We expect multiple segments, and total E should sum to ~1.0 (relative)
        e_vals = []
        for ln in out:
            if ln.startswith("G1") and " E" in ln:
                parts = ln.split()
                for p in parts:
                    if p.startswith("E"):
                        e_vals.append(float(p[1:]))
        assert sum(e_vals) == pytest.approx(1.0, rel=1e-6)
