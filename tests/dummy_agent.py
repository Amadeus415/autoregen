"""Local researcher used to prove the ratchet without a model.

Each call applies one hypothesized edit to solver.py. Improvements are
incremental CAD capabilities; the junk steps exist so keep/discard/crash
all appear. This file is not part of the research surface.
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
    if "hole" in features:
        lines += [
            '    if {"width", "depth", "thick", "hole_d"} <= named:',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').box(width, depth, thick)"',
            '            ".faces(\'>Z\').workplane().hole(hole_d))"',
            '        )',
        ]
    if "tube" in features:
        lines += [
            '    if {"outer_r", "inner_r", "height"} <= named:',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').circle(outer_r)"',
            '            ".circle(inner_r).extrude(height))"',
            '        )',
        ]
    if "boss" in features:
        lines += [
            '    if {"width", "depth", "plate_t", "boss_d", "boss_h"} <= named:',
            '        body = (',
            '            "return (cq.Workplane(\'XY\').box(width, depth, plate_t)"',
            '            ".faces(\'>Z\').workplane().circle(boss_d / 2).extrude(boss_h))"',
            '        )',
        ]
    if "swap" in features:
        lines += [
            '    if {"width", "depth", "height"} <= named:',
            '        body = "return cq.Workplane(\'XY\').box(height, width, depth)"',
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


def _whitespace(src: str) -> str:
    return src.rstrip() + "\n\n\n"


def _break_solve(src: str) -> str:
    return src.replace("def solve", "def solv", 1)


def _proposals():
    return [
        (lambda src: render_solver({"bind"}), "bind width/depth/height/thick to the box"),
        (_comment, "add a comment, no behavior change"),
        (lambda src: render_solver({"bind", "cyl"}), "emit a cylinder when radius is present"),
        (lambda src: render_solver({"unit"}), "always emit a unit cube"),
        (
            lambda src: render_solver({"bind", "cyl", "hole"}),
            "cut a through-hole when hole_d is present",
        ),
        (_break_solve, "rename solve so the module no longer exports it"),
        (
            lambda src: render_solver({"bind", "cyl", "hole", "tube"}),
            "emit a tube when inner_r and outer_r are present",
        ),
        (_whitespace, "add trailing whitespace"),
        (
            lambda src: render_solver({"bind", "cyl", "hole", "tube", "boss"}),
            "emit a boss when boss_d and boss_h are present",
        ),
        (lambda src: render_solver({"bind"}), "drop later features and keep only box binding"),
    ]


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
