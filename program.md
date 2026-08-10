# program.md — research directions for autoregen

**Human-written.** The agent may read this file. The agent may **not** edit it
(enforced by `loop.sh` ownership rules). In Phase 3 an outer loop may edit it;
for v0 it is frozen.

## Goal

Minimize mean `intent_err` on the sealed-from-solver `dev` split. Lower is better.
`intent_err = 0.35·shape + 0.45·gen + 0.15·robust + 0.05·parsimony`.

Generalization (`gen_err` on held-out parameter vectors) outweighs shape match on
the observed member. Recover **design intent**, not a single solid.

## Ownership rules (mechanical)

1. Edit **only** `solver.py`. Any other path → violation, revert, log.
2. Do not read `data/gt/`, `prepare.py` internals, or sealed test splits for training signal.
3. Do not use network I/O inside `solver.py` or emitted `build()` modules.
4. `HARNESS.sha256` is re-verified every generation. Mismatch → hard stop.

## Solver contract

```python
def solve(task_dir: str) -> str:
    """Return Python source of a module defining build(**params) -> solid."""
```

Inputs in `task_dir`:

- `target.step` — observed B-rep solid
- `params.json` — parameter **names**, types, units, ranges (values withheld)
- `budget.json` — wall-clock / token budget
- `views/*.png` — optional orthographic renders

Emitted module must expose `build(...)` with keyword args matching `params.json`
names, returning a CadQuery workplane/solid. Prefer CadQuery (OpenCascade).

## Constraints

- **Deterministic at v0.** No LLM calls at inference time. Fixed seeds, pure algorithms.
- Per-member build timeout: 20s. Per-task solve timeout: 90s.
- Prefer single-body manifold solids with parsimonious face counts.
- Wrap risky reconstruction in try/except with a parametric bbox fallback so
  crashes become shape error, not hard zeros.

## Promising research directions (priority order)

1. **Better topology → feature mapping**
   - Cylinder-axis clustering for hole patterns (linear / polar).
   - Parallel-plane pairing for extrude direction and thickness.
   - Fillet/chamfer radius from blend-face curvature, not thickness heuristics.

2. **Constraint / dependency inference**
   - Detect `fillet_r < plate_t/2`, `hole_d < min(w,h)`, pattern pitch feasibility.
   - Emit clamps in `build()` so robustness sweep passes.

3. **Template library expansion**
   - Add shells, counterbores, ribs, bosses, lofts as first-class templates.
   - Score templates by residual face-type histogram match before emitting.

4. **Parameter binding**
   - Fuzzy name match is weak. Bind by unit + range + feature magnitude.
   - Solve a small assignment problem: params ↔ inferred dimensions.

5. **Multi-hypothesis search (within budget)**
   - Emit K candidate programs, score cheap proxies (volume, face count, bbox)
     against the observed solid, keep the best — still no GT access.

6. **Do not**
   - Voxel-soup or mesh-soup the observed solid (fails held-out + parsimony).
   - Hardcode observed geometry ignoring parameters (gen_err ≈ 1).
   - Read ground truth or edit the harness.

## Metric notes

- Observed shape match is table stakes; held-out members are the signal.
- `robust_err` measures authoring quality under ±15% param noise.
- `parsimony_pen` punishes face explosion (brute-force CSG soup).

## Logging

Every generation appends one row to `results.tsv`. Write a one-line hypothesis
describing the change. Rejected experiments stay in the log — the cloud of
rejects is the honest part of the chart.
