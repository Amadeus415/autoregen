#!/usr/bin/env bash
# loop.sh — the autoregen ratchet driver.
# Agent edits solver.py only. Commit if better, reset if not.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

# Config
MAX_GENS="${MAX_GENS:-200}"
WORKERS="${WORKERS:-4}"
WALL_CAP="${WALL_CAP:-240}"          # seconds per dev eval
RESOLUTION="${RESOLUTION:-64}"
N_POINTS="${N_POINTS:-8000}"
ROBUST_N="${ROBUST_N:-8}"
USD_CEILING="${USD_CEILING:-50}"     # hard stop (baseline has $0 cost)
AGENT_CMD="${AGENT_CMD:-}"           # optional external agent; empty = dry/manual mode
SLEEP_BETWEEN="${SLEEP_BETWEEN:-0}"
SPLIT="${SPLIT:-dev}"
BRANCH="${BRANCH:-autoregen-loop}"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die() { log "FATAL: $*"; exit 1; }

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
[[ -f prepare.py ]] || die "prepare.py missing"
[[ -f solver.py ]] || die "solver.py missing"
[[ -f program.md ]] || die "program.md missing"

if [[ ! -d data/families/$SPLIT ]]; then
  log "No $SPLIT data — generating quick set"
  "$PYTHON" prepare.py generate --quick
  "$PYTHON" prepare.py checksum --write
fi

log "Verifying HARNESS.sha256"
"$PYTHON" prepare.py verify-checksum || die "Harness checksum mismatch — hard stop"

# git setup
if [[ ! -d .git ]]; then
  git init
  git add -A
  git commit -m "chore: initial autoregen import" || true
fi
git checkout -B "$BRANCH" 2>/dev/null || git checkout "$BRANCH"

# ensure gen0 baseline exists
if [[ ! -f best_per_task.json ]]; then
  log "No best_per_task.json — running gen0"
  "$PYTHON" prepare.py gen0 --workers "$WORKERS" --resolution "$RESOLUTION" \
    --n-points "$N_POINTS" --robust-n "$ROBUST_N" || true
  [[ -f best_per_task.json ]] || die "gen0 failed to produce best_per_task.json"
fi

# generation counter
GEN=0
if [[ -f results.tsv ]]; then
  # last numeric gen in col1
  GEN=$(awk -F'\t' 'NR>1 && $1 ~ /^[0-9]+$/ {g=$1} END{print g+0}' results.tsv)
fi
log "Starting loop at gen=$GEN max=$MAX_GENS"

# ---------------------------------------------------------------------------
# Agent step: propose ONE change to solver.py
# ---------------------------------------------------------------------------
run_agent() {
  local gen="$1"
  local hypothesis_file="$ROOT/.hypothesis.txt"

  if [[ -n "$AGENT_CMD" ]]; then
    # External agent: receives gen number, must edit only solver.py
    # and write a one-line hypothesis to .hypothesis.txt
    log "Running external agent: $AGENT_CMD"
    # shellcheck disable=SC2086
    GEN="$gen" ROOT="$ROOT" $AGENT_CMD || log "Agent exited non-zero"
  else
    # Built-in micro-agent: deterministic algorithmic mutations for demo loop.
    # Real research replaces AGENT_CMD with an LLM coding agent constrained
    # to solver.py. This default explores a small mutation space so the
    # ratchet has something to climb without external deps.
    "$PYTHON" - <<'PY'
import os, re, random
from pathlib import Path
root = Path(os.environ.get("ROOT", "."))
gen = int(os.environ.get("GEN", "1"))
rng = random.Random(gen * 10007 + 13)
src_path = root / "solver.py"
src = src_path.read_text()
hypothesis = "noop"

mutations = []

# Mutation pool — each is a (name, pattern, repl) or callable
def mut_fillet_frac(s):
    # tweak fillet guess fraction
    new = rng.choice(["0.10", "0.12", "0.15", "0.18", "0.20", "0.25"])
    if "thickness * 0.15" in s:
        return s.replace("thickness * 0.15", f"thickness * {new}", 1), f"fillet_guess_frac={new}"
    if re.search(r"thickness \* 0\.\d+", s):
        return re.sub(r"thickness \* 0\.\d+", f"thickness * {new}", s, count=1), f"fillet_guess_frac={new}"
    return s, None

def mut_hole_cluster_tol(s):
    new = rng.choice(["0.10", "0.12", "0.15", "0.20", "0.25"])
    if "tol=0.15" in s:
        return s.replace("tol=0.15", f"tol={new}", 1), f"hole_cluster_tol={new}"
    if re.search(r"tol=0\.\d+", s):
        return re.sub(r"tol=0\.\d+", f"tol={new}", s, count=1), f"hole_cluster_tol={new}"
    return s, None

def mut_plane_dot(s):
    new = rng.choice(["0.95", "0.96", "0.97", "0.98", "0.99"])
    if "dot < 0.98" in s:
        return s.replace("dot < 0.98", f"dot < {new}", 1), f"plane_parallel_dot={new}"
    return s, None

def mut_template_priority(s):
    # swap preference: pattern before fillet or vice versa
    a = "elif count_p and hole_p:\n        template = \"pattern\"\n    elif pocket_p or cbore_p:"
    b = "elif pocket_p or cbore_p:\n        template = \"pocket\"\n    elif count_p and hole_p:"
    # simpler: change plate_hole_fillet vs plate_hole priority
    if 'elif hole_p and fillet_p:\n        template = "plate_hole_fillet"\n    elif hole_p:' in s:
        if rng.random() < 0.5:
            s2 = s.replace(
                'elif hole_p and fillet_p:\n        template = "plate_hole_fillet"\n    elif hole_p:\n        template = "plate_hole"',
                'elif hole_p:\n        template = "plate_hole"\n    elif hole_p and fillet_p:\n        template = "plate_hole_fillet"',
                1,
            )
            if s2 != s:
                return s2, "prefer_plate_hole_over_fillet"
    return s, None

def mut_fallback_dims(s):
    # tweak default box fallback
    if "box(40.0, 30.0, 5.0)" in s:
        w = rng.choice([35.0, 40.0, 45.0, 50.0])
        h = rng.choice([25.0, 30.0, 35.0])
        t = rng.choice([4.0, 5.0, 6.0, 8.0])
        return s.replace("box(40.0, 30.0, 5.0)", f"box({w}, {h}, {t})", 1), f"fallback_box={w}x{h}x{t}"
    return s, None

def mut_bind_thickness_name(s):
    # broaden thickness name matching
    if 'lname in (\n            "plate_t",' in s and "depth" not in s.split("plate_t")[0][-80:]:
        pass
    if '"plate_t",\n            "block_t",' in s and '"depth",' not in s:
        s2 = s.replace('"plate_t",\n            "block_t",', '"plate_t",\n            "depth",\n            "block_t",', 1)
        if s2 != s:
            return s2, "bind_thickness_add_depth"
    return s, None

def mut_hole_fit_factor(s):
    new = rng.choice(["0.5", "0.6", "0.65", "0.7", "0.75"])
    if "abs(c[\"radius\"] - hole_radii[0]) < 0.2" in s:
        return s.replace(
            'abs(c["radius"] - hole_radii[0]) < 0.2',
            f'abs(c["radius"] - hole_radii[0]) < {new}',
            1,
        ), f"hole_count_radius_tol={new}"
    return s, None

def mut_enable_pattern_template(s):
    """Re-introduce pattern template for multi-hole families."""
    marker = "elif hole_p and fillet_p:"
    if "template = \"pattern\"" in s and "count_p and hole_p" in s:
        return s, None
    if marker in s and "count_p and hole_p and n_cyl" not in s:
        insert = (
            "elif count_p and hole_p and n_cyl >= 2:\n"
            "        template = \"pattern\"\n"
            "    elif hole_p and fillet_p:"
        )
        s2 = s.replace(marker, insert, 1)
        if s2 != s:
            return s2, "enable_pattern_template"
    return s, None

def mut_enable_pocket_template(s):
    marker = "elif hole_p and fillet_p:"
    if 'template = "pocket"' in s.split("Choose template")[-1][:800] if "Choose template" in s else s:
        # already has pocket in selection path near templates
        if "elif pocket_p or cbore_p:" in s:
            return s, None
    if marker in s and "pocket_p or cbore_p" not in s:
        insert = (
            "elif pocket_p or cbore_p:\n"
            "        template = \"pocket\"\n"
            "    elif hole_p and fillet_p:"
        )
        s2 = s.replace(marker, insert, 1)
        if s2 != s:
            return s2, "enable_pocket_template"
    return s, None

def mut_enable_shell_template(s):
    if "elif wall_p and (w_p or h_p):" in s:
        return s, None
    marker = "if outer_r_p and n_cyl >= 1 and not w_p:"
    if marker in s:
        insert = (
            "if wall_p and (w_p or h_p):\n"
            "        template = \"shell\"\n"
            "    elif outer_r_p and n_cyl >= 1 and not w_p:"
        )
        s2 = s.replace(marker, insert, 1)
        if s2 != s:
            return s2, "enable_shell_template"
    return s, None

def mut_enable_ribbed_template(s):
    if "elif rib_h_p or rib_t_p:" in s:
        return s, None
    marker = "if outer_r_p and n_cyl >= 1 and not w_p:"
    # prefer after shell if present
    if "if wall_p and (w_p or h_p):" in s:
        marker = "if wall_p and (w_p or h_p):"
        insert = (
            "if rib_h_p or rib_t_p:\n"
            "        template = \"ribbed\"\n"
            "    elif wall_p and (w_p or h_p):"
        )
    else:
        insert = (
            "if rib_h_p or rib_t_p:\n"
            "        template = \"ribbed\"\n"
            "    elif outer_r_p and n_cyl >= 1 and not w_p:"
        )
    if marker in s:
        s2 = s.replace(marker, insert, 1)
        if s2 != s:
            return s2, "enable_ribbed_template"
    return s, None

def mut_enable_boss_template(s):
    if "elif boss_d_p or boss_h_p:" in s:
        return s, None
    marker = "if outer_r_p and n_cyl >= 1 and not w_p:"
    if "if rib_h_p or rib_t_p:" in s:
        marker = "if rib_h_p or rib_t_p:"
        insert = (
            "if boss_d_p or boss_h_p:\n"
            "        template = \"boss\"\n"
            "    elif rib_h_p or rib_t_p:"
        )
    else:
        insert = (
            "if boss_d_p or boss_h_p:\n"
            "        template = \"boss\"\n"
            "    elif outer_r_p and n_cyl >= 1 and not w_p:"
        )
    if marker in s:
        s2 = s.replace(marker, insert, 1)
        if s2 != s:
            return s2, "enable_boss_template"
    return s, None

muts = [
    mut_enable_pattern_template,
    mut_enable_pocket_template,
    mut_enable_shell_template,
    mut_enable_ribbed_template,
    mut_enable_boss_template,
    mut_fillet_frac,
    mut_hole_cluster_tol,
    mut_plane_dot,
    mut_template_priority,
    mut_fallback_dims,
    mut_bind_thickness_name,
    mut_hole_fit_factor,
]
rng.shuffle(muts)
new_src = src
hyp = "noop"
for m in muts:
    new_src, hyp = m(src)
    if hyp and new_src != src:
        break
else:
    # force a comment bump so git has a change to evaluate (will reset if not better)
    new_src = src.rstrip() + f"\n# gen {gen} probe\n"
    hyp = f"comment_probe_gen_{gen}"

src_path.write_text(new_src)
(root / ".hypothesis.txt").write_text(hyp + "\n")
print(hyp)
PY
  fi

  if [[ -f "$hypothesis_file" ]]; then
    cat "$hypothesis_file"
  else
    echo "no-hypothesis"
  fi
}

# ---------------------------------------------------------------------------
# Ownership gate: only solver.py may change
# ---------------------------------------------------------------------------
assert_only_solver_dirty() {
  local dirty
  dirty="$(git diff --name-only HEAD 2>/dev/null || true)"
  dirty="$(echo "$dirty" | grep -v '^$' || true)"
  if [[ -z "$dirty" ]]; then
    # also check untracked? agent shouldn't create files
    return 0
  fi
  local bad
  bad="$(echo "$dirty" | grep -v '^solver\.py$' || true)"
  if [[ -n "$bad" ]]; then
    log "VIOLATION: agent touched non-solver files:"
    echo "$bad"
    git checkout -- .
    git clean -fd --exclude=data --exclude=.venv --exclude=last_eval.json \
      --exclude=best_per_task.json --exclude=results.tsv --exclude=plots \
      --exclude=noise_floor.json --exclude=.hypothesis.txt 2>/dev/null || true
    echo "ownership_violation" >> "$ROOT/violations.log"
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
CUM_USD=0
while (( GEN < MAX_GENS )); do
  GEN=$((GEN + 1))
  log "======== generation $GEN ========"

  "$PYTHON" prepare.py verify-checksum || die "Harness tampered at gen $GEN"

  # snapshot solver for reset
  cp solver.py solver.py.bak

  export GEN ROOT
  HYP="$(run_agent "$GEN" | tail -n1)"
  log "Hypothesis: $HYP"

  if ! assert_only_solver_dirty; then
    append_violation=1
    "$PYTHON" - <<PY
from harness.eval import append_results_tsv
from pathlib import Path
import hashlib
src = Path("solver.py").read_bytes()
sha = hashlib.sha256(src).hexdigest()
append_results_tsv(Path("results.tsv"), {
    "gen": $GEN, "sha": sha, "intent_err": 1.0, "shape_err": 1.0, "gen_err": 1.0,
    "robust_err": 1.0, "parsimony_pen": 1.0, "wall_s": 0, "tokens": 0, "usd": 0,
    "accepted": 0, "note": "violation:ownership", "violations": "ownership",
    "split": "$SPLIT", "n_tasks": 0,
})
PY
    mv solver.py.bak solver.py 2>/dev/null || true
    continue
  fi

  # if no change, skip
  if git diff --quiet solver.py 2>/dev/null; then
    log "No change to solver.py — skip"
    GEN=$((GEN - 1))  # don't burn a gen number... actually keep counting
    # restore gen count meaning: keep
    sleep "$SLEEP_BETWEEN"
    continue
  fi

  # commit candidate
  git add solver.py
  git commit -m "gen ${GEN}: ${HYP}" --allow-empty=false || {
    log "Nothing to commit"
    continue
  }
  SHA="$(git rev-parse --short HEAD)"

  # eval
  log "Evaluating dev set..."
  set +e
  "$PYTHON" prepare.py eval \
    --split "$SPLIT" \
    --workers "$WORKERS" \
    --resolution "$RESOLUTION" \
    --n-points "$N_POINTS" \
    --robust-n "$ROBUST_N" \
    --wall-cap "$WALL_CAP" \
    --out last_eval.json \
    --gen "$GEN" \
    --note "$HYP"
  EVAL_RC=$?
  set -e

  if [[ $EVAL_RC -ne 0 && ! -f last_eval.json ]]; then
    log "Eval failed hard — reset"
    git reset --hard HEAD~1
    "$PYTHON" - <<PY
from harness.eval import append_results_tsv
from pathlib import Path
append_results_tsv(Path("results.tsv"), {
    "gen": $GEN, "sha": "$SHA", "intent_err": 1.0, "shape_err": 1.0, "gen_err": 1.0,
    "robust_err": 1.0, "parsimony_pen": 1.0, "wall_s": 0, "tokens": 0, "usd": 0,
    "accepted": 0, "note": "eval_fail:${HYP}", "violations": "eval_fail",
    "split": "$SPLIT", "n_tasks": 0,
})
PY
    continue
  fi

  # statistical gate
  set +e
  "$PYTHON" prepare.py gate --new-eval last_eval.json --best best_per_task.json --out last_gate.json
  GATE_RC=$?
  set -e

  INTENT="$("$PYTHON" -c 'import json; print(json.load(open("last_eval.json"))["intent_err"])')"
  AGG="$("$PYTHON" -c 'import json; a=json.load(open("last_eval.json"))["aggregate"]; print(a["shape_err"], a["gen_err"], a["robust_err"], a["parsimony_pen"], a.get("n_tasks",0))')"
  read -r SHAPE GENERR ROBUST PARS NTASKS <<<"$AGG"
  WALL="$("$PYTHON" -c 'import json; print(json.load(open("last_eval.json")).get("wall_s",0))')"

  if [[ $GATE_RC -eq 0 ]]; then
    log "ACCEPTED gen=$GEN intent_err=$INTENT sha=$SHA hyp=$HYP"
    cp last_eval.json best_per_task.json
    # rewrite best_per_task in expected shape
    "$PYTHON" - <<PY
import json
from pathlib import Path
r = json.loads(Path("last_eval.json").read_text())
Path("best_per_task.json").write_text(json.dumps({
    "intent_err": r["intent_err"],
    "per_task": r["per_task"],
    "solver_sha": r.get("solver_sha"),
    "gen": $GEN,
}, indent=2))
PY
    "$PYTHON" - <<PY
from harness.eval import append_results_tsv
from pathlib import Path
append_results_tsv(Path("results.tsv"), {
    "gen": $GEN, "sha": "$SHA", "intent_err": float("$INTENT"),
    "shape_err": float("$SHAPE"), "gen_err": float("$GENERR"),
    "robust_err": float("$ROBUST"), "parsimony_pen": float("$PARS"),
    "wall_s": float("$WALL"), "tokens": 0, "usd": 0.0,
    "accepted": 1, "note": """$HYP""", "violations": "",
    "split": "$SPLIT", "n_tasks": int(float("$NTASKS")),
})
PY
  else
    log "REJECTED gen=$GEN intent_err=$INTENT — reset"
    git reset --hard HEAD~1
    "$PYTHON" - <<PY
from harness.eval import append_results_tsv
from pathlib import Path
append_results_tsv(Path("results.tsv"), {
    "gen": $GEN, "sha": "$SHA", "intent_err": float("$INTENT"),
    "shape_err": float("$SHAPE"), "gen_err": float("$GENERR"),
    "robust_err": float("$ROBUST"), "parsimony_pen": float("$PARS"),
    "wall_s": float("$WALL"), "tokens": 0, "usd": 0.0,
    "accepted": 0, "note": """$HYP""", "violations": "",
    "split": "$SPLIT", "n_tasks": int(float("$NTASKS")),
})
PY
  fi

  rm -f solver.py.bak

  # sealed test every 25 gens
  if (( GEN % 25 == 0 )); then
    log "Sealed test eval at gen $GEN"
    "$PYTHON" prepare.py eval --split test --workers "$WORKERS" \
      --resolution "$RESOLUTION" --max-tasks 32 \
      --out "test_gen${GEN}.json" --append-tsv --gen "$GEN" --note "sealed-test" || true
    if [[ -d data/families/test-ood ]]; then
      "$PYTHON" prepare.py eval --split test-ood --workers "$WORKERS" \
        --resolution "$RESOLUTION" --max-tasks 16 \
        --out "testood_gen${GEN}.json" --append-tsv --gen "$GEN" --note "sealed-ood" || true
    fi
  fi

  # noise floor every 20 gens
  if (( GEN % 20 == 0 )); then
    log "Noise floor measurement"
    "$PYTHON" prepare.py noise-floor --n 2 --workers "$WORKERS" \
      --resolution "$RESOLUTION" --robust-n "$ROBUST_N" || true
  fi

  # chart
  if [[ -f plots/make_chart.py ]]; then
    "$PYTHON" plots/make_chart.py || true
  fi

  # cost ceiling
  CUM_USD="$("$PYTHON" -c "
import pathlib
p=pathlib.Path('results.tsv')
if not p.exists():
    print(0); raise SystemExit
usd=0
for i,line in enumerate(p.read_text().splitlines()):
    if i==0: continue
    parts=line.split('\t')
    if len(parts)>9:
        try: usd+=float(parts[9])
        except: pass
print(usd)
")"
  if "$PYTHON" -c "import sys; sys.exit(0 if float('$CUM_USD') < float('$USD_CEILING') else 1)"; then
    :
  else
    die "USD ceiling hit ($CUM_USD >= $USD_CEILING)"
  fi

  sleep "$SLEEP_BETWEEN"
done

log "Loop finished at gen=$GEN"
"$PYTHON" plots/make_chart.py || true
log "Done. See results.tsv and plots/chart.png"
