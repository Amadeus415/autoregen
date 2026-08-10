# autoregen v0.3 — remediation plan

Handoff spec. Goal: turn `autoregen` from a mechanism demo into a benchmark that
credibly measures **recursive agent improvement on parametric CAD inference**.

North star (unchanged):

> Under a fixed research budget, how much can an agent improve a deterministic
> system that converts a STEP solid into a parametric CAD program that
> regenerates correctly on unseen parameter values and unseen part families?

---

## 0. Confirmed diagnosis

These are verified against the repo, not conjecture. Do not re-litigate them;
they are the premises for the work below.

1. **The baseline shipped the answers.** Commit `f88a29c` (`solver.py`,
   `_emit_template`) already contained full emit bodies for `pattern`,
   `pocket`, `shell`, `ribbed`, and `boss`. Dispatch was disabled by an
   `if/elif` chain with a comment naming it "the loop's job"
   (`solver.py:389-411`). All four accepted generations in `results.tsv`
   (gens 1, 2, 6, 12) are `enable_*_template` commits. The 68–75% headline
   improvement is agents flipping switches on pre-written code.

2. **The task labels leak the answer.** `harness/generator.py:846` builds
   `family_id = f"{spec.grammar}_{fam_seed:08x}"`, producing agent-visible
   directory names like `data/families/dev/l3_ribbed_plate_6fb59ea3` next to a
   solver containing `elif template == "ribbed"`. This is the mechanism behind
   the one-generation discovery and immediate plateau, and it must be fixed
   even after the dormant code is removed.

3. **Two of five metric terms are inert.** `robust_err` and `parsimony_pen`
   are `0.000000` in all 13 rows of `results.tsv`. With `W_ROBUST=0.15` and
   `W_PARSIMONY=0.05` (`harness/scorer.py:19-22`), `intent_err` is effectively
   `0.35·shape_err + 0.45·gen_err`. `robust_err` only counts build failures
   (`harness/scorer.py:229-245`), so a consistently wrong solid scores 0.

4. **The OOD result is one family.** Both `data/families/test-ood` tasks are
   `ood_helix_cut` (two seeds). Grok's `0.744` OOD figure is a single-family
   observation, not a transfer measurement.

5. **Cost accounting is not wired.** `loop.sh:557-558` writes `"tokens": 0`
   and `"usd": 0.0` unconditionally. `USD_CEILING` (`loop.sh:21`) therefore
   never binds.

6. **Sealed-test results are written where a later turn can read them.**
   The gen%25 checkpoint at `loop.sh:565-577` calls `prepare.py eval --split
   test --append-tsv`, appending hidden scores to `results.tsv` inside the
   agent's own workspace.

---

## Phase 1 — The falsification experiment (do this first, alone)

**Do not build anything else until Phase 1 reports.** It costs roughly an
afternoon and it determines whether the rest of the plan is worth executing.

### 1.1 Strip the baseline

Create branch `v0.3-honest-baseline` from `f88a29c`.

In `solver.py`, delete the `_emit_template` bodies for `pattern`, `pocket`,
`shell`, `ribbed`, and `boss`, and remove their dispatch branches. Keep only
`plate`, `plate_hole`, `plate_hole_fillet`, `cylinder`, `slot`. Remove the
comments at `solver.py:389-393` that name the missing families — they are a
hint sheet.

Everything unreachable after this deletion goes too: the `find_role` lookups
for `rib_h`, `rib_t`, `boss_d`, `boss_h`, `pocket_d`, `cbore_d`, `wall_t`
should only remain if a surviving template consumes them.

Acceptance: `grep -ciE 'rib|boss|shell|pocket|counterbore' solver.py` returns 0.

### 1.2 Anonymize task identity

`harness/generator.py:846` — replace with a content-independent id:

```python
family_id = f"fam_{fam_seed:08x}"
```

Keep `spec.grammar` in the **sealed GT metadata only** (`data/gt/<split>/...`),
never in `data/families/`. Audit every file written by `write_family`
(`generator.py:693-780`) and strip `grammar`, `family_id`-derived names, and
any level marker (`L1`/`L2`/`L3`) from the agent-visible side. Regenerate all
splits after this change; the old directories are contaminated.

Acceptance: `grep -rlE 'l1_|l2_|l3_|ribbed|boss|helix' data/families/` returns
nothing.

### 1.3 Re-measure

Re-run `benchmark_models.py` with the same two arms, same `--generations 3`,
against the stripped baseline. Record the new baseline `intent_err`.

### 1.4 Report before proceeding

Report, and stop:

- New baseline `intent_err` (expect materially worse than `0.405`).
- Per-arm improvement over 3 generations.
- **The diffs of any accepted generation, quoted in full.** This is the actual
  deliverable. The question is not "did the number move" but "did the agent
  write a rib-recovery heuristic, or did it find another shortcut."

If no arm produces a nontrivial accepted improvement, say so plainly. That is
a real and publishable finding about task difficulty, and it changes Phase 3's
design. Do not paper over it by loosening the acceptance gate.

---

## Phase 2 — Make the metric measure the right thing

Independent of Phase 1's outcome; can proceed in parallel.

### 2.1 Rename `intent_err` → `regen_err`

Mechanical, but do it now while the results file is small. Update
`harness/scorer.py`, `harness/eval.py`, `loop.sh`, `benchmark_models.py`,
`plots/make_chart.py`, `results.tsv` header, `README.md`. Keep a
`results-v0.2.tsv` copy of the old data under its old column names.

### 2.2 Replace `robust_err` with a parameter-sensitivity term

The current term (`harness/scorer.py:229-245`) asks only "did the build
survive." Replace with: for each parameter `p`, perturb `p` alone across its
range holding others fixed, and compare the *response* of the predicted solid
against GT's response on the same perturbations. Response vector per
parameter: Δvolume, Δbbox (x,y,z), Δface-count, Δhole-count. Score as
normalized disagreement between predicted and GT response vectors.

This is the term that distinguishes "the hole diameter parameter controls the
hole" from "the geometry happens to look right at the observed point."

Keep the build-failure count as a separate, smaller `regen_fail` term — it is
still worth measuring, just not worth 15% of the metric.

Proposed weights (`harness/scorer.py:19-22`). Treat the split as a starting
point, not a result; the load-bearing change is that sensitivity is measured
at all:

| term | weight | notes |
|---|---|---|
| `shape_err` (observed) | 0.20 | down from 0.35 |
| `gen_err` (held-out params) | 0.45 | unchanged |
| `sens_err` (new) | 0.20 | replaces `robust_err` |
| `regen_fail` | 0.10 | build failures only |
| `parsimony_pen` | 0.05 | unchanged |

### 2.3 Make `parsimony_pen` actually fire

It is `0.000000` in every recorded row. Either fix it so it discriminates or
delete it and redistribute its weight. Do not ship a third inert term.

### 2.4 Guard against inert terms

Add a test that runs the scorer over a deliberately-wrong reference solver and
asserts every weighted term is nonzero. An inert term should fail CI, not sit
in the metric for 13 generations.

---

## Phase 3 — Compositional task generation

Only after Phase 1 reports. Its result determines the difficulty target.

Replace the twelve named archetypes in `harness/generator.py` with a
randomized feature-graph sampler:

- sketch primitives + constraints
- extrude, revolve, loft, sweep
- cuts, holes, pockets, counterbores
- fillets, chamfers
- linear + polar patterns
- shells, ribs, bosses
- feature-order dependencies (including orderings that fail)

A task is a random composition. No task should be recognizable as a named
family. Emit two parameter-naming tracks:

- **semantic**: `hole_d`, `plate_t`
- **anonymous**: `p0`, `p1`, `p2`

The anonymous track is the more honest measurement, since `solver.py`'s
current `find_role` logic is substring matching on parameter names — under
anonymous naming that entire strategy collapses and the agent must infer role
from geometry. Report both tracks separately.

### Difficulty target

- stripped baseline `regen_err`: **0.55–0.70**
- handwritten reference solver: **below 0.15**
- enough independent failure modes to support 5–15 meaningful improvements
  over 50 generations

Write the handwritten reference solver as part of this phase. Without it you
cannot tell "hard" from "impossible," and the headroom number above is
unverifiable.

### Split sizes

| split | count | purpose |
|---|---|---|
| dev | 64–128 | agent-visible |
| test | ≥256 | sealed, in-distribution |
| test-ood | ≥128 | sealed, composition/operation OOD, **many distinct families** |

The OOD split must not repeat a single family the way the current
`ood_helix_cut` pair does.

---

## Phase 4 — Benchmark recursion itself

**This is the differentiator and it is cheap. Do not defer it.**

Without a control, "recursive improvement" is indistinguishable from "N
independent samples, keep the best." Add to `loop.sh` a mode flag:

- `CARRY=1` (default) — recursive: accepted solver seeds the next generation.
- `CARRY=0` — no-carry: every proposal starts from the pristine baseline;
  the ratchet still records the best, but nothing is inherited.
- `FEEDBACK=0` (optional third arm) — proposals do not see prior scores.

Run all arms at identical budget and seed count. The headline claim of the
project is: **the recursive arm beats the no-carry arm at equal budget.**
Report the gap with confidence intervals. If it does not beat it, report that
— it is the most interesting negative result the project could produce.

---

## Phase 5 — Budget, sealing, reproducibility

### 5.1 Wire real cost accounting

`loop.sh:557-558` hardcodes `"tokens": 0, "usd": 0.0`. Capture actual token
counts and USD from the agent CLI invocation and write them through. Until
this works, `USD_CEILING` (`loop.sh:21`) is decorative and no cost-efficiency
comparison between arms is valid.

Also record per-generation agent wall time separately from evaluation wall
time — `wall_s` currently conflates them.

### 5.2 Stop leaking sealed scores into the workspace

`loop.sh:565-577` appends sealed `test` and `test-ood` results to
`results.tsv`, which the next agent turn can read. Write hidden-split results
to a path outside the agent's working tree and merge them into the run bundle
only after the run completes.

### 5.3 Pin dependencies

`requirements.txt:3-8` uses lower bounds only. CadQuery/OCP version drift
changes tessellation and therefore scores. Pin exact versions, commit a
lockfile, and record the resolved versions in each run manifest.

### 5.4 Run protocol

- 50 generations, or a fixed six-hour budget, whichever binds first
- per-turn caps on wall time and tokens
- **three independent seeds per arm** — the current n=1 supports no claim
- identical starting commit, feedback contract, and environment across arms

---

## Phase 6 — Chart the scientific story

`plots/make_chart.py`. Per model, plot:

- every attempted experiment (accepted and rejected)
- the accepted dev frontier
- **hidden in-distribution score, plotted separately from dev**
- hidden compositional-OOD score
- confidence band across the three seeds
- x-axis toggle: generations / wall time / tokens / dollars

The single most important addition is separating hidden from dev. A dev curve
that improves while the hidden curve does not is the overfitting signal this
benchmark exists to detect, and the current chart cannot show it.

---

## Explicitly deferred

**Constrained CAD IR** (replacing emitted Python with an interpreted JSON
feature tree). Deferred, not rejected. Reasons: reward hacking is not the
current bottleneck (`violations: 0` in both arms of the v2 manifest);
hand-authoring the IR means hand-authoring the hypothesis space the agent is
supposed to be searching, which reintroduces the Phase-1 problem in a new
form; and it is the largest single engineering cost on the list. Revisit when
accepting untrusted third-party submissions.

**Full container sealing** (no-network agent container, separate evaluator
container, read-only FS, hidden GT never mounted). Correct for a public
benchmark, unnecessary for a single-operator research loop. Phase 5.2 fixes
the one leak that affects current results. Do the rest at public release.

---

## Sequence and gates

| phase | gate to proceed |
|---|---|
| 1. Honest baseline + falsification | Accepted diffs reviewed; go/no-go decision recorded |
| 2. Metric (parallel with 1) | No inert weighted terms; CI test passing |
| 3. Compositional generator | Baseline 0.55–0.70; reference solver below 0.15 |
| 4. No-carry control | Recursive vs no-carry gap measured with CIs |
| 5. Budget + sealing | Nonzero token/USD in results; no hidden scores in workspace |
| 6. Chart + release | Hidden and dev curves plotted separately |

Tag the current state `v0.2-mechanism-demo` before starting, and describe it
in the README as exactly that: a demonstration that the loop mechanism works,
in which the measured improvement came from enabling pre-written templates.
The honest framing costs nothing now and protects the v0.3 result later.

## Deliverable

Report back with: the Phase 1 accepted diffs quoted in full, the new baseline
number, and a go/no-go recommendation on Phase 3 based on what the agents
actually wrote. Do not proceed past the Phase 1 gate without that review.
