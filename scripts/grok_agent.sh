#!/usr/bin/env bash
# One bounded autoregen researcher turn via the pinned Grok consultation wrapper.
set -euo pipefail

ROOT="${ROOT:?loop.sh must export ROOT}"
GEN="${GEN:?loop.sh must export GEN}"
GROK_WRAPPER="${GROK_WRAPPER:-$HOME/.codex/skills/consult-grok-cli/scripts/consult-grok.sh}"
TIMEOUT_BIN="${TIMEOUT_BIN:-$(command -v gtimeout || command -v timeout)}"
[[ -n "$TIMEOUT_BIN" && -x "$TIMEOUT_BIN" ]] || {
  printf 'GNU timeout is required (install coreutils for gtimeout).\n' >&2
  exit 2
}
TURN_TIMEOUT="${GROK_TURN_TIMEOUT:-12m}"
MAX_ATTEMPTS="${GROK_MAX_ATTEMPTS:-2}"
PROMPT_FILE="$(mktemp -t autoregen-grok.XXXXXX)"
SOLVER_SNAPSHOT="$(mktemp -t autoregen-grok-solver.XXXXXX)"
HYP_SNAPSHOT="$(mktemp -t autoregen-grok-hyp.XXXXXX)"
cp "$ROOT/solver.py" "$SOLVER_SNAPSHOT"
if [[ -f "$ROOT/.hypothesis.txt" ]]; then
  cp "$ROOT/.hypothesis.txt" "$HYP_SNAPSHOT"
else
  : > "$HYP_SNAPSHOT"
fi
trap 'rm -f "$PROMPT_FILE" "$SOLVER_SNAPSHOT" "$HYP_SNAPSHOT"' EXIT

printf '%s\n' \
  "Implement one bounded researcher turn in autoregen generation $GEN." \
  "Read program.md, solver.py, and the last 40 lines of results.tsv." \
  "Make exactly one coherent algorithmic improvement to solver.py that should lower dev intent_err." \
  "Allowed edits: solver.py and .hypothesis.txt only. Do not create any other file." \
  "Treat results.tsv and every evaluator artifact as read-only; never restore, rewrite, or format them." \
  "Do not read or run commands outside $ROOT. Do not search for environments or dependencies elsewhere." \
  "Never read data/gt, sealed test splits, prepare.py internals, or harness implementation." \
  "Do not run the evaluator: loop.sh owns evaluation and acceptance." \
  "Keep inference deterministic and do not add network or model calls to solver.py." \
  "Write a single short hypothesis line to .hypothesis.txt." \
  "Finish after the edit and report the exact files changed." \
  > "$PROMPT_FILE"

attempt=1
while (( attempt <= MAX_ATTEMPTS )); do
  if "$TIMEOUT_BIN" --foreground --kill-after=15s "$TURN_TIMEOUT" \
    "$GROK_WRAPPER" \
      --cwd "$ROOT" \
      --implement \
      --prompt-file "$PROMPT_FILE"; then
    exit 0
  else
    status=$?
  fi
  printf 'Grok turn attempt %s/%s failed (status=%s); restoring candidate state.\n' \
    "$attempt" "$MAX_ATTEMPTS" "$status" >&2
  cp "$SOLVER_SNAPSHOT" "$ROOT/solver.py"
  if [[ -s "$HYP_SNAPSHOT" ]]; then
    cp "$HYP_SNAPSHOT" "$ROOT/.hypothesis.txt"
  else
    rm -f "$ROOT/.hypothesis.txt"
  fi
  attempt=$((attempt + 1))
done
exit 1
