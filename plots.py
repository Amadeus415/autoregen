#!/usr/bin/env python3
"""Charts for the CAD design-intent race.

Reads one or more results.tsv logs and writes PNGs that the README embeds.
The point of every chart is the same: the accepted frontier is a staircase,
and every discarded experiment stays visible.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from prepare import Row, parse_log, score_solver

FAMILY_NAMES = {
    "A": "box",
    "C": "cylinder",
    "D": "tube",
    "B": "plate + hole",
    "F": "offset hole",
    "E": "boss",
    "G": "offset boss",
    "H": "fillet",
    "I": "chamfer",
    "J": "counterbore",
    "K": "slot",
    "L": "hole pair",
}


ROOT = Path(__file__).resolve().parent
PLOTS = ROOT / "plots"

# Distinct on GitHub's white README background.
PALETTE = {
    "grok-4.5": "#1D9BF0",
    "gemini-3.7-flash": "#7C3AED",
    "gpt-5.6-terra": "#059669",
    "gpt-5.6-sol": "#F59E0B",
    "grok-4.6": "#64748B",
}

LABELS = {
    "grok-4.5": "Grok 4.5  ·  high  ·  grok CLI",
    "gemini-3.7-flash": "Gemini 3.7 Flash  ·  high  ·  antigravity",
    "gpt-5.6-terra": "GPT-5.6 Terra  ·  high  ·  Codex",
    "gpt-5.6-sol": "GPT-5.6 Sol  ·  medium  ·  Codex",
    "grok-4.6": "Grok 4.6  ·  medium  ·  grok CLI",
}
SHORT = {
    "grok-4.5": "Grok 4.5",
    "gemini-3.7-flash": "Gemini 3.7",
    "gpt-5.6-terra": "Terra",
    "gpt-5.6-sol": "Sol",
    "grok-4.6": "Grok 4.6",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "#FFFFFF",
            "axes.facecolor": "#F8FAFC",
            "axes.edgecolor": "#E2E8F0",
            "axes.labelcolor": "#0F172A",
            "axes.titlecolor": "#0F172A",
            "axes.grid": True,
            "grid.color": "#E2E8F0",
            "grid.linewidth": 0.8,
            "xtick.color": "#475569",
            "ytick.color": "#475569",
            "font.size": 11,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica Neue", "Arial"],
            "axes.titlesize": 14,
            "axes.titleweight": "semibold",
            "axes.labelsize": 11,
            "legend.frameon": False,
            "savefig.facecolor": "#FFFFFF",
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.25,
        }
    )


def _frontier(rows: list[Row]) -> tuple[list[int], list[float]]:
    xs: list[int] = []
    ys: list[float] = []
    best: float | None = None
    for row in rows:
        if row.status == "keep":
            best = row.intent_err
            xs.append(row.gen)
            ys.append(row.intent_err)
        elif best is not None:
            xs.append(row.gen)
            ys.append(best)
    return xs, ys


def summarize(rows: list[Row]) -> dict:
    agent = [r for r in rows if r.gen >= 1]
    keeps = [r for r in agent if r.status == "keep"]
    discards = [r for r in agent if r.status == "discard"]
    crashes = [r for r in agent if r.status == "crash"]
    start = rows[0].intent_err if rows else 1.0
    end = min((r.intent_err for r in rows if r.status == "keep"), default=start)
    return {
        "start": start,
        "end": end,
        "steps": len(agent),
        "keeps": len(keeps),
        "discards": len(discards),
        "crashes": len(crashes),
        "keep_rate": (len(keeps) / len(agent)) if agent else 0.0,
        "solved": end <= 1e-9,
    }


def _load_named(items: list[tuple[str, Path]]) -> list[tuple[str, list[Row], str]]:
    loaded = []
    for name, path in items:
        if not path.is_file():
            raise FileNotFoundError(path)
        loaded.append((name, parse_log(path), PALETTE.get(name, "#334155")))
    return loaded


def write_race(runs: list[tuple[str, list[Row], str]], out: Path) -> None:
    _style()
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    for name, rows, color in runs:
        gens = [r.gen for r in rows]
        errs = [r.intent_err for r in rows]
        ax.scatter(
            gens,
            errs,
            s=36,
            c=color,
            alpha=0.28,
            linewidths=0,
            zorder=2,
        )
        fx, fy = _frontier(rows)
        if fx:
            ax.step(
                fx,
                fy,
                where="post",
                color=color,
                lw=2.4,
                zorder=3,
                label=LABELS.get(name, name),
            )
            ax.scatter([fx[0]], [fy[0]], c=color, s=42, zorder=4)
            ax.scatter([fx[-1]], [fy[-1]], c=color, s=56, zorder=4)
            stats = summarize(rows)
            ax.annotate(
                f"{stats['end']:.3f}",
                (fx[-1], fy[-1]),
                textcoords="offset points",
                xytext=(8, 6 if stats["end"] > 0.01 else 10),
                color=color,
                fontsize=9,
                fontweight="semibold",
            )
    ax.set_xlabel("generation")
    ax.set_ylabel("intent_err   (lower is better)")
    ax.set_title("Recovering design intent — accepted frontier vs every attempt")
    peak = max(r.intent_err for _, rows, _ in runs for r in rows)
    xmax = max(r.gen for _, rows, _ in runs for r in rows)
    ax.set_ylim(-0.01, max(0.30, peak + 0.04))
    ax.set_xlim(-0.6, xmax + 0.8)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    if xmax > 20:
        ax.axvline(20, color="#94A3B8", ls="--", lw=1.0, zorder=1)
        ax.text(
            20.2,
            ax.get_ylim()[1] * 0.92,
            "20-gen budget",
            color="#64748B",
            fontsize=9,
        )
    ax.legend(loc="upper right", fontsize=10)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)


def write_progress(name: str, rows: list[Row], color: str, out: Path) -> None:
    _style()
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    ax.scatter(
        [r.gen for r in rows],
        [r.intent_err for r in rows],
        c="#94A3B8",
        s=32,
        zorder=2,
        label="every experiment",
    )
    keeps = [r for r in rows if r.status == "keep"]
    discards = [r for r in rows if r.status == "discard"]
    crashes = [r for r in rows if r.status == "crash"]
    if discards:
        ax.scatter(
            [r.gen for r in discards],
            [r.intent_err for r in discards],
            c="#94A3B8",
            s=32,
            zorder=3,
        )
    if crashes:
        ax.scatter(
            [r.gen for r in crashes],
            [r.intent_err for r in crashes],
            c="#EF4444",
            s=40,
            marker="x",
            zorder=4,
            label="crash",
        )
    fx, fy = _frontier(rows)
    if fx:
        ax.step(fx, fy, where="post", color=color, lw=2.4, label="accepted frontier")
        ax.scatter(
            [r.gen for r in keeps],
            [r.intent_err for r in keeps],
            c=color,
            s=42,
            zorder=5,
        )
    stats = summarize(rows)
    ax.set_xlabel("generation")
    ax.set_ylabel("intent_err   (lower is better)")
    ax.set_title(LABELS.get(name, name))
    ax.set_ylim(-0.01, max(0.30, max(r.intent_err for r in rows) + 0.02))
    ax.set_xlim(-0.6, max(r.gen for r in rows) + 0.8)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.text(
        0.98,
        0.06,
        f"{stats['start']:.3f}  ->  {stats['end']:.3f}"
        f"    {stats['keeps']} keeps / {stats['steps']} tries",
        transform=ax.transAxes,
        ha="right",
        color="#334155",
        fontsize=10,
    )
    ax.legend(loc="upper right")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)


def write_summary(runs: list[tuple[str, list[Row], str]], out: Path) -> None:
    _style()
    names = [n for n, _, _ in runs]
    colors = [c for _, _, c in runs]
    stats = [summarize(rows) for _, rows, _ in runs]

    fig, axes = plt.subplots(1, 3, figsize=(11.2, 4.2))
    x = range(len(names))

    bars = axes[0].bar(x, [s["end"] for s in stats], color=colors, width=0.62)
    axes[0].set_title("Final intent_err")
    axes[0].set_ylabel("lower is better")
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels([SHORT.get(n, n) for n in names], fontsize=9)
    axes[0].set_ylim(0, max(0.05, max(s["end"] for s in stats) * 1.35))
    for bar, s in zip(bars, stats):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.002,
            f"{s['end']:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="semibold",
        )

    axes[1].bar(x, [s["keeps"] for s in stats], color=colors, width=0.62)
    axes[1].set_title("Accepted steps")
    axes[1].set_ylabel("keeps")
    axes[1].set_xticks(list(x))
    axes[1].set_xticklabels([SHORT.get(n, n) for n in names], fontsize=9)

    axes[2].bar(
        x, [100 * s["keep_rate"] for s in stats], color=colors, width=0.62
    )
    axes[2].set_title("Keep rate")
    axes[2].set_ylabel("% of generations accepted")
    axes[2].set_xticks(list(x))
    axes[2].set_xticklabels([SHORT.get(n, n) for n in names], fontsize=9)
    axes[2].set_ylim(0, 100)

    fig.suptitle("Same hill, four researchers", fontsize=14, fontweight="semibold")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)


def write_loop_diagram(out: Path) -> None:
    _style()
    fig, ax = plt.subplots(figsize=(11.2, 3.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4)
    ax.axis("off")
    boxes = [
        (0.3, 1.45, "1  Researcher\nreads the log"),
        (3.2, 1.45, "2  One edit to\nsolver.py"),
        (6.1, 1.45, "3  Immutable\nheld-out score"),
        (9.0, 1.45, "4  Keep if better\nelse reset"),
    ]
    fills = ["#DBEAFE", "#D1FAE5", "#FEF3C7", "#FCE7F3"]
    edges = ["#1D4ED8", "#059669", "#D97706", "#BE185D"]
    for (x, y, text), fill, edge in zip(boxes, fills, edges):
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                2.5,
                1.5,
                boxstyle="round,pad=0.08,rounding_size=0.18",
                facecolor=fill,
                edgecolor=edge,
                linewidth=1.4,
            )
        )
        ax.text(x + 1.25, y + 0.75, text, ha="center", va="center", fontsize=11)
    for x in (2.8, 5.7, 8.6):
        ax.add_patch(
            FancyArrowPatch(
                (x, 2.2),
                (x + 0.4, 2.2),
                arrowstyle="-|>",
                mutation_scale=12,
                color="#334155",
                lw=1.4,
            )
        )
    ax.annotate(
        "",
        xy=(1.55, 1.45),
        xytext=(10.25, 1.45),
        arrowprops=dict(
            arrowstyle="-|>",
            color="#1D9BF0",
            lw=1.6,
            connectionstyle="arc3,rad=-0.28",
        ),
    )
    ax.text(
        6.0,
        0.45,
        "accepted solver is the next start  ·  rejects stay in the log",
        ha="center",
        color="#1D4ED8",
        fontsize=11,
    )
    ax.set_title("The loop  —  one hypothesis per generation")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)


def _family_order(data_root: Path) -> list[tuple[str, str]]:
    import json

    hidden = data_root / "data" / "hidden"
    by_key: dict[str, tuple[str, str]] = {}
    for spec_path in hidden.glob("*/spec.json"):
        spec = json.loads(spec_path.read_text())
        key = spec["family"]
        by_key[key] = (spec_path.parent.name, FAMILY_NAMES.get(key, key))
    order = ["A", "C", "D", "B", "F", "E", "G", "H", "I", "J", "K", "L"]
    return [by_key[k] for k in order if k in by_key]


def write_families(
    solvers: list[tuple[str, Path]],
    data_root: Path,
    out: Path,
) -> None:
    """Heatmap of per-task error for the final solver of each arm."""
    _style()
    families = _family_order(data_root)
    matrix: list[list[float]] = []
    for _name, solver in solvers:
        scored = score_solver(solver, data_root)
        matrix.append([scored.per_task[tid] for tid, _label in families])

    fig, ax = plt.subplots(figsize=(11.2, 3.6 + 0.4 * len(solvers)))
    im = ax.imshow(matrix, cmap="RdYlGn_r", vmin=0.0, vmax=0.50, aspect="auto")
    ax.set_xticks(range(len(families)))
    ax.set_xticklabels([label for _tid, label in families], rotation=35, ha="right")
    ax.set_yticks(range(len(solvers)))
    ax.set_yticklabels([SHORT.get(n, n) for n, _ in solvers])
    ax.set_title("Which families did the final solver recover?")
    ax.grid(False)
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            ax.text(
                j,
                i,
                "0" if value <= 1e-9 else f"{value:.3f}",
                ha="center",
                va="center",
                color="#F8FAFC" if value < 0.12 or value > 0.38 else "#0F172A",
                fontsize=8.5,
                fontweight="semibold",
            )
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("per-task intent_err")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)


def write_all(
    items: list[tuple[str, Path]],
    dest: Path,
    *,
    solvers: list[tuple[str, Path]] | None = None,
    data_root: Path | None = None,
) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    runs = _load_named(items)
    written = [dest / "loop.png", dest / "race.png", dest / "summary.png"]
    write_loop_diagram(written[0])
    write_race(runs, written[1])
    write_summary(runs, written[2])
    for name, rows, color in runs:
        path = dest / f"progress-{name}.png"
        write_progress(name, rows, color, path)
        written.append(path)
    if solvers and data_root is not None:
        fam = dest / "families.png"
        write_families(solvers, data_root, fam)
        written.append(fam)
    return written


def default_items() -> list[tuple[str, Path]]:
    candidates = [
        ("grok-4.5", ROOT / "examples" / "grok-4.5-high.tsv"),
        ("gemini-3.7-flash", ROOT / "examples" / "gemini-3.7-flash-high.tsv"),
        ("gpt-5.6-terra", ROOT / "examples" / "gpt-5.6-terra-high.tsv"),
        ("gpt-5.6-sol", ROOT / "examples" / "gpt-5.6-sol-medium.tsv"),
    ]
    found = [(n, p) for n, p in candidates if p.is_file()]
    if found:
        return found
    legacy = ROOT / "examples" / "grok-4.6-medium.tsv"
    if legacy.is_file():
        return [("grok-4.6", legacy)]
    raise FileNotFoundError("no example logs under examples/")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draw the autoregen race")
    parser.add_argument("--out", type=Path, default=PLOTS)
    parser.add_argument(
        "--log",
        action="append",
        nargs=2,
        metavar=("NAME", "PATH"),
        help="repeatable: --log grok-4.5 examples/grok-4.5-high.tsv",
    )
    args = parser.parse_args(argv)
    items = (
        [(name, Path(path)) for name, path in args.log]
        if args.log
        else default_items()
    )
    solvers: list[tuple[str, Path]] = []
    data_root: Path | None = None
    for name, path in items:
        run_dir = Path(
            {
                "grok-4.5": ROOT / "runs" / "grok-4.5",
                "gemini-3.7-flash": ROOT / "runs" / "gemini-3.7-flash",
                "gpt-5.6-terra": ROOT / "runs" / "codex-terra-high",
                "gpt-5.6-sol": ROOT / "runs" / "codex-sol-medium",
            }.get(name, path.parent)
        )
        solver = run_dir / "solver.py"
        sealed = run_dir.parent / f"{run_dir.name}.sealed"
        if solver.is_file():
            solvers.append((name, solver))
        if sealed.is_dir() and (sealed / "data" / "hidden").is_dir():
            data_root = sealed
    written = write_all(
        items,
        args.out,
        solvers=solvers or None,
        data_root=data_root,
    )
    for path in written:
        print(f"wrote\t{path}")
    for name, path in items:
        rows = parse_log(path)
        s = summarize(rows)
        print(
            f"{name}\t{s['start']:.8f}\t{s['end']:.8f}\t"
            f"keeps={s['keeps']}\tsteps={s['steps']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
