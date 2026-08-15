"""Sealed family builders and member vectors.

The agent workspace does not include this file. prepare.py imports it to
generate tasks and to rebuild ground-truth solids at held-out parameters.
"""

from __future__ import annotations

from typing import Callable


def _cq():
    import cadquery as cq

    return cq


def box(p: dict) -> object:
    return _cq().Workplane("XY").box(p["width"], p["depth"], p["height"])


def plate_hole(p: dict) -> object:
    return (
        _cq()
        .Workplane("XY")
        .box(p["width"], p["depth"], p["thick"])
        .faces(">Z")
        .workplane()
        .hole(p["hole_d"])
    )


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


# Keys are opaque letters. They never appear in task directory names.
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
]

BUILDERS: dict[str, Callable[[dict], object]] = {f["key"]: f["build"] for f in FAMILIES}
