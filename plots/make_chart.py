#!/usr/bin/env python3
"""Plot autoregen results: grey dots, best-so-far ratchet, test/OOD markers, noise band."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TSV = ROOT / "results.tsv"
OUT = ROOT / "plots" / "chart.png"
NOISE = ROOT / "noise_floor.json"


def load_tsv(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open() as f:
        header = f.readline().strip().split("\t")
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            d = dict(zip(header, parts))
            try:
                d["gen"] = int(float(d.get("gen", -1)))
                d["intent_err"] = float(d.get("intent_err", 1.0))
                d["accepted"] = int(float(d.get("accepted", 0)))
                d["wall_s"] = float(d.get("wall_s", 0) or 0)
                d["usd"] = float(d.get("usd", 0) or 0)
            except ValueError:
                continue
            rows.append(d)
    return rows


def main() -> int:
    rows = load_tsv(TSV)
    if not rows:
        print("No results.tsv rows yet — nothing to plot")
        # empty placeholder
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.set_title("autoregen — intent_err (no data yet)")
        ax.set_xlabel("generation")
        ax.set_ylabel("intent_err (lower is better)")
        fig.savefig(OUT, dpi=140, bbox_inches="tight")
        print(f"Wrote {OUT}")
        return 0

    dev = [r for r in rows if r.get("split", "dev") in ("dev", "") or r.get("note", "").startswith("gen")]
    # Prefer rows that are regular loop evals on dev
    loop_rows = [
        r
        for r in rows
        if r.get("split", "dev") == "dev"
        and "sealed" not in r.get("note", "")
        and "violation" not in r.get("note", "")
    ]
    if not loop_rows:
        loop_rows = rows

    gens = np.array([r["gen"] for r in loop_rows], dtype=float)
    errs = np.array([r["intent_err"] for r in loop_rows], dtype=float)
    acc = np.array([r["accepted"] for r in loop_rows], dtype=int)

    # best-so-far step
    best = np.minimum.accumulate(errs)
    # only step on accepted? design: grey = all, bold = best-so-far including rejects measured
    # Karpathy: best-so-far frontier from kept commits. We track accepted ratchet separately.
    best_acc = []
    cur = 1.0
    for e, a in zip(errs, acc):
        if a and e < cur:
            cur = e
        best_acc.append(cur)
    best_acc = np.array(best_acc)

    fig, ax = plt.subplots(figsize=(11, 6))

    # all experiments
    ax.scatter(gens, errs, c="#9aa0a6", s=28, alpha=0.75, label="experiments", zorder=2)
    # accepted
    if acc.any():
        ax.scatter(
            gens[acc == 1],
            errs[acc == 1],
            c="#1a73e8",
            s=40,
            zorder=3,
            label="accepted",
        )

    # ratchet step line
    ax.step(gens, best_acc, where="post", color="#202124", lw=2.2, label="best-so-far (dev)", zorder=4)

    # noise floor band
    if NOISE.exists():
        try:
            nf = json.loads(NOISE.read_text())
            mu, std = float(nf["mean"]), float(nf["std"])
            # band around current best
            if len(best_acc):
                y = best_acc[-1]
                # if std~0 (deterministic), show tiny band from report max-min
                half = max(std * 1.96, (float(nf["max"]) - float(nf["min"])) / 2, 0.002)
                ax.axhspan(y - half, y + half, color="#1a73e8", alpha=0.12, label="noise floor")
        except Exception:
            pass

    # sealed test / ood markers
    test_rows = [r for r in rows if "sealed-test" in r.get("note", "") or r.get("split") == "test"]
    ood_rows = [r for r in rows if "sealed-ood" in r.get("note", "") or r.get("split") == "test-ood"]
    if test_rows:
        ax.scatter(
            [r["gen"] for r in test_rows],
            [r["intent_err"] for r in test_rows],
            c="#d93025",
            s=70,
            marker="D",
            zorder=5,
            label="test (sealed)",
        )
    if ood_rows:
        ax.scatter(
            [r["gen"] for r in ood_rows],
            [r["intent_err"] for r in ood_rows],
            c="#f9ab00",
            s=70,
            marker="s",
            zorder=5,
            label="test-ood (sealed)",
        )

    # optional stacked term contribution for last accepted
    # secondary info as text
    last_acc = [r for r in loop_rows if r["accepted"]]
    if last_acc:
        r = last_acc[-1]
        try:
            txt = (
                f"best intent_err={best_acc[-1]:.4f}\n"
                f"shape={float(r.get('shape_err', 0)):.3f}  "
                f"gen={float(r.get('gen_err', 0)):.3f}  "
                f"robust={float(r.get('robust_err', 0)):.3f}  "
                f"pars={float(r.get('parsimony_pen', 0)):.3f}"
            )
            ax.text(
                0.02,
                0.98,
                txt,
                transform=ax.transAxes,
                va="top",
                ha="left",
                fontsize=9,
                family="monospace",
                bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#dadce0", alpha=0.9),
            )
        except Exception:
            pass

    ax.set_xlabel("generation")
    ax.set_ylabel("intent_err (lower is better)")
    ax.set_title("autoregen — design-intent recovery loop")
    ax.set_ylim(0, min(1.05, max(errs.max() * 1.1, 0.3)))
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", framealpha=0.9)

    # cumulative wall hours on secondary x is busy; annotate total wall
    total_h = sum(r.get("wall_s", 0) for r in loop_rows) / 3600.0
    ax.set_xlabel(f"generation  (cum wall ≈ {total_h:.2f} h)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUT} ({len(loop_rows)} points)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
