# program.md — research brief

Human-written. Read this. Do not edit it.

## Goal

Recover **design intent**, not one solid.

Each task gives you:

- `data/tasks/<id>/target.step` — one observed member of a parametric family
- `data/tasks/<id>/params.json` — the **names**, types, and ranges of the driving parameters. **Values are withheld.**

`solve(task_dir)` must return Python source that defines:

```python
def build(**params):
    # return a CadQuery solid
```

The immutable evaluator in `prepare.py` rebuilds the family at the observed parameter vector **and** at held-out vectors you never saw. The official score is the mean shape error over those members, then the mean over tasks.

```
intent_err  ∈ [0, 1]   lower is better
shape_err   = ½ · |Δvolume|/volume_gt  +  ½ · mean |Δextent|/extent_gt
```

A crash, timeout, or invalid solid scores 1.0 for that member. Same solver scored twice yields the same number.

Shape-matching the observed solid and ignoring parameters fails the held-out members. That is the point.

## Ownership

- Edit **only** `solver.py`.
- Write one line to `.hypothesis.txt` describing the change.
- Do not edit `prepare.py`, `program.md`, the log, or anything under `data/`.
- Do not read `data/hidden/` or `hidden_eval.py` — that is sealed ground truth.
- Do not leave the workspace or read `tests/`.
- Do not score yourself. The loop scores you and keeps or discards.
- No network, no LLM calls inside `solver.py`. Deterministic algorithms only.

## The loop (the harness runs this, not you)

You are invoked **once per generation**. Each invocation is one hypothesized change.

1. Read `program.md`, `solver.py`, and the tail of `results.tsv`.
2. Make one change to `solver.py`.
3. Stop.

The harness then:

4. Scores the new solver with the immutable evaluator.
5. If `intent_err` is strictly lower, **keep** (git commit).
6. If it is equal, worse, or the file crashes, **discard** (`git checkout -- solver.py`).
7. Appends one row to `results.tsv` (`keep` / `discard` / `crash`).
8. Invokes you again. The next start is the last **accepted** solver plus the full log.

Rejected edits are not the next start. The cloud of discards is the honest part of the log.

## Promising directions

The baseline emits the observed bounding box and ignores parameters. It is mediocre on purpose.

1. Bind parameter names to the dimensions they name. A `width` that does not drive width is not intent.
2. Use topology on the observed solid (planes, cylinders, through-holes, bosses) to choose a builder, then let **parameters** drive it.
3. Prefer a short `build()` that regenerates. A soup of observed numbers will not survive held-out vectors.
4. One change per generation. Read the log: do not retry a discarded idea verbatim; combine near-misses.

## Do not

- Hard-code the observed solid.
- Voxel- or box-soup the target.
- Put every family you can imagine in dormant `if` branches you are not ready to score — add one hypothesis at a time.
- Read hidden specs or edit the evaluator.
