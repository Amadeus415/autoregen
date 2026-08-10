#!/usr/bin/env python3
"""Plot autoregen results: grey dots, best-so-far ratchet, test/OOD markers, noise band."""

from __future__ import annotations

import argparse
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


def _draw_recursive_cycle(ax) -> None:
    """Render the actual closed loop used by each benchmark arm."""
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    boxes = [
        (0.25, 2.0, "1  Researcher model\nreads prior results"),
        (2.75, 2.0, "2  One solver.py\nhypothesis + edit"),
        (5.25, 2.0, "3  Immutable CAD\nevaluation"),
        (7.75, 2.0, "4  Paired gate\naccept or revert"),
    ]
    colors = ["#e8f0fe", "#e6f4ea", "#fef7e0", "#fce8e6"]
    for (x, y, label), color in zip(boxes, colors):
        ax.add_patch(
            plt.Rectangle((x, y), 2.0, 1.0, facecolor=color, edgecolor="#5f6368", linewidth=1.2)
        )
        ax.text(x + 1.0, y + 0.5, label, ha="center", va="center", fontsize=8.5)
    for x in (2.25, 4.75, 7.25):
        ax.annotate("", xy=(x + 0.45, 2.5), xytext=(x + 0.05, 2.5), arrowprops=dict(arrowstyle="->", lw=1.6))
    ax.annotate(
        "accepted solver becomes the next generation",
        xy=(1.25, 1.95),
        xytext=(8.75, 1.25),
        ha="center",
        fontsize=8.5,
        color="#1a73e8",
        arrowprops=dict(arrowstyle="->", lw=2.0, color="#1a73e8", connectionstyle="arc3,rad=-0.32"),
    )
    ax.text(
        5,
        4.1,
        "Recursive self-improvement is the feedback path — not a smoothed trend line",
        ha="center",
        va="center",
        fontsize=10,
        weight="bold",
    )


def plot_benchmark(run_dir: Path, out: Path) -> int:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"benchmark manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    arms = manifest.get("arms", {})
    if not arms:
        raise ValueError("benchmark manifest has no arms")

    fig = plt.figure(figsize=(14.5, 9))
    grid = fig.add_gridspec(
        2,
        2,
        width_ratios=[4.5, 1.45],
        height_ratios=[3.2, 1.55],
        hspace=0.28,
        wspace=0.08,
    )
    ax = fig.add_subplot(grid[0, 0])
    summary_ax = fig.add_subplot(grid[0, 1])
    cycle_ax = fig.add_subplot(grid[1, :])
    summary_ax.axis("off")
    colors = ["#1a73e8", "#a142f4", "#00897b", "#e37400"]

    summary_lines: list[tuple[str, str, str]] = []
    max_generation = 0.0
    for arm_index, (color, (arm_name, summary)) in enumerate(zip(colors, arms.items())):
        rows = [r for r in load_tsv(run_dir / arm_name / "results.tsv") if r.get("split") == "dev"]
        if not rows:
            continue
        # One canonical baseline plus every candidate generation.
        baseline = float(summary["baseline_intent_err"])
        candidates = sorted((r for r in rows if r["gen"] > 0), key=lambda r: r["gen"])
        gens = np.array([0] + [r["gen"] for r in candidates], dtype=float)
        max_generation = max(max_generation, float(gens[-1]))
        errs = np.array([baseline] + [r["intent_err"] for r in candidates], dtype=float)
        accepted = np.array([1] + [r["accepted"] for r in candidates], dtype=int)
        frontier = [baseline]
        current = baseline
        for row in candidates:
            if row["accepted"]:
                current = row["intent_err"]
            frontier.append(current)

        label = summary.get("label", arm_name)
        ax.plot(gens, errs, color=color, alpha=0.32, linewidth=1.0)
        ax.scatter(gens, errs, color=color, alpha=0.55, s=42, label=f"{label} candidates")
        ax.step(gens, frontier, where="post", color=color, linewidth=2.8, label=f"{label} accepted frontier")
        rejected = accepted == 0
        if rejected.any():
            ax.scatter(gens[rejected], errs[rejected], color=color, marker="x", s=70)

        validation = summary.get("validation", {})
        final_x = gens[-1] + 0.14 + arm_index * 0.11
        if "test" in validation:
            ax.scatter(
                final_x,
                validation["test"]["intent_err"],
                facecolor="#d93025",
                edgecolor=color,
                linewidth=2.0,
                marker="D",
                s=86,
                zorder=7,
            )
        if "test-ood" in validation:
            ax.scatter(
                final_x,
                validation["test-ood"]["intent_err"],
                facecolor="#f9ab00",
                edgecolor=color,
                linewidth=2.0,
                marker="s",
                s=86,
                zorder=7,
            )
        summary_lines.append(
            (
                color,
                label,
                f"dev  {summary['best_intent_err']:.4f}\n"
                f"test  {validation.get('test', {}).get('intent_err', float('nan')):.4f}\n"
                f"OOD  {validation.get('test-ood', {}).get('intent_err', float('nan')):.4f}\n"
                f"gain  {summary['relative_improvement_pct']:.1f}%\n"
                f"accepted  {summary['accepted_generations']}/{summary['candidate_generations']}",
            )
        )

    settings = manifest.get("settings", {})
    ax.set_title(
        "autoregen recursive self-improvement benchmark\n"
        f"same baseline · {settings.get('dev_tasks', '?')} dev tasks · "
        f"{settings.get('generations', '?')} bounded generations per model"
    )
    ax.set_xlabel("recursive generation (accepted solver feeds the next turn)")
    ax.set_ylabel("intent_err (lower is better)")
    ax.grid(True, alpha=0.25)
    ax.set_ylim(bottom=0)
    ax.set_xlim(-0.08, max_generation + 0.55)
    ax.scatter([], [], facecolor="#d93025", edgecolor="#5f6368", marker="D", s=65, label="sealed test")
    ax.scatter([], [], facecolor="#f9ab00", edgecolor="#5f6368", marker="s", s=65, label="sealed OOD")
    ax.scatter([], [], color="#5f6368", marker="x", s=55, label="rejected candidate")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="upper left", fontsize=7.5, framealpha=0.92, ncol=2)

    summary_ax.text(0.02, 0.98, "Validated outcome", va="top", fontsize=12, weight="bold")
    y = 0.90
    summary_step = min(0.39, 0.80 / max(len(summary_lines), 1))
    for color, label, metrics in summary_lines:
        summary_ax.text(0.02, y, label, va="top", color=color, fontsize=9.5, weight="bold")
        summary_ax.text(0.05, y - 0.07, metrics, va="top", fontsize=8.5, family="monospace", linespacing=1.25)
        y -= summary_step
    audited = manifest.get("independent_audit", {}).get("pass", False)
    status = (
        "AUDITED · VALID"
        if manifest.get("valid") and audited
        else ("VALID" if manifest.get("valid") else "INCOMPLETE")
    )
    status_color = "#188038" if manifest.get("valid") else "#d93025"
    summary_ax.text(0.02, 0.045, status, color=status_color, fontsize=11, weight="bold")
    summary_ax.text(
        0.02,
        0.005,
        "Quick profile; not a general leaderboard.",
        color="#5f6368",
        fontsize=7.5,
    )
    _draw_recursive_cycle(cycle_ax)
    fig.suptitle(f"Run {manifest.get('run_id', run_dir.name)}", x=0.99, y=0.995, ha="right", fontsize=8, color="#5f6368")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out} ({len(arms)} model arms)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-run", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    if args.benchmark_run is not None:
        return plot_benchmark(args.benchmark_run.resolve(), args.out.resolve())

    rows = load_tsv(TSV)
    if not rows:
        print("No results.tsv rows yet — nothing to plot")
        # empty placeholder
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.set_title("autoregen — intent_err (no data yet)")
        ax.set_xlabel("generation")
        ax.set_ylabel("intent_err (lower is better)")
        fig.savefig(args.out, dpi=140, bbox_inches="tight")
        print(f"Wrote {args.out}")
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

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    print(f"Wrote {args.out} ({len(loop_rows)} points)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
