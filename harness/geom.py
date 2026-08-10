"""Geometry helpers: STEP I/O, validity, voxel IoU, chamfer, volume IoU."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

import numpy as np

# CadQuery / OCP imports are deferred so modules can be inspected without the kernel.


def _cq():
    import cadquery as cq

    return cq


def _ocp():
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Fuse
    from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCP.GeomAbs import (
        GeomAbs_Plane,
        GeomAbs_Cylinder,
        GeomAbs_Cone,
        GeomAbs_Sphere,
        GeomAbs_Torus,
        GeomAbs_BSplineSurface,
    )
    from OCP.gp import gp_Pnt, gp_Vec

    return {
        "BRepGProp": BRepGProp,
        "GProp_GProps": GProp_GProps,
        "BRepCheck_Analyzer": BRepCheck_Analyzer,
        "BRepAlgoAPI_Common": BRepAlgoAPI_Common,
        "BRepAlgoAPI_Fuse": BRepAlgoAPI_Fuse,
        "TopAbs_SOLID": TopAbs_SOLID,
        "TopAbs_FACE": TopAbs_FACE,
        "TopAbs_EDGE": TopAbs_EDGE,
        "TopExp_Explorer": TopExp_Explorer,
        "BRep_Tool": BRep_Tool,
        "BRepAdaptor_Surface": BRepAdaptor_Surface,
        "BRepAdaptor_Curve": BRepAdaptor_Curve,
        "GeomAbs_Plane": GeomAbs_Plane,
        "GeomAbs_Cylinder": GeomAbs_Cylinder,
        "GeomAbs_Cone": GeomAbs_Cone,
        "GeomAbs_Sphere": GeomAbs_Sphere,
        "GeomAbs_Torus": GeomAbs_Torus,
        "GeomAbs_BSplineSurface": GeomAbs_BSplineSurface,
        "gp_Pnt": gp_Pnt,
        "gp_Vec": gp_Vec,
    }


@dataclass
class SolidInfo:
    volume: float
    bbox: Tuple[float, float, float, float, float, float]  # xmin,ymin,zmin,xmax,ymax,zmax
    n_faces: int
    n_solids: int
    is_valid: bool
    is_manifoldish: bool


def export_step(shape: Any, path: Path | str) -> None:
    cq = _cq()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(shape, "val"):
        shape = shape.val()
    cq.exporters.export(shape, str(path))


def load_step(path: Path | str) -> Any:
    cq = _cq()
    result = cq.importers.importStep(str(path))
    return result


def solid_from_workplane(wp: Any) -> Any:
    """Return the underlying solid/compound shape."""
    if hasattr(wp, "val"):
        return wp.val()
    return wp


def count_solids(shape: Any) -> int:
    o = _ocp()
    solid = solid_from_workplane(shape)
    # CadQuery Shape
    if hasattr(solid, "Solids"):
        return len(solid.Solids())
    exp = o["TopExp_Explorer"](solid.wrapped if hasattr(solid, "wrapped") else solid, o["TopAbs_SOLID"])
    n = 0
    while exp.More():
        n += 1
        exp.Next()
    return n


def count_faces(shape: Any) -> int:
    solid = solid_from_workplane(shape)
    if hasattr(solid, "Faces"):
        return len(solid.Faces())
    o = _ocp()
    wrapped = solid.wrapped if hasattr(solid, "wrapped") else solid
    exp = o["TopExp_Explorer"](wrapped, o["TopAbs_FACE"])
    n = 0
    while exp.More():
        n += 1
        exp.Next()
    return n


def volume_of(shape: Any) -> float:
    solid = solid_from_workplane(shape)
    if hasattr(solid, "Volume"):
        return float(solid.Volume())
    o = _ocp()
    props = o["GProp_GProps"]()
    wrapped = solid.wrapped if hasattr(solid, "wrapped") else solid
    o["BRepGProp"].VolumeProperties(wrapped, props)
    return float(props.Mass())


def bbox_of(shape: Any) -> Tuple[float, float, float, float, float, float]:
    solid = solid_from_workplane(shape)
    if hasattr(solid, "BoundingBox"):
        bb = solid.BoundingBox()
        return (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)
    # fallback via cq
    cq = _cq()
    wp = cq.Workplane().add(solid)
    bb = wp.val().BoundingBox()
    return (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)


def is_valid_solid(shape: Any) -> bool:
    """Single-body, positive volume, BRepCheck ok."""
    try:
        solid = solid_from_workplane(shape)
        n = count_solids(solid)
        if n != 1:
            return False
        vol = volume_of(solid)
        if not math.isfinite(vol) or vol <= 1e-9:
            return False
        o = _ocp()
        wrapped = solid.wrapped if hasattr(solid, "wrapped") else solid
        analyzer = o["BRepCheck_Analyzer"](wrapped)
        if not analyzer.IsValid():
            return False
        return True
    except Exception:
        return False


def analyze_solid(shape: Any) -> SolidInfo:
    try:
        solid = solid_from_workplane(shape)
        n_solids = count_solids(solid)
        vol = volume_of(solid)
        bb = bbox_of(solid)
        n_faces = count_faces(solid)
        valid = is_valid_solid(solid)
        return SolidInfo(
            volume=vol,
            bbox=bb,
            n_faces=n_faces,
            n_solids=n_solids,
            is_valid=valid,
            is_manifoldish=valid and n_solids == 1 and vol > 1e-9,
        )
    except Exception:
        return SolidInfo(
            volume=0.0,
            bbox=(0, 0, 0, 0, 0, 0),
            n_faces=0,
            n_solids=0,
            is_valid=False,
            is_manifoldish=False,
        )


def sample_surface_points(shape: Any, n: int = 30000, seed: int = 0) -> np.ndarray:
    """Uniform-ish surface samples via face tessellation + area weighting."""
    rng = np.random.default_rng(seed)
    solid = solid_from_workplane(shape)
    cq = _cq()

    # Tessellate
    try:
        # Use cadquery tessellate
        s = solid if hasattr(solid, "tessellate") else cq.Shape.cast(solid)
        verts, tris = s.tessellate(0.1, 0.1)
        if not verts or not tris:
            # fallback: bbox corners
            bb = bbox_of(solid)
            return np.array(
                [
                    [bb[0], bb[1], bb[2]],
                    [bb[3], bb[4], bb[5]],
                ],
                dtype=np.float64,
            )
        v = np.array([[p.x, p.y, p.z] for p in verts], dtype=np.float64)
        t = np.array(tris, dtype=np.int64)
        # triangle areas
        a = v[t[:, 0]]
        b = v[t[:, 1]]
        c = v[t[:, 2]]
        areas = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
        total = areas.sum()
        if total <= 0:
            return v[: min(n, len(v))]
        probs = areas / total
        tri_idx = rng.choice(len(t), size=n, p=probs)
        # barycentric
        r1 = np.sqrt(rng.random(n))
        r2 = rng.random(n)
        w0 = 1 - r1
        w1 = r1 * (1 - r2)
        w2 = r1 * r2
        pts = (
            w0[:, None] * v[t[tri_idx, 0]]
            + w1[:, None] * v[t[tri_idx, 1]]
            + w2[:, None] * v[t[tri_idx, 2]]
        )
        return pts
    except Exception:
        bb = bbox_of(solid)
        return rng.uniform(
            low=[bb[0], bb[1], bb[2]],
            high=[bb[3], bb[4], bb[5]],
            size=(n, 3),
        )


def normalize_to_unit_box(points: np.ndarray, bbox: Tuple[float, ...]) -> np.ndarray:
    xmin, ymin, zmin, xmax, ymax, zmax = bbox
    diag = max(xmax - xmin, ymax - ymin, zmax - zmin, 1e-9)
    center = np.array(
        [(xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2], dtype=np.float64
    )
    return (points - center) / diag


def chamfer_distance(
    pts_a: np.ndarray, pts_b: np.ndarray, max_points: int = 8000
) -> float:
    """Symmetric mean nearest-neighbor distance. Subsamples for speed."""
    rng = np.random.default_rng(0)
    if len(pts_a) > max_points:
        pts_a = pts_a[rng.choice(len(pts_a), max_points, replace=False)]
    if len(pts_b) > max_points:
        pts_b = pts_b[rng.choice(len(pts_b), max_points, replace=False)]

    def nn_mean(src, dst):
        # chunked brute force (dev-scale solids are small)
        chunk = 500
        mins = []
        for i in range(0, len(src), chunk):
            s = src[i : i + chunk]
            # (c, n, 3)
            d = np.linalg.norm(s[:, None, :] - dst[None, :, :], axis=2)
            mins.append(d.min(axis=1))
        return float(np.concatenate(mins).mean())

    return 0.5 * (nn_mean(pts_a, pts_b) + nn_mean(pts_b, pts_a))


def voxel_occupancy(
    shape: Any,
    resolution: int = 128,
    pad: float = 0.02,
    shared_bbox: Optional[Tuple[float, ...]] = None,
) -> Tuple[np.ndarray, Tuple[float, ...]]:
    """
    Approximate occupancy grid via surface samples + bbox fill using ray-free
    signed test: sample grid points and test containment with OCC BRepClass3d.
    For speed on coarse grids we use a hybrid: mesh-based winding via trimesh
    when possible, else surface dilation.
    """
    solid = solid_from_workplane(shape)
    if shared_bbox is None:
        bb = bbox_of(solid)
    else:
        bb = shared_bbox
    xmin, ymin, zmin, xmax, ymax, zmax = bb
    # pad
    sx, sy, sz = xmax - xmin, ymax - ymin, zmax - zmin
    pad_x, pad_y, pad_z = sx * pad + 1e-6, sy * pad + 1e-6, sz * pad + 1e-6
    xmin, ymin, zmin = xmin - pad_x, ymin - pad_y, zmin - pad_z
    xmax, ymax, zmax = xmax + pad_x, ymax + pad_y, zmax + pad_z
    grid_bbox = (xmin, ymin, zmin, xmax, ymax, zmax)

    # Prefer trimesh contains for speed
    try:
        import trimesh
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.TopLoc import TopLoc_Location
        from OCP.BRep import BRep_Tool
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_FACE
        from OCP.BRep import BRep_Tool as BT

        wrapped = solid.wrapped if hasattr(solid, "wrapped") else solid
        BRepMesh_IncrementalMesh(wrapped, 0.15, True, 0.5, True)
        # Use cadquery tessellate instead
        cq = _cq()
        s = solid if hasattr(solid, "tessellate") else solid
        verts, faces = s.tessellate(0.15, 0.5)
        if verts and faces:
            v = np.array([[p.x, p.y, p.z] for p in verts], dtype=np.float64)
            f = np.array(faces, dtype=np.int64)
            mesh = trimesh.Trimesh(vertices=v, faces=f, process=False)
            xs = np.linspace(xmin, xmax, resolution)
            ys = np.linspace(ymin, ymax, resolution)
            zs = np.linspace(zmin, zmax, resolution)
            # subsample for contains: full 128^3 is heavy; use batch
            # Build only surface shell + flood fill is hard; use contains on
            # a coarser check with vectorized trimesh
            xx, yy, zz = np.meshgrid(xs, ys, zs, indexing="ij")
            pts = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
            # trimesh.contains can be slow; batch it
            inside = np.zeros(len(pts), dtype=bool)
            batch = 20000
            for i in range(0, len(pts), batch):
                inside[i : i + batch] = mesh.contains(pts[i : i + batch])
            grid = inside.reshape(resolution, resolution, resolution)
            return grid, grid_bbox
    except Exception:
        pass

    # Fallback: mark voxels near surface samples (underestimates solid interior
    # but still provides a relative signal for similar shapes)
    pts = sample_surface_points(solid, n=20000, seed=1)
    xs = np.linspace(xmin, xmax, resolution)
    ys = np.linspace(ymin, ymax, resolution)
    zs = np.linspace(zmin, zmax, resolution)
    grid = np.zeros((resolution, resolution, resolution), dtype=bool)
    # map points to voxels
    ix = np.clip(
        ((pts[:, 0] - xmin) / max(xmax - xmin, 1e-9) * (resolution - 1)).astype(int),
        0,
        resolution - 1,
    )
    iy = np.clip(
        ((pts[:, 1] - ymin) / max(ymax - ymin, 1e-9) * (resolution - 1)).astype(int),
        0,
        resolution - 1,
    )
    iz = np.clip(
        ((pts[:, 2] - zmin) / max(zmax - zmin, 1e-9) * (resolution - 1)).astype(int),
        0,
        resolution - 1,
    )
    grid[ix, iy, iz] = True
    # small dilation to thicken shell
    from scipy import ndimage

    grid = ndimage.binary_dilation(grid, iterations=2)
    return grid, grid_bbox


def voxel_iou(
    shape_a: Any,
    shape_b: Any,
    resolution: int = 128,
) -> float:
    bb_a = bbox_of(shape_a)
    bb_b = bbox_of(shape_b)
    shared = (
        min(bb_a[0], bb_b[0]),
        min(bb_a[1], bb_b[1]),
        min(bb_a[2], bb_b[2]),
        max(bb_a[3], bb_b[3]),
        max(bb_a[4], bb_b[4]),
        max(bb_a[5], bb_b[5]),
    )
    ga, _ = voxel_occupancy(shape_a, resolution=resolution, shared_bbox=shared)
    gb, _ = voxel_occupancy(shape_b, resolution=resolution, shared_bbox=shared)
    inter = np.logical_and(ga, gb).sum()
    union = np.logical_or(ga, gb).sum()
    if union == 0:
        return 0.0
    return float(inter / union)


def exact_volume_iou(shape_a: Any, shape_b: Any) -> Optional[float]:
    """Exact volumetric IoU via OCC booleans. Returns None on failure."""
    try:
        o = _ocp()
        a = solid_from_workplane(shape_a)
        b = solid_from_workplane(shape_b)
        wa = a.wrapped if hasattr(a, "wrapped") else a
        wb = b.wrapped if hasattr(b, "wrapped") else b
        common = o["BRepAlgoAPI_Common"](wa, wb)
        common.Build()
        if not common.IsDone():
            return None
        fuse = o["BRepAlgoAPI_Fuse"](wa, wb)
        fuse.Build()
        if not fuse.IsDone():
            return None
        props_i = o["GProp_GProps"]()
        props_u = o["GProp_GProps"]()
        o["BRepGProp"].VolumeProperties(common.Shape(), props_i)
        o["BRepGProp"].VolumeProperties(fuse.Shape(), props_u)
        vi, vu = props_i.Mass(), props_u.Mass()
        if vu <= 1e-12:
            return 0.0
        return float(max(0.0, min(1.0, vi / vu)))
    except Exception:
        return None


def shape_error(
    pred: Any,
    gt: Any,
    resolution: int = 128,
    n_points: int = 30000,
    tau: float = 0.05,
    seed: int = 0,
) -> float:
    """
    shape_err = 0.5 * (1 - IoU) + 0.5 * clamp(CD_norm / tau, 0, 1)
    Prefer exact volume IoU when available.
    """
    if not is_valid_solid(pred):
        return 1.0
    if not is_valid_solid(gt):
        return 1.0

    # IoU
    exact = exact_volume_iou(pred, gt)
    if exact is not None:
        iou = exact
    else:
        iou = voxel_iou(pred, gt, resolution=resolution)
    shape_term = 1.0 - float(np.clip(iou, 0.0, 1.0))

    # Chamfer on unit box (use union bbox for normalization)
    bb_p = bbox_of(pred)
    bb_g = bbox_of(gt)
    shared = (
        min(bb_p[0], bb_g[0]),
        min(bb_p[1], bb_g[1]),
        min(bb_p[2], bb_g[2]),
        max(bb_p[3], bb_g[3]),
        max(bb_p[4], bb_g[4]),
        max(bb_p[5], bb_g[5]),
    )
    pts_p = sample_surface_points(pred, n=n_points, seed=seed)
    pts_g = sample_surface_points(gt, n=n_points, seed=seed + 1)
    pts_p_n = normalize_to_unit_box(pts_p, shared)
    pts_g_n = normalize_to_unit_box(pts_g, shared)
    cd = chamfer_distance(pts_p_n, pts_g_n)
    cd_term = float(np.clip(cd / tau, 0.0, 1.0))

    return 0.5 * shape_term + 0.5 * cd_term


def extract_topology(shape: Any) -> dict:
    """Lightweight topology summary for the baseline solver."""
    solid = solid_from_workplane(shape)
    o = _ocp()
    bb = bbox_of(solid)
    dims = (bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
    info = {
        "bbox": bb,
        "dims": dims,
        "volume": volume_of(solid),
        "n_faces": count_faces(solid),
        "n_solids": count_solids(solid),
        "planes": [],
        "cylinders": [],
        "other_faces": 0,
    }
    try:
        faces = solid.Faces() if hasattr(solid, "Faces") else []
        for f in faces:
            try:
                surf = f.geomAdapter() if hasattr(f, "geomAdapter") else None
                # Use Surface type via OCP
                adaptor = o["BRepAdaptor_Surface"](f.wrapped)
                st = adaptor.GetType()
                if st == o["GeomAbs_Plane"]:
                    pln = adaptor.Plane()
                    ax = pln.Axis().Direction()
                    loc = pln.Location()
                    info["planes"].append(
                        {
                            "normal": (ax.X(), ax.Y(), ax.Z()),
                            "origin": (loc.X(), loc.Y(), loc.Z()),
                            "area": float(f.Area()) if hasattr(f, "Area") else 0.0,
                        }
                    )
                elif st == o["GeomAbs_Cylinder"]:
                    cyl = adaptor.Cylinder()
                    ax = cyl.Axis().Direction()
                    loc = cyl.Location()
                    info["cylinders"].append(
                        {
                            "axis": (ax.X(), ax.Y(), ax.Z()),
                            "origin": (loc.X(), loc.Y(), loc.Z()),
                            "radius": float(cyl.Radius()),
                            "area": float(f.Area()) if hasattr(f, "Area") else 0.0,
                        }
                    )
                else:
                    info["other_faces"] += 1
            except Exception:
                info["other_faces"] += 1
    except Exception:
        pass
    return info
