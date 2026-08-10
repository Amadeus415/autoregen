"""Procedural parametric family generator (L1/L2/L3). Immutable."""

from __future__ import annotations

import json
import math
import random
import textwrap
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import geom


# ---------------------------------------------------------------------------
# Param / family schemas
# ---------------------------------------------------------------------------

@dataclass
class ParamSpec:
    name: str
    unit: str
    type: str  # "float" | "int"
    range: Tuple[float, float]
    default: float


@dataclass
class FamilySpec:
    family_id: str
    level: str  # L1 | L2 | L3
    grammar: str  # production name
    params: List[ParamSpec]
    program_src: str  # source of build(**params)
    dependencies: List[str] = field(default_factory=list)
    seed: int = 0


# ---------------------------------------------------------------------------
# GT program templates — each returns (params, src, dependencies)
# ---------------------------------------------------------------------------

def _fmt_params(params: List[ParamSpec]) -> str:
    parts = []
    for p in params:
        if p.type == "int":
            parts.append(f"{p.name}: int")
        else:
            parts.append(f"{p.name}: float")
    return ", ".join(parts)


def fam_l1_plate_extrude(rng: random.Random, seed: int) -> FamilySpec:
    """Simple rectangular plate extrude. Params: plate_w, plate_h, plate_t."""
    params = [
        ParamSpec("plate_w", "mm", "float", (20.0, 80.0), 40.0),
        ParamSpec("plate_h", "mm", "float", (15.0, 60.0), 30.0),
        ParamSpec("plate_t", "mm", "float", (2.0, 12.0), 5.0),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(plate_w: float, plate_h: float, plate_t: float):
            return (
                cq.Workplane("XY")
                .rect(plate_w, plate_h)
                .extrude(plate_t)
            )
        '''
    )
    return FamilySpec(
        family_id="",
        level="L1",
        grammar="l1_plate_extrude",
        params=params,
        program_src=src,
        dependencies=[],
        seed=seed,
    )


def fam_l1_plate_hole(rng: random.Random, seed: int) -> FamilySpec:
    """Plate with centered through-hole."""
    params = [
        ParamSpec("plate_w", "mm", "float", (25.0, 80.0), 50.0),
        ParamSpec("plate_h", "mm", "float", (25.0, 80.0), 50.0),
        ParamSpec("plate_t", "mm", "float", (3.0, 15.0), 6.0),
        ParamSpec("hole_d", "mm", "float", (3.0, 20.0), 8.0),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(plate_w: float, plate_h: float, plate_t: float, hole_d: float):
            # ensure hole fits
            d = min(hole_d, min(plate_w, plate_h) * 0.7)
            return (
                cq.Workplane("XY")
                .rect(plate_w, plate_h)
                .extrude(plate_t)
                .faces(">Z")
                .workplane()
                .hole(d)
            )
        '''
    )
    return FamilySpec(
        family_id="",
        level="L1",
        grammar="l1_plate_hole",
        params=params,
        program_src=src,
        dependencies=["hole_d < min(plate_w, plate_h) * 0.7"],
        seed=seed,
    )


def fam_l1_cylinder_revolve(rng: random.Random, seed: int) -> FamilySpec:
    """Solid of revolution: disk with optional bore."""
    params = [
        ParamSpec("outer_r", "mm", "float", (10.0, 40.0), 20.0),
        ParamSpec("height", "mm", "float", (5.0, 40.0), 15.0),
        ParamSpec("bore_d", "mm", "float", (0.0, 15.0), 5.0),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(outer_r: float, height: float, bore_d: float):
            solid = cq.Workplane("XY").circle(outer_r).extrude(height)
            if bore_d > 0.5 and bore_d < outer_r * 1.6:
                solid = solid.faces(">Z").workplane().hole(min(bore_d, outer_r * 1.5))
            return solid
        '''
    )
    return FamilySpec(
        family_id="",
        level="L1",
        grammar="l1_cylinder_revolve",
        params=params,
        program_src=src,
        dependencies=["bore_d < 2 * outer_r"],
        seed=seed,
    )


def fam_l1_block_slot(rng: random.Random, seed: int) -> FamilySpec:
    """Rectangular block with a rectangular through-slot."""
    params = [
        ParamSpec("block_l", "mm", "float", (30.0, 90.0), 60.0),
        ParamSpec("block_w", "mm", "float", (20.0, 60.0), 40.0),
        ParamSpec("block_t", "mm", "float", (8.0, 25.0), 12.0),
        ParamSpec("slot_w", "mm", "float", (4.0, 20.0), 8.0),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(block_l: float, block_w: float, block_t: float, slot_w: float):
            sw = min(slot_w, block_w * 0.6)
            sl = block_l * 0.5
            return (
                cq.Workplane("XY")
                .box(block_l, block_w, block_t)
                .faces(">Z")
                .workplane()
                .rect(sl, sw)
                .cutThruAll()
            )
        '''
    )
    return FamilySpec(
        family_id="",
        level="L1",
        grammar="l1_block_slot",
        params=params,
        program_src=src,
        dependencies=["slot_w < block_w"],
        seed=seed,
    )


def fam_l2_plate_hole_fillet(rng: random.Random, seed: int) -> FamilySpec:
    """Plate + hole + edge fillets. Dependency: fillet_r < plate_t / 2."""
    params = [
        ParamSpec("plate_w", "mm", "float", (30.0, 80.0), 50.0),
        ParamSpec("plate_h", "mm", "float", (30.0, 80.0), 50.0),
        ParamSpec("plate_t", "mm", "float", (4.0, 16.0), 8.0),
        ParamSpec("hole_d", "mm", "float", (4.0, 18.0), 10.0),
        ParamSpec("fillet_r", "mm", "float", (0.5, 4.0), 1.5),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(plate_w: float, plate_h: float, plate_t: float, hole_d: float, fillet_r: float):
            d = min(hole_d, min(plate_w, plate_h) * 0.6)
            fr = min(fillet_r, plate_t * 0.45, d * 0.3)
            solid = (
                cq.Workplane("XY")
                .rect(plate_w, plate_h)
                .extrude(plate_t)
                .edges("|Z")
                .fillet(max(fr, 0.1))
                .faces(">Z")
                .workplane()
                .hole(d)
            )
            return solid
        '''
    )
    return FamilySpec(
        family_id="",
        level="L2",
        grammar="l2_plate_hole_fillet",
        params=params,
        program_src=src,
        dependencies=["fillet_r < plate_t / 2", "hole_d < min(plate_w, plate_h)"],
        seed=seed,
    )


def fam_l2_plate_hole_pattern(rng: random.Random, seed: int) -> FamilySpec:
    """Plate with linear pattern of holes."""
    params = [
        ParamSpec("plate_w", "mm", "float", (40.0, 100.0), 70.0),
        ParamSpec("plate_h", "mm", "float", (25.0, 60.0), 40.0),
        ParamSpec("plate_t", "mm", "float", (3.0, 12.0), 5.0),
        ParamSpec("hole_d", "mm", "float", (3.0, 10.0), 5.0),
        ParamSpec("hole_count", "mm", "int", (2, 5), 3),
        ParamSpec("pitch", "mm", "float", (12.0, 30.0), 18.0),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(plate_w: float, plate_h: float, plate_t: float, hole_d: float, hole_count: int, pitch: float):
            n = max(2, min(int(hole_count), 6))
            d = min(hole_d, plate_h * 0.5)
            p = min(pitch, (plate_w - d) / max(n - 1, 1) * 0.9)
            total = p * (n - 1)
            xs = [ -total / 2 + i * p for i in range(n) ]
            solid = cq.Workplane("XY").rect(plate_w, plate_h).extrude(plate_t)
            solid = (
                solid.faces(">Z")
                .workplane()
                .pushPoints([(x, 0) for x in xs])
                .hole(d)
            )
            return solid
        '''
    )
    return FamilySpec(
        family_id="",
        level="L2",
        grammar="l2_plate_hole_pattern",
        params=params,
        program_src=src,
        dependencies=["pitch * (hole_count-1) < plate_w"],
        seed=seed,
    )


def fam_l2_pocket_counterbore(rng: random.Random, seed: int) -> FamilySpec:
    """Block with rectangular pocket and counterbored hole."""
    params = [
        ParamSpec("block_l", "mm", "float", (40.0, 90.0), 60.0),
        ParamSpec("block_w", "mm", "float", (30.0, 70.0), 45.0),
        ParamSpec("block_t", "mm", "float", (12.0, 30.0), 18.0),
        ParamSpec("pocket_d", "mm", "float", (3.0, 12.0), 6.0),
        ParamSpec("hole_d", "mm", "float", (4.0, 12.0), 6.0),
        ParamSpec("cbore_d", "mm", "float", (8.0, 20.0), 12.0),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(block_l: float, block_w: float, block_t: float, pocket_d: float, hole_d: float, cbore_d: float):
            pd = min(pocket_d, block_t * 0.6)
            hd = min(hole_d, min(block_l, block_w) * 0.25)
            cd = max(hd * 1.4, min(cbore_d, min(block_l, block_w) * 0.4))
            solid = (
                cq.Workplane("XY")
                .box(block_l, block_w, block_t)
                .faces(">Z")
                .workplane()
                .rect(block_l * 0.5, block_w * 0.5)
                .cutBlind(-pd)
                .faces(">Z")
                .workplane()
                .cboreHole(hd, cd, min(pd * 0.5, 3.0))
            )
            return solid
        '''
    )
    return FamilySpec(
        family_id="",
        level="L2",
        grammar="l2_pocket_counterbore",
        params=params,
        program_src=src,
        dependencies=["pocket_d < block_t", "cbore_d > hole_d"],
        seed=seed,
    )


def fam_l2_shell_box(rng: random.Random, seed: int) -> FamilySpec:
    """Hollow box shell with wall thickness and open top."""
    params = [
        ParamSpec("box_l", "mm", "float", (30.0, 80.0), 50.0),
        ParamSpec("box_w", "mm", "float", (25.0, 70.0), 40.0),
        ParamSpec("box_h", "mm", "float", (15.0, 50.0), 30.0),
        ParamSpec("wall_t", "mm", "float", (1.5, 5.0), 2.5),
        ParamSpec("fillet_r", "mm", "float", (0.5, 3.0), 1.0),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(box_l: float, box_w: float, box_h: float, wall_t: float, fillet_r: float):
            wt = min(wall_t, min(box_l, box_w) * 0.2)
            fr = min(fillet_r, wt * 0.8)
            solid = (
                cq.Workplane("XY")
                .box(box_l, box_w, box_h)
                .edges("|Z")
                .fillet(max(fr, 0.1))
                .faces(">Z")
                .shell(-wt)
            )
            return solid
        '''
    )
    return FamilySpec(
        family_id="",
        level="L2",
        grammar="l2_shell_box",
        params=params,
        program_src=src,
        dependencies=["wall_t < min(box_l, box_w) / 4"],
        seed=seed,
    )


def fam_l3_ribbed_plate(rng: random.Random, seed: int) -> FamilySpec:
    """Plate with reinforcing ribs and mounting holes. Multiple dependencies."""
    params = [
        ParamSpec("plate_w", "mm", "float", (50.0, 100.0), 70.0),
        ParamSpec("plate_h", "mm", "float", (40.0, 80.0), 50.0),
        ParamSpec("plate_t", "mm", "float", (3.0, 8.0), 4.0),
        ParamSpec("rib_h", "mm", "float", (6.0, 20.0), 12.0),
        ParamSpec("rib_t", "mm", "float", (2.0, 6.0), 3.0),
        ParamSpec("rib_count", "mm", "int", (2, 5), 3),
        ParamSpec("hole_d", "mm", "float", (3.0, 8.0), 5.0),
        ParamSpec("fillet_r", "mm", "float", (0.3, 2.0), 0.8),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(plate_w: float, plate_h: float, plate_t: float, rib_h: float,
                  rib_t: float, rib_count: int, hole_d: float, fillet_r: float):
            n = max(2, min(int(rib_count), 6))
            rt = min(rib_t, plate_w / (n + 2))
            rh = max(rib_h, plate_t)
            fr = min(fillet_r, plate_t * 0.4, rt * 0.4)
            d = min(hole_d, plate_h * 0.3)
            plate = cq.Workplane("XY").box(plate_w, plate_h, plate_t)
            # ribs along X, spaced in Y
            spacing = plate_h * 0.7 / max(n - 1, 1)
            ys = [ -plate_h * 0.35 + i * spacing for i in range(n) ]
            ribs = cq.Workplane("XY")
            for y in ys:
                rib = (
                    cq.Workplane("XY")
                    .center(0, y)
                    .box(plate_w * 0.9, rt, rh)
                    .translate((0, 0, plate_t / 2 + rh / 2))
                )
                plate = plate.union(rib)
            # corner holes
            m = plate_w * 0.35
            n2 = plate_h * 0.35
            plate = (
                plate.faces(">Z")
                .workplane(centerOption="CenterOfBoundBox")
                .pushPoints([(m, n2), (m, -n2), (-m, n2), (-m, -n2)])
                .hole(d)
            )
            try:
                plate = plate.edges("|Z").fillet(max(fr, 0.1))
            except Exception:
                pass
            return plate
        '''
    )
    return FamilySpec(
        family_id="",
        level="L3",
        grammar="l3_ribbed_plate",
        params=params,
        program_src=src,
        dependencies=[
            "rib_t < plate_w / rib_count",
            "fillet_r < plate_t / 2",
            "hole_d < plate_h / 3",
        ],
        seed=seed,
    )


def fam_l3_boss_interface(rng: random.Random, seed: int) -> FamilySpec:
    """Base plate with cylindrical bosses and clearance holes (mating interface)."""
    params = [
        ParamSpec("base_w", "mm", "float", (40.0, 90.0), 60.0),
        ParamSpec("base_h", "mm", "float", (40.0, 90.0), 60.0),
        ParamSpec("base_t", "mm", "float", (4.0, 12.0), 6.0),
        ParamSpec("boss_d", "mm", "float", (8.0, 20.0), 12.0),
        ParamSpec("boss_h", "mm", "float", (5.0, 18.0), 10.0),
        ParamSpec("boss_count", "mm", "int", (2, 4), 2),
        ParamSpec("clearance_d", "mm", "float", (3.0, 10.0), 5.0),
        ParamSpec("chamfer_s", "mm", "float", (0.3, 2.0), 0.8),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(base_w: float, base_h: float, base_t: float, boss_d: float,
                  boss_h: float, boss_count: int, clearance_d: float, chamfer_s: float):
            n = max(2, min(int(boss_count), 4))
            bd = min(boss_d, min(base_w, base_h) * 0.35)
            cd = min(clearance_d, bd * 0.7)
            ch = min(chamfer_s, base_t * 0.3, bd * 0.15)
            base = cq.Workplane("XY").box(base_w, base_h, base_t)
            # place bosses
            if n == 2:
                pts = [(base_w * 0.25, 0), (-base_w * 0.25, 0)]
            elif n == 3:
                pts = [(base_w * 0.25, base_h * 0.2), (-base_w * 0.25, base_h * 0.2), (0, -base_h * 0.2)]
            else:
                pts = [
                    (base_w * 0.25, base_h * 0.25),
                    (base_w * 0.25, -base_h * 0.25),
                    (-base_w * 0.25, base_h * 0.25),
                    (-base_w * 0.25, -base_h * 0.25),
                ]
            for x, y in pts:
                boss = (
                    cq.Workplane("XY")
                    .center(x, y)
                    .circle(bd / 2)
                    .extrude(boss_h)
                    .translate((0, 0, base_t / 2))
                )
                base = base.union(boss)
            base = (
                base.faces(">Z")
                .workplane(centerOption="CenterOfBoundBox")
                .pushPoints(pts)
                .hole(cd)
            )
            try:
                base = base.edges("#Z").chamfer(max(ch, 0.1))
            except Exception:
                pass
            return base
        '''
    )
    return FamilySpec(
        family_id="",
        level="L3",
        grammar="l3_boss_interface",
        params=params,
        program_src=src,
        dependencies=[
            "clearance_d < boss_d",
            "boss_d < min(base_w, base_h) / 2",
            "chamfer_s < base_t / 2",
        ],
        seed=seed,
    )


# OOD grammars — only used in test-ood, never in train/dev
def fam_ood_helix_cut(rng: random.Random, seed: int) -> FamilySpec:
    """Twisted/swept-ish feature via lofted cut — absent from train grammar."""
    params = [
        ParamSpec("body_r", "mm", "float", (15.0, 35.0), 25.0),
        ParamSpec("body_h", "mm", "float", (20.0, 50.0), 35.0),
        ParamSpec("cut_w", "mm", "float", (4.0, 12.0), 6.0),
        ParamSpec("cut_depth", "mm", "float", (3.0, 10.0), 5.0),
        ParamSpec("twist_n", "mm", "int", (1, 3), 2),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(body_r: float, body_h: float, cut_w: float, cut_depth: float, twist_n: int):
            body = cq.Workplane("XY").circle(body_r).extrude(body_h)
            # radial slots at twisted angles
            n = max(1, min(int(twist_n), 4))
            for i in range(n):
                ang = i * (180.0 / n)
                slot = (
                    cq.Workplane("XY")
                    .transformed(rotate=(0, 0, ang))
                    .center(body_r - cut_depth / 2, 0)
                    .rect(cut_depth, cut_w)
                    .extrude(body_h)
                )
                body = body.cut(slot)
            return body
        '''
    )
    return FamilySpec(
        family_id="",
        level="OOD",
        grammar="ood_helix_cut",
        params=params,
        program_src=src,
        dependencies=[],
        seed=seed,
    )


def fam_ood_wedge_draft(rng: random.Random, seed: int) -> FamilySpec:
    """Wedge with draft-like taper via loft — OOD grammar."""
    params = [
        ParamSpec("base_w", "mm", "float", (30.0, 70.0), 50.0),
        ParamSpec("base_h", "mm", "float", (30.0, 70.0), 40.0),
        ParamSpec("top_scale", "mm", "float", (0.4, 0.9), 0.6),
        ParamSpec("height", "mm", "float", (15.0, 40.0), 25.0),
        ParamSpec("hole_d", "mm", "float", (3.0, 12.0), 6.0),
    ]
    src = textwrap.dedent(
        '''\
        import cadquery as cq

        def build(base_w: float, base_h: float, top_scale: float, height: float, hole_d: float):
            s = max(0.3, min(top_scale, 0.95))
            solid = (
                cq.Workplane("XY")
                .rect(base_w, base_h)
                .workplane(offset=height)
                .rect(base_w * s, base_h * s)
                .loft(combine=True)
            )
            d = min(hole_d, min(base_w, base_h) * s * 0.5)
            try:
                solid = solid.faces(">Z").workplane().hole(d)
            except Exception:
                pass
            return solid
        '''
    )
    return FamilySpec(
        family_id="",
        level="OOD",
        grammar="ood_wedge_draft",
        params=params,
        program_src=src,
        dependencies=["top_scale < 1"],
        seed=seed,
    )


TRAIN_DEV_PRODUCTIONS = [
    fam_l1_plate_extrude,
    fam_l1_plate_hole,
    fam_l1_cylinder_revolve,
    fam_l1_block_slot,
    fam_l2_plate_hole_fillet,
    fam_l2_plate_hole_pattern,
    fam_l2_pocket_counterbore,
    fam_l2_shell_box,
    fam_l3_ribbed_plate,
    fam_l3_boss_interface,
]

OOD_PRODUCTIONS = [
    fam_ood_helix_cut,
    fam_ood_wedge_draft,
]


def sample_param_vector(params: List[ParamSpec], rng: random.Random) -> Dict[str, float]:
    vec = {}
    for p in params:
        lo, hi = p.range
        if p.type == "int":
            vec[p.name] = float(rng.randint(int(lo), int(hi)))
        else:
            vec[p.name] = float(rng.uniform(lo, hi))
    return vec


def cast_params(params: List[ParamSpec], vec: Dict[str, float]) -> Dict[str, Any]:
    out = {}
    for p in params:
        v = vec[p.name]
        out[p.name] = int(round(v)) if p.type == "int" else float(v)
    return out


def load_build_fn(program_src: str):
    ns: Dict[str, Any] = {}
    exec(compile(program_src, "<gt_program>", "exec"), ns, ns)
    if "build" not in ns:
        raise RuntimeError("GT program missing build()")
    return ns["build"]


def validate_family(
    spec: FamilySpec,
    members: List[Dict[str, float]],
    min_member_iou_distinct: float = 0.9,
) -> Tuple[bool, str]:
    """All members must regenerate as valid distinct solids."""
    try:
        build = load_build_fn(spec.program_src)
    except Exception as e:
        return False, f"import: {e}"

    solids = []
    for i, vec in enumerate(members):
        try:
            kwargs = cast_params(spec.params, vec)
            solid = build(**kwargs)
            if not geom.is_valid_solid(solid):
                return False, f"member {i} invalid solid"
            solids.append(solid)
        except Exception as e:
            return False, f"member {i} build failed: {e}"

    # pairwise distinctness via volume IoU
    for i in range(len(solids)):
        for j in range(i + 1, len(solids)):
            try:
                iou = geom.exact_volume_iou(solids[i], solids[j])
                if iou is None:
                    # fallback: volume ratio
                    vi, vj = geom.volume_of(solids[i]), geom.volume_of(solids[j])
                    ratio = min(vi, vj) / max(vi, vj, 1e-12)
                    if ratio > 0.98:
                        # also check bbox dims
                        di = geom.bbox_of(solids[i])
                        dj = geom.bbox_of(solids[j])
                        dims_i = (di[3] - di[0], di[4] - di[1], di[5] - di[2])
                        dims_j = (dj[3] - dj[0], dj[4] - dj[1], dj[5] - dj[2])
                        if all(abs(a - b) < 0.5 for a, b in zip(dims_i, dims_j)):
                            return False, f"members {i},{j} not distinct"
                elif iou >= min_member_iou_distinct:
                    return False, f"members {i},{j} IoU={iou:.3f} too similar"
            except Exception:
                pass
    return True, "ok"


def make_members(spec: FamilySpec, rng: random.Random, k_heldout: int = 4) -> List[Dict[str, float]]:
    """Observed + K held-out parameter vectors."""
    members = []
    attempts = 0
    while len(members) < 1 + k_heldout and attempts < 80:
        attempts += 1
        vec = sample_param_vector(spec.params, rng)
        # crude dependency soft-enforcement
        ok = True
        for p in spec.params:
            if p.name.endswith("_r") or "fillet" in p.name:
                # find a thickness-like param
                for tname in ("plate_t", "block_t", "base_t", "wall_t", "box_h"):
                    if tname in vec and vec[p.name] > vec[tname] * 0.45:
                        vec[p.name] = vec[tname] * 0.3
            if "hole" in p.name and p.name.endswith("_d"):
                for wname in ("plate_w", "plate_h", "block_l", "block_w", "base_w", "outer_r"):
                    if wname in vec and vec[p.name] > vec[wname] * 0.6:
                        vec[p.name] = vec[wname] * 0.3
        # ensure not too close to existing
        too_close = False
        for existing in members:
            dist = sum(abs(vec[k] - existing[k]) / max(abs(existing[k]), 1.0) for k in vec)
            if dist < 0.15 * len(vec):
                too_close = True
                break
        if too_close:
            continue
        members.append(vec)
    return members


def write_family(
    root: Path,
    gt_root: Path,
    split: str,
    family_id: str,
    spec: FamilySpec,
    members: List[Dict[str, float]],
    render_views: bool = False,
) -> None:
    """Write task inputs under data/families and sealed GT under data/gt."""
    task_dir = root / split / family_id
    gt_dir = gt_root / split / family_id
    task_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir(parents=True, exist_ok=True)

    build = load_build_fn(spec.program_src)
    observed = members[0]
    kwargs = cast_params(spec.params, observed)
    solid = build(**kwargs)
    geom.export_step(solid, task_dir / "target.step")

    params_json = {
        "params": [
            {
                "name": p.name,
                "unit": p.unit,
                "type": p.type,
                "range": list(p.range),
            }
            for p in spec.params
        ],
        "dependencies_hint": spec.dependencies,  # names of constraints, not values
    }
    (task_dir / "params.json").write_text(json.dumps(params_json, indent=2))
    (task_dir / "budget.json").write_text(
        json.dumps(
            {
                "wall_clock_s": 90,
                "tokens": 0,
                "per_member_timeout_s": 20,
            },
            indent=2,
        )
    )
    (task_dir / "meta.json").write_text(
        json.dumps(
            {
                "family_id": family_id,
                "level": spec.level,
                "grammar": spec.grammar,
                "split": split,
                "seed": spec.seed,
                "n_params": len(spec.params),
            },
            indent=2,
        )
    )

    # views optional
    views_dir = task_dir / "views"
    views_dir.mkdir(exist_ok=True)
    (views_dir / ".gitkeep").write_text("")

    # sealed GT
    (gt_dir / "program.py").write_text(spec.program_src)
    (gt_dir / "members.json").write_text(
        json.dumps(
            {
                "observed": observed,
                "heldout": members[1:],
                "all": members,
            },
            indent=2,
        )
    )
    (gt_dir / "meta.json").write_text(
        json.dumps(
            {
                "family_id": family_id,
                "level": spec.level,
                "grammar": spec.grammar,
                "params": [asdict(p) for p in spec.params],
            },
            indent=2,
        )
    )


def generate_split(
    split: str,
    n: int,
    seed: int,
    families_root: Path,
    gt_root: Path,
    ood: bool = False,
    level_weights: Optional[Dict[str, float]] = None,
) -> int:
    """Generate n validated families for a split. Returns count written."""
    rng = random.Random(seed)
    productions = OOD_PRODUCTIONS if ood else TRAIN_DEV_PRODUCTIONS
    if level_weights is None:
        # Slightly L2/L3-heavy so a bbox/heuristic baseline stays mediocre
        level_weights = {"L1": 0.25, "L2": 0.45, "L3": 0.30}

    written = 0
    attempts = 0
    max_attempts = n * 30

    while written < n and attempts < max_attempts:
        attempts += 1
        prod = rng.choice(productions)
        fam_seed = rng.randint(0, 2**31 - 1)
        fam_rng = random.Random(fam_seed)
        spec = prod(fam_rng, fam_seed)

        if not ood and level_weights:
            # re-roll to match level mix
            r = rng.random()
            cum = 0.0
            target_level = "L1"
            for lv, w in level_weights.items():
                cum += w
                if r <= cum:
                    target_level = lv
                    break
            level_prods = [p for p in productions if p(fam_rng, fam_seed).level == target_level]
            # reset rng and pick properly
            if level_prods:
                # pick by name match on level
                candidates = []
                for p in productions:
                    # instantiate with throwaway to check level — inefficient but ok
                    pass
                # simpler: filter known
                level_map = {
                    "L1": [fam_l1_plate_extrude, fam_l1_plate_hole, fam_l1_cylinder_revolve, fam_l1_block_slot],
                    "L2": [fam_l2_plate_hole_fillet, fam_l2_plate_hole_pattern, fam_l2_pocket_counterbore, fam_l2_shell_box],
                    "L3": [fam_l3_ribbed_plate, fam_l3_boss_interface],
                }
                pool = level_map.get(target_level, productions)
                prod = rng.choice(pool)
                fam_seed = rng.randint(0, 2**31 - 1)
                fam_rng = random.Random(fam_seed)
                spec = prod(fam_rng, fam_seed)

        members = make_members(spec, fam_rng, k_heldout=4)
        if len(members) < 5:
            continue

        ok, reason = validate_family(spec, members)
        if not ok:
            continue

        family_id = f"{spec.grammar}_{fam_seed:08x}"
        spec.family_id = family_id
        write_family(families_root, gt_root, split, family_id, spec, members)
        written += 1
        if written % 10 == 0 or written == n:
            print(f"  [{split}] {written}/{n} families (attempts={attempts})")

    return written


def generate_all(
    data_root: Path,
    seed: int = 42,
    sizes: Optional[Dict[str, int]] = None,
    quick: bool = False,
) -> Dict[str, int]:
    """
    Generate full dataset splits.

    Default sizes from the design spec. Use quick=True for a tiny smoke set.
    """
    if sizes is None:
        if quick:
            # Harder mix so gen-0 lands near the 0.55–0.70 band even on a tiny set
            sizes = {"train": 12, "dev": 8, "test": 4, "test-ood": 2}
        else:
            sizes = {"train": 512, "dev": 64, "test": 256, "test-ood": 128}

    families_root = data_root / "families"
    gt_root = data_root / "gt"
    families_root.mkdir(parents=True, exist_ok=True)
    gt_root.mkdir(parents=True, exist_ok=True)

    counts = {}
    # independent seeds per split for non-leakage
    split_seeds = {
        "train": seed + 1,
        "dev": seed + 2,
        "test": seed + 3,
        "test-ood": seed + 4,
    }
    # Quick smoke sets bias toward L2/L3 so baseline isn't already saturated
    weights = {"L1": 0.15, "L2": 0.45, "L3": 0.40} if quick else None

    for split, n in sizes.items():
        print(f"Generating split={split} n={n} ...")
        counts[split] = generate_split(
            split=split,
            n=n,
            seed=split_seeds[split],
            families_root=families_root,
            gt_root=gt_root,
            ood=(split == "test-ood"),
            level_weights=weights,
        )
    # write split manifest
    manifest = {
        "seed": seed,
        "sizes_requested": sizes,
        "sizes_written": counts,
        "productions_train_dev": [p.__name__ for p in TRAIN_DEV_PRODUCTIONS],
        "productions_ood": [p.__name__ for p in OOD_PRODUCTIONS],
    }
    (data_root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return counts
