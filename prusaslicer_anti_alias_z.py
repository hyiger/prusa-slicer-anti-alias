#!/usr/bin/env python3
"""PrusaSlicer post-processing: sub-layer Z anti-aliasing (single-file distribution).

This combines the former package module (anti_alias_prusaslicer/core.py)
into this script for easier PrusaSlicer post-processing deployment.
"""


from __future__ import annotations

import argparse
import math
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

try:
    import trimesh
except Exception as e:  # pragma: no cover
    trimesh = None  # type: ignore


_FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_RE_PARAM = re.compile(r"([A-Za-z])(" + _FLOAT + r")")

# PrusaSlicer comments we care about
_RE_LAYER_Z = re.compile(r"^\s*;\s*Z\s*:\s*(" + _FLOAT + r")\s*$", re.I)
_RE_LAYER_H = re.compile(r"^\s*;\s*HEIGHT\s*:\s*(" + _FLOAT + r")\s*$", re.I)
_RE_TYPE = re.compile(r"^\s*;\s*TYPE\s*:\s*(.+?)\s*$", re.I)
_RE_MODEL_FROM_M486 = re.compile(r"^\s*M486\s+A(.+?\.stl)\s*$", re.I)


def strip_comment(line: str) -> str:
    return line.split(";", 1)[0].strip()


def parse_params(line: str) -> Dict[str, float]:
    params: Dict[str, float] = {}
    for m in _RE_PARAM.finditer(line):
        params[m.group(1).upper()] = float(m.group(2))
    return params


def fmt_float(x: float) -> str:
    s = f"{x:.5f}".rstrip("0").rstrip(".")
    return s if s else "0"


@dataclass
class ModalState:
    abs_xyz: bool = True     # G90/G91
    rel_e: bool = True       # PrusaSlicer commonly uses M83 (relative E)
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    e: float = 0.0           # tracked but mostly unused when rel_e
    f: Optional[float] = None


@dataclass
class Context:
    layer_z: Optional[float] = None
    layer_h: Optional[float] = None
    feature_type: Optional[str] = None


def extract_model_filename(lines: Sequence[str]) -> Optional[str]:
    """
    PrusaSlicer emits e.g.:
        M486 Amidedgehinge-s-a0.stl
    We'll take the first one we see.
    """
    for ln in lines:
        m = _RE_MODEL_FROM_M486.match(strip_comment(ln))
        if m:
            return m.group(1).strip()
    return None


def infer_layer_height_prusaslicer(lines: Sequence[str]) -> Optional[float]:
    """
    Prefer ;HEIGHT:... values (PrusaSlicer emits them at each layer change).
    """
    hs: List[float] = []
    for ln in lines:
        m = _RE_LAYER_H.match(ln)
        if m:
            try:
                h = float(m.group(1))
                if 0.01 < h < 2.0:
                    hs.append(h)
            except Exception:
                continue
    if not hs:
        return None
    # Use median of later values (skip first layer if it differs)
    if len(hs) >= 4:
        return float(np.median(hs[1:]))  # typical: first layer special
    return float(np.median(hs))



class VerticalProjector:
    """
    Vertical +Z ray 'intersection' without rtree/pyembree.

    We exploit a key simplification:
      - rays are always vertical (+Z)
      - we only need the *first* triangle above a given Z

    Approach:
      1) Pre-bucket triangles into a uniform XY grid using their XY AABB.
      2) For a query (x, y), check candidate triangles from the cell (and neighbors).
      3) For each candidate, test if (x, y) lies inside the triangle's XY projection (barycentric in 2D).
      4) If inside, compute z by barycentric interpolation of vertex z's.
      5) Return the smallest z >= z0 within max_dist.

    This avoids trimesh's optional `rtree` dependency while remaining fast enough for typical STLs.
    """

    def __init__(self, mesh: "trimesh.Trimesh", cell_size: float):
        self.mesh = mesh
        self.tri = np.asarray(mesh.triangles, dtype=np.float64)  # (n, 3, 3)
        if self.tri.ndim != 3 or self.tri.shape[1:] != (3, 3):
            raise RuntimeError("Unexpected triangles array shape")

        if cell_size <= 0:
            raise ValueError("cell_size must be > 0")
        self.cell = float(cell_size)

        # Mesh bounds in XY
        b = np.asarray(mesh.bounds, dtype=np.float64)  # (2, 3)
        self.minx = float(b[0, 0])
        self.miny = float(b[0, 1])

        # Build grid: dict[(ix,iy)] -> list[tri_index]
        # Use triangles' XY bounds.
        tri_xy = self.tri[:, :, :2]  # (n, 3, 2)
        mins = tri_xy.min(axis=1)
        maxs = tri_xy.max(axis=1)

        self.grid: Dict[Tuple[int, int], List[int]] = {}
        for i in range(self.tri.shape[0]):
            minx, miny = mins[i]
            maxx, maxy = maxs[i]
            ix0 = int(math.floor((minx - self.minx) / self.cell))
            iy0 = int(math.floor((miny - self.miny) / self.cell))
            ix1 = int(math.floor((maxx - self.minx) / self.cell))
            iy1 = int(math.floor((maxy - self.miny) / self.cell))
            for ix in range(ix0, ix1 + 1):
                for iy in range(iy0, iy1 + 1):
                    self.grid.setdefault((ix, iy), []).append(i)

    @staticmethod
    def _barycentric_2d(px: float, py: float, a, b, c) -> Optional[Tuple[float, float, float]]:
        # a,b,c are (x,y)
        ax, ay = a
        bx, by = b
        cx, cy = c
        v0x, v0y = (bx - ax), (by - ay)
        v1x, v1y = (cx - ax), (cy - ay)
        v2x, v2y = (px - ax), (py - ay)

        den = v0x * v1y - v1x * v0y
        if abs(den) < 1e-12:
            return None  # degenerate in XY (near-vertical)
        inv = 1.0 / den
        u = (v2x * v1y - v1x * v2y) * inv
        v = (v0x * v2y - v2x * v0y) * inv
        w = 1.0 - u - v
        # allow tiny epsilon for edge hits
        eps = -1e-9
        if u < eps or v < eps or w < eps:
            return None
        return (w, u, v)

    def z_hit_above(self, x: float, y: float, z0: float, max_dist: float) -> Optional[float]:
        ix = int(math.floor((x - self.minx) / self.cell))
        iy = int(math.floor((y - self.miny) / self.cell))

        # Check the cell and 8 neighbors for robustness
        cand: List[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand.extend(self.grid.get((ix + dx, iy + dy), []))

        if not cand:
            return None

        z_best: Optional[float] = None
        z_max = z0 + max_dist

        for ti in cand:
            t = self.tri[ti]  # (3,3)
            a2, b2, c2 = t[0, :2], t[1, :2], t[2, :2]
            bc = self._barycentric_2d(x, y, a2, b2, c2)
            if bc is None:
                continue
            w, u, v = bc
            # interpolate z
            z = float(w * t[0, 2] + u * t[1, 2] + v * t[2, 2])
            if z < z0 - 1e-9:
                continue
            if z > z_max + 1e-9:
                continue
            if z_best is None or z < z_best:
                z_best = z

        return z_best


@dataclass
class Segment:
    x0: float
    y0: float
    x1: float
    y1: float
    e: float
    f: Optional[float]


def _dist_xy(x0: float, y0: float, x1: float, y1: float) -> float:
    return math.hypot(x1 - x0, y1 - y0)


def split_extrusion_move(
    x0: float, y0: float, x1: float, y1: float,
    e: float,
    max_step: float,
    f: Optional[float],
) -> List[Tuple[float, float, float, Optional[float]]]:
    """
    Split one extrusion move into N submoves.
    Returns list of (x, y, e_sub, f_for_first_only_or_None)
    We keep E relative (M83) and split proportionally.
    """
    d = _dist_xy(x0, y0, x1, y1)
    if d <= max_step or d == 0:
        return [(x1, y1, e, f)]
    n = int(math.ceil(d / max_step))
    out = []
    for i in range(1, n + 1):
        t = i / n
        xi = x0 + (x1 - x0) * t
        yi = y0 + (y1 - y0) * t
        ei = e / n
        out.append((xi, yi, ei, f if i == 1 else None))
    return out


def should_modify_type(feature_type: Optional[str], include_types: Sequence[str]) -> bool:
    if feature_type is None:
        return False
    ft = feature_type.strip().lower()
    return any(ft == t.strip().lower() for t in include_types)


def rewrite_prusaslicer_gcode(
    lines: Sequence[str],
    mesh_path: str,
    nozzle_diam: float,
    max_dz_frac: float = 0.5,
    include_types: Sequence[str] = ("External perimeter", "Perimeter", "Top solid infill"),
    disable_first_layer: bool = True,
    max_ray_dist: Optional[float] = None,
) -> List[str]:
    """
    PrusaSlicer-specific rewrite:
      - expects absolute XYZ (G90) and relative E (M83), but is tolerant.
      - uses ;Z: and ;HEIGHT: for nominal layer values.
      - uses ;TYPE: to decide which regions to modify.
    """
    if trimesh is None:  # pragma: no cover
        raise RuntimeError("trimesh is required. pip install trimesh (and optionally pyembree)")

    mesh = trimesh.load_mesh(mesh_path, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        raise RuntimeError("Mesh did not load as a single Trimesh")
    # Mesh cleanup (scipy-free; safe for CI)
    # Avoid mesh.process(validate=True) because it pulls in scipy
    if hasattr(mesh, "remove_duplicate_faces"):
        mesh.remove_duplicate_faces()
    if hasattr(mesh, "remove_degenerate_faces"):
        mesh.remove_degenerate_faces()
    if hasattr(mesh, "remove_unreferenced_vertices"):
        mesh.remove_unreferenced_vertices()
    proj = VerticalProjector(mesh, cell_size=nozzle_diam)

    st = ModalState()
    ctx = Context()

    out: List[str] = []
    last_layer_z: Optional[float] = None

    for ln in lines:
        # Track PrusaSlicer metadata comments
        m = _RE_LAYER_Z.match(ln)
        if m:
            ctx.layer_z = float(m.group(1))
            last_layer_z = ctx.layer_z
            out.append(ln)
            continue
        m = _RE_LAYER_H.match(ln)
        if m:
            ctx.layer_h = float(m.group(1))
            out.append(ln)
            continue
        m = _RE_TYPE.match(ln)
        if m:
            ctx.feature_type = m.group(1).strip()
            out.append(ln)
            continue

        code = strip_comment(ln).upper()
        if not code:
            out.append(ln)
            continue

        # modal updates
        if code.startswith("G90"):
            st.abs_xyz = True
            out.append(ln)
            continue
        if code.startswith("G91"):
            st.abs_xyz = False
            out.append(ln)
            continue
        if code.startswith("M82"):
            st.rel_e = False
            out.append(ln)
            continue
        if code.startswith("M83"):
            st.rel_e = True
            out.append(ln)
            continue

        # We only rewrite G1 extrusion moves in allowed feature types.
        if code.startswith("G1"):
            params = parse_params(code)
            # feedrate updates
            if "F" in params:
                st.f = params["F"]

            # Update XYZ
            x1, y1, z1 = st.x, st.y, st.z
            if "X" in params:
                x1 = params["X"] if st.abs_xyz else st.x + params["X"]
            if "Y" in params:
                y1 = params["Y"] if st.abs_xyz else st.y + params["Y"]
            if "Z" in params:
                z1 = params["Z"] if st.abs_xyz else st.z + params["Z"]

            # Extrusion
            e = params.get("E", None)
            is_extruding = (e is not None) and ((e > 0) if st.rel_e else (e > st.e)) and (("X" in params) or ("Y" in params))

            # Decide nominal layer info
            layer_z = ctx.layer_z if ctx.layer_z is not None else last_layer_z
            layer_h = ctx.layer_h

            can_modify = (
                is_extruding
                and layer_z is not None
                and layer_h is not None
                and should_modify_type(ctx.feature_type, include_types)
                and (not disable_first_layer or layer_z > (layer_h + 1e-6))  # skip first layer
            )

            if can_modify:
                dz_max = layer_h * max_dz_frac
                ray_dist = max_ray_dist if max_ray_dist is not None else (layer_h * (max_dz_frac + 1.0))

                # For PrusaSlicer: XYZ absolute + E relative is typical; we will emit absolute XYZ with explicit Z.
                # Split move in XY, distribute E linearly.
                e_delta = float(e) if st.rel_e else float(e - st.e)
                submoves = split_extrusion_move(st.x, st.y, x1, y1, e_delta, max_step=nozzle_diam, f=st.f)

                # Emit submoves
                for (xs, ys, es, f_first) in submoves:
                    # baseline is nominal layer_z, not current z1 (which can contain travel Z hops)
                    z0 = float(layer_z)

                    z_hit = proj.z_hit_above(xs, ys, z0, max_dist=ray_dist)
                    dz = 0.0
                    if z_hit is not None:
                        dz = z_hit - z0
                        if dz > dz_max:
                            dz = dz_max
                        elif dz < -dz_max:
                            dz = -dz_max

                    z_new = z0 + dz

                    parts = ["G1", f"X{fmt_float(xs)}", f"Y{fmt_float(ys)}", f"Z{fmt_float(z_new)}"]
                    # relative E
                    parts.append(f"E{fmt_float(es)}")
                    if f_first is not None:
                        parts.append(f"F{fmt_float(f_first)}")
                    out.append(" ".join(parts) + "\n")

                # advance state to end of original move (position and E)
                st.x, st.y = x1, y1
                st.z = z1
                if st.rel_e:
                    st.e += e_delta
                else:
                    st.e = float(e)
                continue

            # Not modified: pass through, but update state
            out.append(ln)
            st.x, st.y, st.z = x1, y1, z1
            if e is not None:
                if st.rel_e:
                    st.e += float(e)
                else:
                    st.e = float(e)
            continue

        # other lines: pass through
        out.append(ln)

    return out


def resolve_stl_for_gcode(gcode_path: str, explicit_stl: Optional[str] = None) -> str:
    if explicit_stl:
        return explicit_stl
    lines = open(gcode_path, "r", encoding="utf-8", errors="replace").read().splitlines(True)
    name = extract_model_filename(lines)
    if name:
        # try same directory as gcode
        cand = os.path.join(os.path.dirname(os.path.abspath(gcode_path)), name)
        if os.path.isfile(cand):
            return cand
        # try cwd
        if os.path.isfile(name):
            return name
    raise FileNotFoundError("Could not resolve STL. Provide --stl or ensure M486 A<file.stl> is present and the STL is alongside the gcode.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="PrusaSlicer post-processing: sub-layer Z anti-aliasing via vertical STL raycasts."
    )
    ap.add_argument("gcode", help="Input G-code path (PrusaSlicer). This script edits in-place by default.")
    ap.add_argument("--stl", default=None, help="STL path. If omitted, derived from 'M486 A<name>.stl' and resolved near the gcode.")
    ap.add_argument("--out", default=None, help="Output G-code path. Default: overwrite input file.")
    ap.add_argument("--nozzle", type=float, default=0.4, help="Nozzle diameter (also resample step), mm.")
    ap.add_argument("--max-dz-frac", type=float, default=0.5, help="Clamp dz to ±(HEIGHT * frac). Default 0.5 => ±h/2.")
    ap.add_argument("--include-type", action="append", default=None,
                    help="PrusaSlicer ;TYPE: to modify (can repeat). Default: External perimeter, Perimeter, Top solid infill.")
    ap.add_argument("--include-infill", action="store_true", help="Also include Solid infill and Infill.")
    ap.add_argument("--enable-first-layer", action="store_true", help="Allow modifications on first layer (not recommended).")
    args = ap.parse_args(list(argv) if argv is not None else None)

    stl = resolve_stl_for_gcode(args.gcode, args.stl)
    out_path = args.out or args.gcode

    with open(args.gcode, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    include_types = args.include_type or ["External perimeter", "Perimeter", "Top solid infill"]
    if args.include_infill:
        include_types += ["Solid infill", "Infill"]

    rewritten = rewrite_prusaslicer_gcode(
        lines=lines,
        mesh_path=stl,
        nozzle_diam=args.nozzle,
        max_dz_frac=args.max_dz_frac,
        include_types=tuple(include_types),
        disable_first_layer=(not args.enable_first_layer),
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(rewritten)

    return 0

# ---- CLI (PrusaSlicer post-processing entrypoint) ----


def is_binary_gcode(path: str) -> bool:
    if path.lower().endswith(".bgcode"):
        return True
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(1024)
    except OSError:
        return False


#!/usr/bin/env python3

if __name__ == "__main__":
    raise SystemExit(main())
