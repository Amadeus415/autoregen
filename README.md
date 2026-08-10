# autoregen

An [autoresearch](https://github.com/karpathy/autoresearch)-style recursive improvement loop for **parametric CAD**.

**Not AutoCAD.** Different product, different problem. This repo recovers *design intent* from a solid — a parametric `build()` program that generalizes to held-out parameter vectors — and ratchets improvements with git.

| Autoresearch | autoregen |
|---|---|
| `val_bpb` | `intent_err` ∈ [0, 1] (lower is better) |
| `train.py` | `solver.py` |
| gradient step | geometry / topology algorithm step |
| ~12 exp/hour | ~20–30 exp/hour target (geometry is cheap) |

## What it measures

Given an observed STEP solid + the **names** (not values) of driving parameters, the solver must emit:

```python
def build(plate_t: float, hole_d: float, fillet_r: float, ...) -> Solid: ...
```

Scored on the observed member **and** 4 held-out parameter vectors the solver never saw, plus a robustness sweep and a parsimony penalty:

```
intent_err = 0.35·shape_err + 0.45·gen_err + 0.15·robust_err + 0.05·parsimony_pen
```

Shape match on one solid is table stakes. Generalization is the signal.

## Quick start

```bash
# Python 3.10–3.13 recommended (CadQuery/OCP wheels)
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Tiny synthetic dataset + harness checksum
python prepare.py generate --quick
python prepare.py checksum --write

# Baseline (gen 0), twice — must match
python prepare.py gen0 --quick --workers 2

# Chart
python plots/make_chart.py

# Overnight ratchet (built-in micro-mutations; set AGENT_CMD for a real agent)
chmod +x loop.sh
MAX_GENS=50 WORKERS=4 ./loop.sh
```

Full dataset sizes (spec defaults): `train=512`, `dev=64`, `test=256`, `test-ood=128`.

```bash
python prepare.py generate --seed 42
python prepare.py checksum --write
python prepare.py gen0 --workers 8
```

## Repo layout

```
prepare.py        # IMMUTABLE — generator, scorer, sandbox, logging
solver.py         # THE ONLY FILE THE AGENT EDITS
program.md        # Human research directions (read-only to the agent)
loop.sh           # Ratchet: verify → edit → eval → gate → commit|reset
results.tsv       # Append-only experiment log
HARNESS.sha256    # Checksum of prepare.py + harness/ + task inputs + data/gt
data/families/    # Task inputs (STEP, params.json, budget)
data/gt/          # Sealed ground-truth programs (sandbox-blocked)
plots/make_chart.py
```

## Ownership rules

- Agent may edit `solver.py` only. `loop.sh` checks `git diff --name-only`.
- `HARNESS.sha256` covers code, visible task inputs, and GT; mismatch → hard stop.
- Solver subprocess: no network, no `data/gt/` reads, static AST checks.
- Violations append to `results.tsv` / `violations.log` — never silent.

## The loop

1. Verify harness checksum  
2. Agent reads `program.md`, `solver.py`, tail of `results.tsv`  
3. One change + one-line hypothesis  
4. `git commit`  
5. Dev eval (parallel workers, wall-clock cap)  
6. **Paired bootstrap gate** — accept only if 95% CI of mean per-task improvement excludes 0  
7. Keep or `git reset --hard`  
8. Goto 1  

Statistical gate matters: without it, noise manufactures a fake ratchet.

## Baseline (gen 0)

Deterministic heuristics — no LLM at inference:

1. Parse STEP topology (planes, cylinders, bbox)  
2. Parallel planes → thickness; cylinder clusters → holes  
3. Fuzzy-bind parameter names → features  
4. Emit a CadQuery template (`plate`, `plate+hole`, `fillet`, `pattern`, `shell`, …)  
5. try/except bbox fallback  

Target band: `intent_err ≈ 0.55–0.70`. Below ~0.3 → tasks too easy; above ~0.85 → no gradient.

## Chart

`plots/chart.png` after any eval:

- Grey dots — every experiment (including rejects)  
- Bold step — best-so-far accepted dev  
- Blue dots — accepted gens  
- Red / orange — sealed `test` / `test-ood` every 25 gens  
- Shaded band — measured noise floor  

For a same-start model comparison, `benchmark_models.py` produces a second,
data-driven view: each model's candidate points and accepted frontier, sealed
test/OOD markers, plus the actual feedback cycle that makes the run recursive.
The chart does not infer or smooth improvement: only a gate-accepted solver is
fed into the next generation.

## Reproducible model-arm benchmark

```bash
# Preflight the isolated baseline without calling either model
python benchmark_models.py --preflight-only

# Three recursive generations per arm, then dev determinism + sealed test/OOD
python benchmark_models.py --generations 3 --workers 4
```

The built-in arms are pinned to:

- Antigravity CLI: `gemini-3.6-flash-high`, high effort, edit-accepting mode
- Grok CLI: `grok-4.5`, high reasoning, no subagents, through the pinned wrapper

Each arm starts from the same historical baseline solver, current immutable
harness, seed 42 quick dataset, and evaluation settings. Work happens in
isolated disposable repositories. The durable run contains a manifest, raw
per-arm TSVs, final solvers, CLI logs, deterministic dev reruns, sealed test and
OOD reports, and `chart.png` under `benchmark_runs/<run-id>/`.

After a run, independently re-score its saved solvers on the root dataset:

```bash
python audit_benchmark.py benchmark_runs/<run-id>
```

The audit requires the root harness checksum (including visible task inputs and
GT) to pass, repeats dev for determinism, and requires every dev/test/OOD score
and solver hash to match the isolated run before marking the report audited.

The default is deliberately a **quick comparative profile** (8 dev / 4 test /
2 OOD tasks) suitable for validating the end-to-end claim. It demonstrates the
mechanism; it is not enough evidence for a general model leaderboard. Publish a
winner only after a preregistered larger multi-seed run.

## Driving with a real agent

```bash
# Your agent CLI must: edit only solver.py, write .hypothesis.txt
export AGENT_CMD='my-agent --prompt program.md --file solver.py'
./loop.sh
```

Without `AGENT_CMD`, `loop.sh` runs a **built-in mutation agent** (hyperparameter / heuristic tweaks) so the harness is testable end-to-end.

## Honest failure modes

| Failure | What you'll see |
|---|---|
| Reward hacking | rows in `violations.log`, ownership resets |
| Noise as progress | bootstrap gate rejects; noise floor band on chart |
| Dev overfit | `test` / `test-ood` diverge from dev |
| OCC boolean flakiness | voxel IoU primary; exact IoU secondary-when-available |
| Plateau | expected after ~30 gens without archive/tree search |

## Phase status

- [x] Phase 1 — harness, generator L1–L3 + OOD, scorer, sandbox, baseline, chart  
- [x] Phase 2 — `loop.sh`, ratchet, bootstrap gate, violation log  
- [x] Researcher-arm comparison — isolated same-start CLI runs + validation chart
- [ ] Phase 3 — nested outer loop on `program.md` (`Δintent_err` / hour)
- [ ] Phase 4 — community submit and statistically powered leaderboard

## License

Apache-2.0 (intended). STEP/CadQuery stack is third-party; synthetic families are generated by this repo.
