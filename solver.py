"""solver.py — the only file the agent edits.

Given a task directory (observed solid + parameter names, values withheld),
return Python source that defines build(**params) -> solid.

Baseline: emit the observed bounding box and ignore parameters.
Deterministic. No network.
"""

from __future__ import annotations

import json
from pathlib import Path


def solve(task_dir: str) -> str:
    import cadquery as cq

    task = Path(task_dir)
    names = json.loads((task / "params.json").read_text())["names"]
    args = ", ".join(names)
    wp = cq.importers.importStep(str(task / "target.step"))
    bb = wp.val().BoundingBox()
    dx, dy, dz = bb.xlen, bb.ylen, bb.zlen
    return (
        "import cadquery as cq\n\n"
        f"def build({args}):\n"
        f"    return cq.Workplane('XY').box({dx:.6f}, {dy:.6f}, {dz:.6f})\n"
    )
