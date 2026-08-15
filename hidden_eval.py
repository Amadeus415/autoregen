"""Sealed family builders and member vectors.

The agent workspace does not include this file. prepare.py imports it to
generate tasks and to rebuild ground-truth solids at held-out parameters.

Twelve families, each a distinct design-intent recovery. Offset holes/bosses
exist so a centered feature is not a complete answer — centroid still moves.
"""

from __future__ import annotations

from typing import Callable


def _cq():
    import cadquery as cq

    return cq


def box(p: dict) -> object:
    return _cq().Workplane("XY").box(p["width"], p["depth"], p["height"])


def cylinder(p: dict) -> object:
    return _cq().Workplane("XY").circle(p["radius"]).extrude(p["height"])


def tube(p: dict) -> object:
    return (
        _cq()
        .Workplane("XY")
        .circle(p["outer_r"])
        .circle(p["inner_r"])
        .extrude(p["height"])
    )


def plate_hole(p: dict) -> object:
    return (
        _cq()
        .Workplane("XY")
        .box(p["width"], p["depth"], p["thick"])
        .faces(">Z")
        .workplane()
        .hole(p["hole_d"])
    )


def offset_hole(p: dict) -> object:
    return (
        _cq()
        .Workplane("XY")
        .box(p["width"], p["depth"], p["thick"])
        .faces(">Z")
        .workplane()
        .center(p["hole_x"], p["hole_y"])
        .hole(p["hole_d"])
    )


def boss(p: dict) -> object:
    return (
        _cq()
        .Workplane("XY")
        .box(p["width"], p["depth"], p["plate_t"])
        .faces(">Z")
        .workplane()
        .circle(p["boss_d"] / 2.0)
        .extrude(p["boss_h"])
    )


def offset_boss(p: dict) -> object:
    return (
        _cq()
        .Workplane("XY")
        .box(p["width"], p["depth"], p["plate_t"])
        .faces(">Z")
        .workplane()
        .center(p["boss_x"], p["boss_y"])
        .circle(p["boss_d"] / 2.0)
        .extrude(p["boss_h"])
    )


def filleted_box(p: dict) -> object:
    return (
        _cq()
        .Workplane("XY")
        .box(p["width"], p["depth"], p["height"])
        .edges()
        .fillet(p["fillet_r"])
    )


def chamfered_box(p: dict) -> object:
    return (
        _cq()
        .Workplane("XY")
        .box(p["width"], p["depth"], p["height"])
        .edges(">Z")
        .chamfer(p["chamfer"])
    )


def counterbore(p: dict) -> object:
    return (
        _cq()
        .Workplane("XY")
        .box(p["width"], p["depth"], p["thick"])
        .faces(">Z")
        .workplane()
        .cboreHole(p["hole_d"], p["cbore_d"], p["cbore_h"])
    )


def slotted_plate(p: dict) -> object:
    return (
        _cq()
        .Workplane("XY")
        .box(p["width"], p["depth"], p["thick"])
        .faces(">Z")
        .workplane()
        .slot2D(p["slot_l"], p["slot_w"])
        .cutThruAll()
    )


def hole_pair(p: dict) -> object:
    half = p["pitch"] / 2.0
    return (
        _cq()
        .Workplane("XY")
        .box(p["width"], p["depth"], p["thick"])
        .faces(">Z")
        .workplane()
        .pushPoints([(-half, 0.0), (half, 0.0)])
        .hole(p["hole_d"])
    )


FAMILIES: list[dict] = [
    {
        "key": "A",
        "names": ["width", "depth", "height"],
        "ranges": {"width": [15, 80], "depth": [15, 80], "height": [8, 40]},
        "build": box,
        "observed": {"width": 40, "depth": 20, "height": 10},
        "heldout": [
            {"width": 70, "depth": 25, "height": 12},
            {"width": 35, "depth": 35, "height": 20},
            {"width": 22, "depth": 55, "height": 14},
        ],
    },
    {
        "key": "C",
        "names": ["radius", "height"],
        "ranges": {"radius": [6, 20], "height": [10, 50]},
        "build": cylinder,
        "observed": {"radius": 10, "height": 30},
        "heldout": [
            {"radius": 16, "height": 20},
            {"radius": 8, "height": 40},
            {"radius": 12, "height": 12},
        ],
    },
    {
        "key": "D",
        "names": ["outer_r", "inner_r", "height"],
        "ranges": {"outer_r": [8, 22], "inner_r": [3, 12], "height": [12, 40]},
        "build": tube,
        "observed": {"outer_r": 12, "inner_r": 6, "height": 25},
        "heldout": [
            {"outer_r": 18, "inner_r": 8, "height": 20},
            {"outer_r": 10, "inner_r": 5, "height": 30},
            {"outer_r": 15, "inner_r": 4, "height": 15},
        ],
    },
    {
        "key": "B",
        "names": ["width", "depth", "thick", "hole_d"],
        "ranges": {
            "width": [30, 90],
            "depth": [20, 70],
            "thick": [4, 12],
            "hole_d": [4, 16],
        },
        "build": plate_hole,
        "observed": {"width": 50, "depth": 30, "thick": 6, "hole_d": 8},
        "heldout": [
            {"width": 80, "depth": 40, "thick": 8, "hole_d": 12},
            {"width": 40, "depth": 40, "thick": 5, "hole_d": 6},
            {"width": 60, "depth": 25, "thick": 10, "hole_d": 10},
        ],
    },
    {
        "key": "F",
        "names": ["width", "depth", "thick", "hole_d", "hole_x", "hole_y"],
        "ranges": {
            "width": [40, 90],
            "depth": [24, 60],
            "thick": [4, 12],
            "hole_d": [4, 12],
            "hole_x": [-18, 18],
            "hole_y": [-12, 12],
        },
        "build": offset_hole,
        "observed": {
            "width": 56,
            "depth": 34,
            "thick": 6,
            "hole_d": 8,
            "hole_x": 12,
            "hole_y": 6,
        },
        "heldout": [
            {"width": 80, "depth": 44, "thick": 8, "hole_d": 10, "hole_x": 18, "hole_y": -8},
            {"width": 48, "depth": 36, "thick": 5, "hole_d": 6, "hole_x": -14, "hole_y": 9},
            {"width": 64, "depth": 28, "thick": 7, "hole_d": 9, "hole_x": 8, "hole_y": -5},
        ],
    },
    {
        "key": "E",
        "names": ["width", "depth", "plate_t", "boss_d", "boss_h"],
        "ranges": {
            "width": [30, 70],
            "depth": [20, 50],
            "plate_t": [4, 10],
            "boss_d": [8, 18],
            "boss_h": [4, 14],
        },
        "build": boss,
        "observed": {
            "width": 40,
            "depth": 30,
            "plate_t": 5,
            "boss_d": 12,
            "boss_h": 8,
        },
        "heldout": [
            {"width": 60, "depth": 40, "plate_t": 6, "boss_d": 16, "boss_h": 12},
            {"width": 35, "depth": 35, "plate_t": 4, "boss_d": 10, "boss_h": 6},
            {"width": 50, "depth": 20, "plate_t": 8, "boss_d": 8, "boss_h": 10},
        ],
    },
    {
        "key": "G",
        "names": ["width", "depth", "plate_t", "boss_d", "boss_h", "boss_x", "boss_y"],
        "ranges": {
            "width": [40, 80],
            "depth": [28, 56],
            "plate_t": [4, 10],
            "boss_d": [8, 16],
            "boss_h": [4, 12],
            "boss_x": [-16, 16],
            "boss_y": [-10, 10],
        },
        "build": offset_boss,
        "observed": {
            "width": 52,
            "depth": 36,
            "plate_t": 5,
            "boss_d": 12,
            "boss_h": 8,
            "boss_x": 10,
            "boss_y": -6,
        },
        "heldout": [
            {"width": 70, "depth": 42, "plate_t": 6, "boss_d": 14, "boss_h": 10, "boss_x": 16, "boss_y": 8},
            {"width": 46, "depth": 32, "plate_t": 4, "boss_d": 10, "boss_h": 6, "boss_x": -12, "boss_y": 7},
            {"width": 58, "depth": 30, "plate_t": 7, "boss_d": 11, "boss_h": 9, "boss_x": 8, "boss_y": -8},
        ],
    },
    {
        "key": "H",
        "names": ["width", "depth", "height", "fillet_r"],
        "ranges": {
            "width": [20, 60],
            "depth": [16, 50],
            "height": [10, 28],
            "fillet_r": [0.8, 3.0],
        },
        "build": filleted_box,
        "observed": {"width": 32, "depth": 20, "height": 12, "fillet_r": 1.5},
        "heldout": [
            {"width": 48, "depth": 28, "height": 16, "fillet_r": 2.0},
            {"width": 24, "depth": 18, "height": 14, "fillet_r": 1.2},
            {"width": 40, "depth": 22, "height": 18, "fillet_r": 2.4},
        ],
    },
    {
        "key": "I",
        "names": ["width", "depth", "height", "chamfer"],
        "ranges": {
            "width": [20, 60],
            "depth": [16, 50],
            "height": [10, 28],
            "chamfer": [0.6, 2.4],
        },
        "build": chamfered_box,
        "observed": {"width": 30, "depth": 22, "height": 14, "chamfer": 1.2},
        "heldout": [
            {"width": 46, "depth": 26, "height": 16, "chamfer": 1.8},
            {"width": 24, "depth": 18, "height": 12, "chamfer": 0.8},
            {"width": 38, "depth": 20, "height": 18, "chamfer": 1.5},
        ],
    },
    {
        "key": "J",
        "names": ["width", "depth", "thick", "hole_d", "cbore_d", "cbore_h"],
        "ranges": {
            "width": [30, 80],
            "depth": [24, 60],
            "thick": [6, 14],
            "hole_d": [4, 10],
            "cbore_d": [8, 18],
            "cbore_h": [1.5, 4.0],
        },
        "build": counterbore,
        "observed": {
            "width": 48,
            "depth": 32,
            "thick": 8,
            "hole_d": 6,
            "cbore_d": 12,
            "cbore_h": 2.5,
        },
        "heldout": [
            {"width": 70, "depth": 40, "thick": 10, "hole_d": 8, "cbore_d": 16, "cbore_h": 3.0},
            {"width": 40, "depth": 28, "thick": 7, "hole_d": 5, "cbore_d": 10, "cbore_h": 2.0},
            {"width": 56, "depth": 36, "thick": 12, "hole_d": 7, "cbore_d": 14, "cbore_h": 3.5},
        ],
    },
    {
        "key": "K",
        "names": ["width", "depth", "thick", "slot_l", "slot_w"],
        "ranges": {
            "width": [40, 90],
            "depth": [24, 50],
            "thick": [4, 12],
            "slot_l": [16, 40],
            "slot_w": [4, 10],
        },
        "build": slotted_plate,
        "observed": {"width": 60, "depth": 32, "thick": 6, "slot_l": 24, "slot_w": 6},
        "heldout": [
            {"width": 80, "depth": 40, "thick": 8, "slot_l": 32, "slot_w": 8},
            {"width": 50, "depth": 28, "thick": 5, "slot_l": 20, "slot_w": 5},
            {"width": 70, "depth": 36, "thick": 7, "slot_l": 28, "slot_w": 7},
        ],
    },
    {
        "key": "L",
        "names": ["width", "depth", "thick", "hole_d", "pitch"],
        "ranges": {
            "width": [50, 100],
            "depth": [24, 50],
            "thick": [4, 12],
            "hole_d": [4, 10],
            "pitch": [16, 40],
        },
        "build": hole_pair,
        "observed": {"width": 64, "depth": 30, "thick": 6, "hole_d": 6, "pitch": 24},
        "heldout": [
            {"width": 88, "depth": 40, "thick": 8, "hole_d": 8, "pitch": 32},
            {"width": 56, "depth": 28, "thick": 5, "hole_d": 5, "pitch": 20},
            {"width": 76, "depth": 34, "thick": 7, "hole_d": 7, "pitch": 28},
        ],
    },
]

BUILDERS: dict[str, Callable[[dict], object]] = {f["key"]: f["build"] for f in FAMILIES}
