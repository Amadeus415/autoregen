"""Local researcher used to prove the ratchet without a model.

Each call applies one hypothesized edit to solver.py. Improvements are
one CAD capability at a time so the hill has many rungs. Junk steps
exist so discard/crash still appear. This file is not the research surface.
"""

from __future__ import annotations

from pathlib import Path


def render_solver(features: set[str]) -> str:
    lines = [
        'from pathlib import Path',
        'import json',
        '',
        '',
        'def solve(task_dir: str) -> str:',
        '    import cadquery as cq',
        '',
        '    task = Path(task_dir)',
        '    names = json.loads((task / "params.json").read_text())["names"]',
        '    args = ", ".join(names)',
        '    named = set(names)',
        '    wp = cq.importers.importStep(str(task / "target.step"))',
        '    bb = wp.val().BoundingBox()',
        '    dx, dy, dz = bb.xlen, bb.ylen, bb.zlen',
        '    body = f"return cq.Workplane(\'XY\').box({dx:.6f}, {dy:.6f}, {dz:.6f})"',
    ]
    if "bind" in features:
        lines += [
            '    if {"width", "depth", "height"} <= named:',
            '        body = "return cq.Workplane(\'XY\').box(width, depth, height)"',
            '    elif {"width", "depth", "thick"} <= named:',
            '        body = "return cq.Workplane(\'XY\').box(width, depth, thick)"',
            '    elif {"width", "depth", "plate_t"} <= named:',
            '        body = "return cq.Workplane(\'XY\').box(width, depth, plate_t)"',
        ]
    if "cyl" in features:
        lines += [
            '    if {"radius", "height"} <= named:',
            '        body = "return cq.Workplane(\'XY\').circle(radius).extrude(height)"',
        ]
    if "tube" in features:
        lines += [
            '    if {"outer_r", "inner_r", "height"} <= named:',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').circle(outer_r)"',
            '            ".circle(inner_r).extrude(height))"',
            '        )',
        ]
    if "hole" in features:
        lines += [
            '    if ({"width", "depth", "thick", "hole_d"} <= named',
            '            and "hole_x" not in named and "cbore_d" not in named',
            '            and "pitch" not in named):',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').box(width, depth, thick)"',
            '            ".faces(\'>Z\').workplane().hole(hole_d))"',
            '        )',
        ]
    if "hole_xy" in features:
        lines += [
            '    if {"width", "depth", "thick", "hole_d", "hole_x", "hole_y"} <= named:',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').box(width, depth, thick)"',
            '            ".faces(\'>Z\').workplane().center(hole_x, hole_y).hole(hole_d))"',
            '        )',
        ]
    if "boss" in features:
        lines += [
            '    if ({"width", "depth", "plate_t", "boss_d", "boss_h"} <= named',
            '            and "boss_x" not in named):',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').box(width, depth, plate_t)"',
            '            ".faces(\'>Z\').workplane().circle(boss_d / 2).extrude(boss_h))"',
            '        )',
        ]
    if "boss_xy" in features:
        lines += [
            '    if {"width", "depth", "plate_t", "boss_d", "boss_h", "boss_x", "boss_y"} <= named:',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').box(width, depth, plate_t)"',
            '            ".faces(\'>Z\').workplane().center(boss_x, boss_y)"',
            '            ".circle(boss_d / 2).extrude(boss_h))"',
            '        )',
        ]
    if "fillet" in features:
        lines += [
            '    if {"width", "depth", "height", "fillet_r"} <= named:',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').box(width, depth, height)"',
            '            ".edges().fillet(fillet_r))"',
            '        )',
        ]
    if "chamfer" in features:
        lines += [
            '    if {"width", "depth", "height", "chamfer"} <= named:',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').box(width, depth, height)"',
            '            ".edges(\'>Z\').chamfer(chamfer))"',
            '        )',
        ]
    if "cbore" in features:
        lines += [
            '    if {"width", "depth", "thick", "hole_d", "cbore_d", "cbore_h"} <= named:',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').box(width, depth, thick)"',
            '            ".faces(\'>Z\').workplane()"',
            '            ".cboreHole(hole_d, cbore_d, cbore_h))"',
            '        )',
        ]
    if "slot" in features:
        lines += [
            '    if {"width", "depth", "thick", "slot_l", "slot_w"} <= named:',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').box(width, depth, thick)"',
            '            ".faces(\'>Z\').workplane().slot2D(slot_l, slot_w).cutThruAll())"',
            '        )',
        ]
    if "pitch" in features:
        lines += [
            '    if {"width", "depth", "thick", "hole_d", "pitch"} <= named:',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').box(width, depth, thick)"',
            '            ".faces(\'>Z\').workplane()"',
            '            ".pushPoints([(-pitch / 2, 0), (pitch / 2, 0)]).hole(hole_d))"',
            '        )',
        ]
    if "unit" in features:
        lines += [
            '    body = "return cq.Workplane(\'XY\').box(1, 1, 1)"',
        ]
    lines += [
        '    return (',
        '        "import cadquery as cq\\n\\n"',
        '        f"def build({args}):\\n"',
        '        f"    {body}\\n"',
        '    )',
        '',
    ]
    return "\n".join(lines) + "\n"


def _comment(src: str) -> str:
    return src.rstrip() + "\n\n# hypothesis-only comment; no behavior change\n"


def _break_solve(src: str) -> str:
    return src.replace("def solve", "def solv", 1)


# One capability per keep. Order is the intended staircase.
_KEEP_STEPS = [
    ({"bind"}, "bind width/depth/height/thick to the box"),
    ({"bind", "cyl"}, "emit a cylinder when radius is present"),
    ({"bind", "cyl", "tube"}, "emit a tube when inner_r and outer_r are present"),
    ({"bind", "cyl", "tube", "hole"}, "cut a centered through-hole when hole_d is present"),
    (
        {"bind", "cyl", "tube", "hole", "hole_xy"},
        "offset the hole when hole_x and hole_y are present",
    ),
    (
        {"bind", "cyl", "tube", "hole", "hole_xy", "boss"},
        "emit a centered boss when boss_d and boss_h are present",
    ),
    (
        {"bind", "cyl", "tube", "hole", "hole_xy", "boss", "boss_xy"},
        "offset the boss when boss_x and boss_y are present",
    ),
    (
        {"bind", "cyl", "tube", "hole", "hole_xy", "boss", "boss_xy", "fillet"},
        "fillet all edges when fillet_r is present",
    ),
    (
        {
            "bind",
            "cyl",
            "tube",
            "hole",
            "hole_xy",
            "boss",
            "boss_xy",
            "fillet",
            "chamfer",
        },
        "chamfer the top edges when chamfer is present",
    ),
    (
        {
            "bind",
            "cyl",
            "tube",
            "hole",
            "hole_xy",
            "boss",
            "boss_xy",
            "fillet",
            "chamfer",
            "cbore",
        },
        "cut a counterbore when cbore_d and cbore_h are present",
    ),
    (
        {
            "bind",
            "cyl",
            "tube",
            "hole",
            "hole_xy",
            "boss",
            "boss_xy",
            "fillet",
            "chamfer",
            "cbore",
            "slot",
        },
        "cut a through-slot when slot_l and slot_w are present",
    ),
    (
        {
            "bind",
            "cyl",
            "tube",
            "hole",
            "hole_xy",
            "boss",
            "boss_xy",
            "fillet",
            "chamfer",
            "cbore",
            "slot",
            "pitch",
        },
        "cut a two-hole pattern when pitch is present",
    ),
]


def _proposals():
    ideas = []
    for feats, hyp in _KEEP_STEPS:
        ideas.append((lambda src, f=feats: render_solver(f), hyp))
        if len(ideas) == 2:
            ideas.append((_comment, "add a comment, no behavior change"))
        if len(ideas) == 6:
            ideas.append((_break_solve, "rename solve so the module no longer exports it"))
        if len(ideas) == 11:
            ideas.append(
                (lambda src: render_solver({"unit"}), "always emit a unit cube")
            )
    return ideas


class DummyAgent:
    def __init__(self) -> None:
        self.step = 0
        self._ideas = _proposals()

    def propose(self, root: Path) -> str:
        if self.step >= len(self._ideas):
            raise RuntimeError("dummy agent is out of hypotheses")
        apply, hypothesis = self._ideas[self.step]
        self.step += 1
        solver = root / "solver.py"
        solver.write_text(apply(solver.read_text()))
        (root / ".hypothesis.txt").write_text(hypothesis + "\n")
        return hypothesis
