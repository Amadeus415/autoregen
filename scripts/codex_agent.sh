#!/usr/bin/env bash
# One bounded autoregen researcher turn via Codex CLI.
set -euo pipefail

ROOT="${ROOT:?loop.sh must export ROOT}"
GEN="${GEN:?loop.sh must export GEN}"
CODEX_BIN="${CODEX_BIN:-$(command -v codex)}"
CODEX_MODEL="${CODEX_MODEL:-gpt-5.6-sol}"
CODEX_REASONING_EFFORT="${CODEX_REASONING_EFFORT:-high}"
PROMPT_FILE="$(mktemp -t autoregen-codex.XXXXXX)"
trap 'rm -f "$PROMPT_FILE"' EXIT

printf '%s\n' \
  "You are one bounded researcher turn in autoregen generation $GEN." \
  "Work only in $ROOT." \
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

"$CODEX_BIN" exec \
  --model "$CODEX_MODEL" \
  --config "model_reasoning_effort=\"$CODEX_REASONING_EFFORT\"" \
  --config 'approval_policy="never"' \
  --sandbox workspace-write \
  --cd "$ROOT" \
  --ephemeral \
  --ignore-user-config \
  - < "$PROMPT_FILE"
