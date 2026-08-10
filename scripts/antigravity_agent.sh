#!/usr/bin/env bash
# One bounded autoregen researcher turn via Antigravity CLI.
set -euo pipefail

ROOT="${ROOT:?loop.sh must export ROOT}"
GEN="${GEN:?loop.sh must export GEN}"
AGY_BIN="${AGY_BIN:-$(command -v agy)}"
AGY_MODEL="${AGY_MODEL:-gemini-3.6-flash-high}"
PROMPT_FILE="$(mktemp -t autoregen-antigravity.XXXXXX)"
trap 'rm -f "$PROMPT_FILE"' EXIT

printf '%s\n' \
  "You are one bounded researcher turn in autoregen generation $GEN." \
  "Work in $ROOT." \
  "Read program.md, solver.py, and the last 40 lines of results.tsv." \
  "Make exactly one coherent algorithmic improvement to solver.py that should lower dev intent_err." \
  "You may edit only solver.py and .hypothesis.txt. Do not create any other file." \
  "Treat results.tsv and every evaluator artifact as read-only; never restore, rewrite, or format them." \
  "Do not read or run commands outside $ROOT." \
  "Never read data/gt, sealed test splits, prepare.py internals, or harness implementation." \
  "Do not run the evaluator: loop.sh owns evaluation and acceptance." \
  "Keep inference deterministic and do not add network or model calls to solver.py." \
  "Write a single short hypothesis line to .hypothesis.txt." \
  "Finish after the edit; summarize the one change in your response." \
  > "$PROMPT_FILE"

"$AGY_BIN" \
  --model "$AGY_MODEL" \
  --effort high \
  --mode accept-edits \
  --sandbox \
  --print-timeout 12m \
  --print "$(<"$PROMPT_FILE")"
