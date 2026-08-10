#!/usr/bin/env python3
"""
prepare.py — IMMUTABLE harness entry point for autoregen.

Family generator, splits, scorer, sandbox, results logging, checksums.
The agent may NOT edit this file. Ownership enforced by loop.sh + HARNESS.sha256.

Usage:
  python prepare.py generate [--quick] [--seed 42]
  python prepare.py eval --split dev [--workers 4] [--max-tasks N]
  python prepare.py checksum [--write]
  python prepare.py verify-checksum
  python prepare.py gen0 [--quick]
  python prepare.py noise-floor [--split dev]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from harness.generator import generate_all
from harness.eval import (
    evaluate,
    append_results_tsv,
    sha256_file,
    sha256_tree,
    load_per_task_intent,
    RESULTS_HEADER,
)
from harness.scorer import paired_bootstrap_gate


def harness_paths(repo: Path) -> list:
    """Files covered by HARNESS.sha256."""
    paths = [
        repo / "prepare.py",
        repo / "harness",
    ]
    for generated in (repo / "data" / "families", repo / "data" / "gt"):
        if generated.exists():
            paths.append(generated)
    return paths


def cmd_generate(args: argparse.Namespace) -> int:
    data_root = REPO_ROOT / "data"
    sizes = None
    if args.quick:
        sizes = {"train": 12, "dev": 8, "test": 4, "test-ood": 2}
    elif args.sizes:
        # e.g. train:32,dev:8,test:8,test-ood:4
        sizes = {}
        for part in args.sizes.split(","):
            k, v = part.split(":")
            sizes[k.strip()] = int(v)
    counts = generate_all(data_root, seed=args.seed, sizes=sizes, quick=args.quick)
    print(json.dumps(counts, indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    result = evaluate(
        REPO_ROOT,
        split=args.split,
        solver_path=REPO_ROOT / "solver.py",
        workers=args.workers,
        resolution=args.resolution,
        n_points=args.n_points,
        robust_n=args.robust_n,
        seed=args.seed,
        max_tasks=args.max_tasks,
        wall_clock_cap_s=args.wall_cap,
        solver_timeout=args.solver_timeout,
        verbose=not args.quiet,
    )
    out_path = Path(args.out) if args.out else REPO_ROOT / "last_eval.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(f"Wrote {out_path}")
    print(f"intent_err={result.get('intent_err', 1.0):.6f}")

    if args.append_tsv:
        agg = result.get("aggregate", {})
        append_results_tsv(
            REPO_ROOT / "results.tsv",
            {
                "gen": args.gen,
                "sha": result.get("solver_sha", ""),
                "intent_err": result.get("intent_err", 1.0),
                "shape_err": agg.get("shape_err", 1.0),
                "gen_err": agg.get("gen_err", 1.0),
                "robust_err": agg.get("robust_err", 1.0),
                "parsimony_pen": agg.get("parsimony_pen", 1.0),
                "wall_s": result.get("wall_s", 0.0),
                "tokens": 0,
                "usd": 0.0,
                "accepted": args.accepted,
                "note": args.note or f"eval:{args.split}",
                "violations": ";".join(result.get("violations", [])[:5]),
                "split": args.split,
                "n_tasks": result.get("n_tasks", 0),
            },
        )
    return 0 if result.get("ok") else 1


def cmd_checksum(args: argparse.Namespace) -> int:
    digest = sha256_tree(harness_paths(REPO_ROOT))
    print(digest)
    if args.write:
        out = REPO_ROOT / "HARNESS.sha256"
        out.write_text(digest + "\n")
        print(f"Wrote {out}")
    return 0


def cmd_verify_checksum(args: argparse.Namespace) -> int:
    path = REPO_ROOT / "HARNESS.sha256"
    if not path.exists():
        print("HARNESS.sha256 missing — run: python prepare.py checksum --write", file=sys.stderr)
        return 2
    expected = path.read_text().strip().split()[0]
    actual = sha256_tree(harness_paths(REPO_ROOT))
    if expected != actual:
        print(f"HARNESS CHECKSUM MISMATCH\nexpected: {expected}\nactual:   {actual}", file=sys.stderr)
        return 1
    print("HARNESS.sha256 OK")
    return 0


def cmd_gen0(args: argparse.Namespace) -> int:
    """Run baseline solver twice and confirm determinism."""
    # ensure data exists
    dev = REPO_ROOT / "data" / "families" / "dev"
    if not dev.exists() or not any(dev.iterdir()):
        print("No dev data — generating quick set...")
        generate_all(
            REPO_ROOT / "data",
            seed=args.seed,
            sizes={"train": 8, "dev": min(args.max_tasks or 4, 8), "test": 2, "test-ood": 2}
            if args.quick
            else None,
            quick=args.quick,
        )
        cmd_checksum(argparse.Namespace(write=True))

    kwargs = dict(
        split="dev",
        workers=args.workers,
        resolution=args.resolution,
        n_points=args.n_points,
        robust_n=args.robust_n,
        seed=args.seed,
        max_tasks=args.max_tasks,
        wall_clock_cap_s=args.wall_cap,
        solver_timeout=args.solver_timeout,
        verbose=True,
    )
    print("=== Gen-0 run 1 ===")
    r1 = evaluate(REPO_ROOT, **kwargs)
    print("=== Gen-0 run 2 (determinism check) ===")
    r2 = evaluate(REPO_ROOT, **kwargs)

    e1, e2 = r1["intent_err"], r2["intent_err"]
    print(f"run1 intent_err={e1:.6f}")
    print(f"run2 intent_err={e2:.6f}")
    # allow tiny float noise
    if abs(e1 - e2) > 1e-9:
        # per-task check
        t1 = {t["family_id"]: t["intent_err"] for t in r1["per_task"]}
        t2 = {t["family_id"]: t["intent_err"] for t in r2["per_task"]}
        diffs = [k for k in t1 if abs(t1[k] - t2.get(k, 99)) > 1e-9]
        print(f"DETERMINISM FAIL: {len(diffs)} tasks differ: {diffs[:5]}", file=sys.stderr)
        ok = False
    else:
        print("Determinism OK (identical intent_err)")
        ok = True

    (REPO_ROOT / "last_eval.json").write_text(json.dumps(r1, indent=2))
    append_results_tsv(
        REPO_ROOT / "results.tsv",
        {
            "gen": 0,
            "sha": r1.get("solver_sha", ""),
            "intent_err": e1,
            "shape_err": r1["aggregate"]["shape_err"],
            "gen_err": r1["aggregate"]["gen_err"],
            "robust_err": r1["aggregate"]["robust_err"],
            "parsimony_pen": r1["aggregate"]["parsimony_pen"],
            "wall_s": r1["wall_s"],
            "tokens": 0,
            "usd": 0.0,
            "accepted": 1,
            "note": "gen0-baseline",
            "violations": "",
            "split": "dev",
            "n_tasks": r1["n_tasks"],
        },
    )
    # also dump per-task for bootstrap baseline
    (REPO_ROOT / "best_per_task.json").write_text(
        json.dumps(
            {
                "intent_err": e1,
                "per_task": r1["per_task"],
                "solver_sha": r1.get("solver_sha"),
            },
            indent=2,
        )
    )
    return 0 if ok else 1


def cmd_gate(args: argparse.Namespace) -> int:
    """Compare new eval vs best_per_task.json with paired bootstrap gate."""
    new = json.loads(Path(args.new_eval).read_text())
    best = json.loads(Path(args.best).read_text())
    old_scores = [t["intent_err"] for t in best["per_task"]]
    new_scores = [t["intent_err"] for t in new["per_task"]]
    # align by family_id
    old_map = {t["family_id"]: t["intent_err"] for t in best["per_task"]}
    new_map = {t["family_id"]: t["intent_err"] for t in new["per_task"]}
    ids = sorted(set(old_map) & set(new_map))
    old_scores = [old_map[i] for i in ids]
    new_scores = [new_map[i] for i in ids]
    gate = paired_bootstrap_gate(old_scores, new_scores, n_boot=args.n_boot, seed=args.seed)
    print(json.dumps(gate, indent=2))
    Path(args.out).write_text(json.dumps(gate, indent=2)) if args.out else None
    return 0 if gate["accept"] else 1


def cmd_noise_floor(args: argparse.Namespace) -> int:
    """Re-run current solver N times; report spread."""
    runs = []
    for i in range(args.n):
        print(f"=== Noise floor run {i+1}/{args.n} ===")
        r = evaluate(
            REPO_ROOT,
            split=args.split,
            workers=args.workers,
            resolution=args.resolution,
            n_points=args.n_points,
            robust_n=args.robust_n,
            seed=args.seed,  # same seed — should be identical if deterministic
            max_tasks=args.max_tasks,
            verbose=True,
        )
        runs.append(r["intent_err"])
    import numpy as np

    arr = np.array(runs)
    report = {
        "n": len(runs),
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "runs": runs,
    }
    print(json.dumps(report, indent=2))
    (REPO_ROOT / "noise_floor.json").write_text(json.dumps(report, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="autoregen immutable harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Synthesize task families")
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--quick", action="store_true", help="Tiny dataset for smoke tests")
    g.add_argument("--sizes", type=str, default=None, help="train:N,dev:N,...")
    g.set_defaults(func=cmd_generate)

    e = sub.add_parser("eval", help="Evaluate solver.py on a split")
    e.add_argument("--split", default="dev")
    e.add_argument("--workers", type=int, default=4)
    e.add_argument("--resolution", type=int, default=64)
    e.add_argument("--n-points", type=int, default=8000)
    e.add_argument("--robust-n", type=int, default=12)
    e.add_argument("--seed", type=int, default=0)
    e.add_argument("--max-tasks", type=int, default=None)
    e.add_argument("--wall-cap", type=float, default=None)
    e.add_argument("--solver-timeout", type=float, default=90.0)
    e.add_argument("--out", type=str, default=None)
    e.add_argument("--append-tsv", action="store_true")
    e.add_argument("--gen", type=int, default=-1)
    e.add_argument("--accepted", type=int, default=0)
    e.add_argument("--note", type=str, default="")
    e.add_argument("--quiet", action="store_true")
    e.set_defaults(func=cmd_eval)

    c = sub.add_parser("checksum", help="Compute harness checksum")
    c.add_argument("--write", action="store_true")
    c.set_defaults(func=cmd_checksum)

    v = sub.add_parser("verify-checksum", help="Verify HARNESS.sha256")
    v.set_defaults(func=cmd_verify_checksum)

    z = sub.add_parser("gen0", help="Run baseline twice; check determinism")
    z.add_argument("--quick", action="store_true")
    z.add_argument("--workers", type=int, default=2)
    z.add_argument("--resolution", type=int, default=64)
    z.add_argument("--n-points", type=int, default=8000)
    z.add_argument("--robust-n", type=int, default=8)
    z.add_argument("--seed", type=int, default=0)
    z.add_argument("--max-tasks", type=int, default=None)
    z.add_argument("--wall-cap", type=float, default=None)
    z.add_argument("--solver-timeout", type=float, default=90.0)
    z.set_defaults(func=cmd_gen0)

    gate = sub.add_parser("gate", help="Paired bootstrap statistical gate")
    gate.add_argument("--new-eval", required=True)
    gate.add_argument("--best", default=str(REPO_ROOT / "best_per_task.json"))
    gate.add_argument("--n-boot", type=int, default=2000)
    gate.add_argument("--seed", type=int, default=0)
    gate.add_argument("--out", type=str, default=None)
    gate.set_defaults(func=cmd_gate)

    nf = sub.add_parser("noise-floor", help="Measure score spread of unchanged solver")
    nf.add_argument("--n", type=int, default=3)
    nf.add_argument("--split", default="dev")
    nf.add_argument("--workers", type=int, default=2)
    nf.add_argument("--resolution", type=int, default=64)
    nf.add_argument("--n-points", type=int, default=8000)
    nf.add_argument("--robust-n", type=int, default=8)
    nf.add_argument("--seed", type=int, default=0)
    nf.add_argument("--max-tasks", type=int, default=None)
    nf.set_defaults(func=cmd_noise_floor)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
