# autoregen

A [Karpathy autoresearch](https://github.com/karpathy/autoresearch)-style loop for **parametric CAD**.

Give an agent one observed solid and the **names** of the driving parameters (values withheld). The agent edits a reconstruction program. An immutable evaluator scores that program on the observed member **and** on held-out parameter vectors. If the score improved, keep the edit. If not, throw it away. Repeat.

You wake up to a log of experiments and (hopefully) a solver that recovered design intent.

## Three files

| File | Role |
|---|---|
| `prepare.py` | Immutable. Generates the tiny synthetic set, scores solvers, runs the ratchet. |
| `solver.py` | **The only file the agent edits.** Task in → `build(**params)` source out. |
| `program.md` | Human-written research brief. The agent reads it; the agent does not edit it. |

`hidden_eval.py` holds the sealed family builders. `--workdir` copies only `solver.py`, `program.md`, and the visible tasks — the agent never gets the answer key in its cwd.

The metric is one scalar, `intent_err`, lower is better:

```
shape_err  = ½ · relative volume error  +  ½ · mean relative bbox-extent error
intent_err = mean over tasks of (mean shape_err over observed + held-out members)
```

Keep if strictly lower. Equal or worse is a discard. A crash is a crash. Every step is one row in `results.tsv`.

## Quick start

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Score the honest (mediocre) baseline twice — the number must match
python prepare.py generate
python prepare.py score
python prepare.py score

# Prove the ratchet with a local dummy researcher (10 causal steps)
python prepare.py loop --agent dummy --gens 10 --workdir runs/dummy

# Same loop, Grok 4.6 medium as the researcher
python prepare.py loop --agent grok --gens 10 --workdir runs/grok \
    --model grok-4.6 --effort medium
```

The loop prints the frontier `intent_err` and the path to `results.tsv`. `chart.png` is the accepted frontier plus every discard.

## What the agent is solving

Not “match this one solid.” The evaluator rebuilds the hidden family at parameter vectors the solver never saw. Copying the observed bounding box looks fine on the member you were shown and falls over on the rest.

Task folders are opaque (`t_8f1a0c2b`, …). Family names are not in the path. Parameter **names** are the intended hint.

## Ownership

- Agent edits `solver.py` only. Anything else is reverted before scoring.
- `data/hidden/` is sealed ground truth. The solver is not given those files.
- `results.tsv` is append-only and untracked. Rejects stay in the log.

## Tests

```bash
python -m pytest tests/ -q
```
