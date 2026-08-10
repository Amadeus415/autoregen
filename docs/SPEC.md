# autoregen — an autoresearch-style recursive improvement loop for parametric CAD

**Status:** design spec, v0.1  
**Analogue:** `karpathy/autoresearch`, with `val_bpb` replaced by a geometric/parametric error metric and `train.py` replaced by `solver.py`.

---

## 0. Naming note (read first)

Don't ship this as "AutoCAD." That's an Autodesk trademark and it's your employer's flagship product — a public repo under that name is the one avoidable mistake in this project. Suggested names, in order of preference:

- **`autoregen`** — double meaning: CAD *regeneration* (the thing that breaks when a parametric model is badly authored) and *autoregressive*. Clean, available-sounding, no collision.
- `autoextrude`
- `intent-ratchet` / `regenbench`

The rest of this doc uses `autoregen`.

---

## 1. Why CAD is the right domain for this

Karpathy's loop works because of four properties, not because of anything about LLM training specifically:

1. The metric is a **single scalar, lower-is-better** (`val_bpb`).
2. The metric is **cheap** — a fixed 5-minute wall-clock budget, ~12 experiments/hour, ~100 overnight.
3. The metric is **immutable** — `prepare.py` is off-limits to the agent.
4. The ratchet is **git** — commit if better, `git reset` if not.

Parametric CAD satisfies all four better than almost any other engineering domain, because *correctness is machine-checkable without a human and without a learned reward model*. A solid either regenerates or it doesn't. Volumes, mass properties, face counts, and boolean intersections are exact. You get a ground-truth-verifiable RL-style signal for free, which is exactly the property that makes a domain a good substrate for a self-improving loop.

The existing CAD benchmarks (CADGenBench, Text2CAD-Bench, BenchCAD, CADPrompt) all measure *shape match on a fixed test set* — one-shot leaderboard evals where the top score currently sits around 0.39 on CADGenBench. None of them are a **loop**. `autoregen`'s contribution isn't a new dataset; it's a self-improving harness plus a metric that measures something the shape-match benchmarks miss.

---

## 2. The task: design intent recovery, not shape matching

**Input to the solver, per task:**

| Field | Content |
|---|---|
| `target.step` | A B-rep solid (one member of a parametric family) |
| `views/*.png` | Four canonical orthographic renders (optional, for VLM solvers) |
| `params.json` | The **names** of the family's driving parameters and their units — e.g. `["plate_t", "hole_d", "fillet_r", "rib_count"]`. **Values are withheld.** |
| `budget.json` | Hard per-task wall-clock and token budget |

**Required output:**

A single Python module exposing:

```python
def build(plate_t: float, hole_d: float, fillet_r: float, rib_count: int) -> Solid: ...
```

built on CadQuery or build123d (OpenCascade kernel either way).

**How it's scored:** the harness knows the ground-truth family program. It evaluates the submitted `build()` at the *observed* parameter vector, and at **K = 4 held-out parameter vectors** the solver never saw. Shape match on the observed member is table stakes. Shape match on the four unseen members is the actual signal — that only happens if the solver recovered the *intent* (this is a hole through a plate whose diameter drives the fillet's validity) rather than fitting a shape.

This is the design decision that makes the whole project interesting. It kills the degenerate strategies:

- **Voxel soup** (union 40,000 tiny boxes to maximize IoU) fails the held-out members and blows the topology budget.
- **Hardcoding** the observed solid and ignoring arguments scores ~0.25 (one of five members correct) and is trivially detectable.
- **Overfit feature trees** that break on regeneration fail the robustness term.

---

## 3. The metric: `intent_err` ∈ [0, 1], lower is better

Per task *t*, over member set *M* = {observed} ∪ {4 held-out}:

```
intent_err(t) = w_s · shape_err + w_g · gen_err + w_r · robust_err + w_p · parsimony_pen
```

with weights `w = (0.35, 0.45, 0.15, 0.05)` at v0 — note generalization outweighs shape match.

**`shape_err`** — on the observed member: `1 − IoU_voxel` blended 50/50 with `clamp(CD_normalized / τ, 0, 1)`. Voxel resolution 128³ on dev, 256³ on test. Chamfer distance from 30k uniformly sampled surface points after normalizing to a unit bounding box. Where OCC booleans succeed, also compute exact volumetric IoU as `vol(A ∩ B) / vol(A ∪ B)` and use it in preference to the voxel approximation.

**`gen_err`** — mean `shape_err` across the four held-out members. Any member whose `build()` throws, times out, or produces a non-manifold / zero-volume result scores 1.0 for that member. No partial credit for a crash.

**`robust_err`** — fraction of a 12-point Latin-hypercube perturbation sweep (±15% on continuous params, ±1 on integer params, clipped to declared ranges) that fails to produce a valid single-body solid. This is the term that measures *authoring quality*, and it's the one no existing benchmark scores. A model that only regenerates at the exact parameters it was fit to is a bad model, and every practicing CAD user knows it.

**`parsimony_pen`** — `clamp((faces_pred / faces_gt − 1) / 4, 0, 1)`. Cheap anti-brute-force guard. Do not skip this.

**Validity gate:** if the module fails to import, exceeds its 20s per-member timeout, attempts network access, or attempts to read anything under `data/gt/`, `intent_err(t) = 1.0` and the task is flagged.

**Headline number:** `intent_err = mean over dev tasks`. One scalar. Lower is better. This is your `val_bpb`.

---

## 4. Task generation: synthesize the data, don't scrape it

Scarcity and leakage kill benchmarks. Generate the families procedurally so you have infinite tasks, provable non-leakage, and no licensing questions.

**Grammar** (`prepare.py`, immutable):

- **L1 — sketch + one feature:** extrude, revolve, simple through-holes. 2–4 params.
- **L2 — multi-feature:** pockets, counterbores, chamfers, fillets, linear/polar patterns, shells, draft. 4–7 params, one inter-parameter dependency (e.g. `fillet_r < plate_t / 2`).
- **L3 — assembly-adjacent:** ribs, bosses, mating interfaces with clearance constraints, swept profiles, non-trivial fillet ordering where the wrong order changes the result. 6–10 params, ≥2 dependencies.

Every generated family is validated before admission: all 5 members must regenerate, be single-body manifold solids, have non-degenerate volume, and be pairwise distinct (min IoU between members < 0.9, so the held-out members are actually different shapes).

**Splits:**

| Split | Size | Who sees it |
|---|---|---|
| `train` | 512 | Agent may read tasks *and* GT programs. For studying patterns. |
| `dev` | 64 | Agent sees inputs and its own score. GT programs sealed. Drives the ratchet. |
| `test` | 256 | Sealed. Human runs it every 25 generations. |
| `test-ood` | 128 | Sealed, and uses **grammar productions absent from train/dev** — different feature verbs entirely. |

`test-ood` is the honesty check. If dev drops and `test-ood` doesn't, the agent found harness quirks, not CAD competence.

Optionally add a small real-parts slice (ABC dataset / Fusion 360 Gallery) as `test-real` for external validity, but keep it out of the loop.

---

## 5. Repo layout

Mirror autoresearch's discipline: three files that matter, tight ownership rules.

```
autoregen/
├── prepare.py        # IMMUTABLE. Family generator, splits, scorer, sandbox, results logging.
├── solver.py         # THE ONLY FILE THE AGENT EDITS. Task in → build() module out.
├── program.md        # HUMAN-WRITTEN. Research directions, constraints, what's in scope.
├── results.tsv       # Append-only: gen, sha, intent_err, per-term breakdown, wall_s, tokens, usd, note
├── loop.sh           # The ratchet driver
├── data/
│   ├── families/     # generated task families, seeded
│   └── gt/           # sealed ground truth. chmod 000 to the solver's sandbox user.
├── HARNESS.sha256    # checksum of prepare.py + data/gt, verified every generation
└── plots/make_chart.py
```

**Ownership rules, stated in `program.md` and enforced mechanically:**

- Agent may edit `solver.py` and nothing else. `loop.sh` verifies `git diff --name-only` touches only that path; any other change → revert and log a violation.
- `HARNESS.sha256` re-verified at the start of every generation. Mismatch → hard stop, alert the human.
- Solver executes as an unprivileged user in a subprocess: no network, read-only filesystem except a scratch dir, no access to `data/gt/`, `data/*/test*`, or `prepare.py`'s internals.
- Violations are recorded in `results.tsv` and never silently discarded. The violation log is itself an interesting artifact — reward hacking attempts are worth a section in your README.

---

## 6. The loop

```
1. Verify HARNESS.sha256. Abort on mismatch.
2. Agent reads program.md, solver.py, and the tail of results.tsv (last ~40 rows).
3. Agent proposes and implements ONE change to solver.py. Writes a one-line hypothesis.
4. git commit on a branch.
5. Run dev eval: 64 tasks × 5 members, 16 parallel workers.
   Hard cap: 4 minutes wall clock. Timeout → treat as failure, revert.
6. Statistical gate (see below).
7. Improved → keep the commit. Not improved → git reset --hard. Either way, append to results.tsv.
8. Goto 2. Loop forever, no /commands, no human.
```

**Throughput target:** ~90s per dev eval at 16 workers → **20–30 experiments/hour**, ~200 overnight. Notably faster than autoresearch's 12/hr, because geometry is cheaper than gradient descent.

**The statistical gate — this is where naive implementations go wrong.** If any part of `solver.py` calls an LLM at inference time, your dev score is a noisy random variable and a plain `if new < best` comparison manufactures a fake ratchet out of nothing but variance. Mitigations, all of them:

- Pin the inference model, `temperature=0`, fixed seed.
- Cache LLM responses keyed on `sha256(prompt)`, so re-scoring an unchanged solver is free and deterministic.
- Accept a change only if it wins on a **paired per-task comparison** — bootstrap the mean difference over the 64 dev tasks, require the 95% CI to exclude zero. Paired, not unpaired: task difficulty variance is huge and dwarfs the effect size.
- Log the noise floor: every 20 generations, re-run the current best unchanged and record the spread. Put that band on the chart as a shaded region. A published loop without a stated noise floor isn't credible.

**Strongly recommended for v0:** make the solver **fully deterministic — no LLM at inference time.** The agent writes *algorithms* (feature inference from B-rep topology, cylinder-axis clustering to find hole patterns, fillet-radius estimation from edge curvature, constraint-dependency inference, parameter-to-feature binding) rather than *prompts*. This gives you a clean signal, a fast loop, a chart with almost no noise, and a result that's a genuine algorithmic contribution rather than prompt tuning. Add an LLM-in-the-solver arm later as a labeled variant.

---

## 7. The chart

Karpathy's chart is one dot per experiment plus a descending frontier. Match that, then add the parts that make it a benchmark rather than a demo:

- **X axis:** generation index (secondary axis: cumulative wall-clock hours, and cumulative USD).
- **Y axis:** `intent_err`, lower is better. Log-ish scale if it collapses fast.
- **Grey dots:** every experiment, including failures (plot rejects at their measured value — the cloud of rejects is the honest part).
- **Bold step line:** best-so-far dev. The ratchet.
- **Shaded band:** measured noise floor around the current best.
- **Red markers, every 25 gens:** sealed `test` score.
- **Orange markers:** sealed `test-ood` score.
- **Stacked area beneath, optional:** contribution of each of the four error terms to the current best, so you can see *what* is improving. This is the panel people will actually screenshot.

The story the chart tells: dev drops fast, `test` tracks it with a gap, `test-ood` lags — and the interesting research question is whether a better `program.md` closes the OOD gap. That's a much better narrative than a single descending line.

---

## 8. Baseline (gen 0)

Ship a deliberately mediocre but non-trivial baseline so the chart has somewhere to go. Target `intent_err ≈ 0.55–0.70`:

- Parse `target.step` with OCC. Extract topology: faces by surface type, cylinder axes and radii, planar face normals, bounding box.
- Heuristics: largest pair of parallel planes → base extrude with thickness param; coaxial cylinder groups → hole features; small-radius toroidal/blend faces → fillets.
- Bind declared parameter names to inferred features by fuzzy name match (`hole_d` → cylinder diameter, `*_t`/`*_thick` → extrude depth, `*_r`/`fillet*` → blend radius, `*_count`/`n_*` → pattern instance count).
- Emit a build123d program. Wrap everything in try/except with a bounding-box fallback so a crash costs `shape_err` rather than a hard zero.

If gen-0 scores below ~0.3, the tasks are too easy — turn up the L3 fraction. Above ~0.85 and the loop has no gradient to climb.

---

## 9. Build phases

**Phase 1 — the harness (≈1 week).** Generator for L1/L2, scorer, sandbox, splits, `results.tsv`, chart script, baseline solver. Deliverable: reproducible gen-0 number and an empty chart. **Do not start the loop until you can re-run gen 0 twice and get the same number.** Determinism first.

**Phase 2 — the loop (≈3 days + overnight runs).** `program.md`, `loop.sh`, the ratchet, statistical gate, violation logging. Deliverable: the first 200-generation overnight run and a real chart. This is the tweetable artifact.

**Phase 3 — the recursive part (the actual research).** Karpathy left the human in charge of `program.md`. Close that loop:

- **Inner loop:** agent edits `solver.py`, scored on `intent_err`.
- **Outer loop:** a second agent edits `program.md`, scored on **`Δintent_err` per wall-clock hour achieved by an N=40-generation inner run**, on a fresh dev resample each time.

This is genuinely recursive — the system is improving the thing that improves the thing. It's also where the failure modes get interesting (outer loop learns to write a `program.md` that games the inner metric; outer-loop evaluation is brutally expensive at ~2 hours per data point; and the outer signal is far noisier than the inner one). Budget for a mostly-negative result and write it up honestly. Even a null result here is a better blog post than another descending line.

**Phase 4 — make it a community benchmark.** L3 families, `test-real` slice, `autoregen submit` producing a signed run manifest (harness checksum, model, cost, seeds, full `results.tsv`), a leaderboard ranked on sealed `test-ood`, and a "researcher arm" comparison — same `program.md`, different driving models — which turns the repo into a live eval of *which model is the better autonomous engineer*. That comparison is what people actually came for.

---

## 10. Known risks

| Risk | Mitigation |
|---|---|
| Reward hacking (voxel soup, GT reads, harness edits) | Parsimony term, sealed GT with filesystem enforcement, checksums, one-file diff enforcement, published violation log |
| Noise mistaken for progress | Paired bootstrap gate, deterministic solver at v0, published noise floor |
| Dev overfitting | Sealed `test` every 25 gens, `test-ood` with disjoint grammar productions |
| OCC boolean failures corrupting scores | Voxel IoU as primary, exact boolean as secondary-when-available, never let a kernel failure silently score as 0 error |
| Loop plateaus after ~30 gens | Expected — the ratchet can't take a step back. Add an archive/tree-search mode that reopens abandoned branches |
| Synthetic tasks don't transfer | `test-real` slice from public parts as a stated external-validity check, reported separately and never in the loop |
| Cost runaway | Per-generation USD ceiling in `loop.sh`, hard stop, cost logged as a first-class column |

---

## 11. What "done" looks like

A repo where a stranger runs `./loop.sh` overnight on a laptop and wakes up to: a git history of validated improvements, a `results.tsv` they can plot, a chart with dev / test / OOD lines and a stated noise floor, and a sealed-set number they can put on a leaderboard. Plus a README that's honest about which improvements were real, which were noise, and which were the agent trying to cheat.

The last part is what will make it circulate.
