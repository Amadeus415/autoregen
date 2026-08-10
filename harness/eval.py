"""Evaluate solver.py on a data split. Parallel workers, results aggregation."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import tempfile
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import scorer
from .sandbox import run_solver_on_task, static_check_source
from .scorer import TermBreakdown, score_task, score_split, paired_bootstrap_gate


def list_tasks(families_root: Path, split: str) -> List[Path]:
    d = families_root / split
    if not d.exists():
        return []
    tasks = sorted([p for p in d.iterdir() if p.is_dir() and (p / "target.step").exists()])
    return tasks


def _eval_one(
    task_dir: str,
    gt_dir: str,
    solver_path: str,
    scratch_root: str,
    resolution: int,
    n_points: int,
    robust_n: int,
    seed: int,
    solver_timeout: float,
) -> Dict[str, Any]:
    task_dir_p = Path(task_dir)
    gt_dir_p = Path(gt_dir)
    solver_path_p = Path(solver_path)
    scratch = Path(scratch_root) / task_dir_p.name
    scratch.mkdir(parents=True, exist_ok=True)

    family_id = task_dir_p.name
    t0 = time.time()
    build_src, violations, solve_wall = run_solver_on_task(
        solver_path_p,
        task_dir_p,
        scratch,
        timeout_s=solver_timeout,
        repo_root=solver_path_p.parent,
    )
    if build_src is None:
        bd = TermBreakdown(
            shape_err=1.0,
            gen_err=1.0,
            robust_err=1.0,
            parsimony_pen=1.0,
            intent_err=1.0,
            flags=violations + ["no_build_src"],
            valid_gate_fail=True,
        )
        return {
            "family_id": family_id,
            "breakdown": asdict(bd),
            "violations": violations,
            "wall_s": time.time() - t0,
            "solve_wall_s": solve_wall,
        }

    try:
        bd = score_task(
            build_src,
            gt_dir_p,
            task_dir_p,
            resolution=resolution,
            n_points=n_points,
            robust_n=robust_n,
            seed=seed,
        )
        if violations:
            bd.flags.extend(violations)
    except Exception as e:
        bd = TermBreakdown(
            shape_err=1.0,
            gen_err=1.0,
            robust_err=1.0,
            parsimony_pen=1.0,
            intent_err=1.0,
            flags=[f"score_exception:{e}", traceback.format_exc()[-300:]],
            valid_gate_fail=True,
        )

    return {
        "family_id": family_id,
        "breakdown": asdict(bd),
        "violations": violations,
        "wall_s": time.time() - t0,
        "solve_wall_s": solve_wall,
    }


def evaluate(
    repo_root: Path,
    split: str = "dev",
    solver_path: Optional[Path] = None,
    workers: int = 4,
    resolution: int = 64,
    n_points: int = 8000,
    robust_n: int = 12,
    seed: int = 0,
    max_tasks: Optional[int] = None,
    wall_clock_cap_s: Optional[float] = None,
    solver_timeout: float = 90.0,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Full split evaluation. Returns aggregate metrics + per-task breakdowns.
    """
    repo_root = Path(repo_root).resolve()
    solver_path = Path(solver_path or (repo_root / "solver.py")).resolve()
    families_root = repo_root / "data" / "families"
    gt_root = repo_root / "data" / "gt"

    tasks = list_tasks(families_root, split)
    if max_tasks is not None:
        tasks = tasks[:max_tasks]
    if not tasks:
        return {
            "ok": False,
            "error": f"no tasks for split={split}",
            "intent_err": 1.0,
            "per_task": [],
            "aggregate": score_split([]),
        }

    if verbose:
        print(f"Evaluating {len(tasks)} tasks on split={split} workers={workers}")

    scratch_root = Path(tempfile.mkdtemp(prefix=f"autoregen_eval_{split}_"))
    t_start = time.time()
    results: List[Dict[str, Any]] = []

    work = []
    for i, td in enumerate(tasks):
        gd = gt_root / split / td.name
        work.append(
            dict(
                task_dir=str(td),
                gt_dir=str(gd),
                solver_path=str(solver_path),
                scratch_root=str(scratch_root),
                resolution=resolution,
                n_points=n_points,
                robust_n=robust_n,
                seed=seed + i * 17,
                solver_timeout=solver_timeout,
            )
        )

    # Use threads if workers==1 for easier debugging; else processes
    if workers <= 1:
        for w in work:
            if wall_clock_cap_s and (time.time() - t_start) > wall_clock_cap_s:
                if verbose:
                    print("Wall-clock cap hit; remaining tasks score 1.0")
                # pad failures
                remaining = len(work) - len(results)
                for j in range(remaining):
                    results.append(
                        {
                            "family_id": Path(work[len(results)]["task_dir"]).name,
                            "breakdown": asdict(
                                TermBreakdown(1, 1, 1, 1, 1, flags=["wall_cap"], valid_gate_fail=True)
                            ),
                            "violations": ["wall_cap"],
                            "wall_s": 0.0,
                            "solve_wall_s": 0.0,
                        }
                    )
                break
            r = _eval_one(**w)
            results.append(r)
            if verbose:
                ie = r["breakdown"]["intent_err"]
                print(f"  [{len(results)}/{len(tasks)}] {r['family_id'][:40]} intent_err={ie:.4f}")
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_eval_one, **w): w for w in work}
            for fut in concurrent.futures.as_completed(futs):
                if wall_clock_cap_s and (time.time() - t_start) > wall_clock_cap_s:
                    if verbose:
                        print("Wall-clock cap hit")
                    break
                try:
                    r = fut.result()
                except Exception as e:
                    w = futs[fut]
                    r = {
                        "family_id": Path(w["task_dir"]).name,
                        "breakdown": asdict(
                            TermBreakdown(1, 1, 1, 1, 1, flags=[f"worker_crash:{e}"], valid_gate_fail=True)
                        ),
                        "violations": [f"worker_crash:{e}"],
                        "wall_s": 0.0,
                        "solve_wall_s": 0.0,
                    }
                results.append(r)
                if verbose and len(results) % max(1, len(tasks) // 10) == 0:
                    print(f"  progress {len(results)}/{len(tasks)}")

    # sort by family_id for determinism
    results.sort(key=lambda r: r["family_id"])

    pairs = [
        (r["family_id"], TermBreakdown(**{k: r["breakdown"][k] for k in TermBreakdown.__dataclass_fields__ if k in r["breakdown"]}))
        for r in results
    ]
    # rebuild TermBreakdown carefully
    pairs = []
    for r in results:
        b = r["breakdown"]
        pairs.append(
            (
                r["family_id"],
                TermBreakdown(
                    shape_err=b["shape_err"],
                    gen_err=b["gen_err"],
                    robust_err=b["robust_err"],
                    parsimony_pen=b["parsimony_pen"],
                    intent_err=b["intent_err"],
                    member_shape_errs=b.get("member_shape_errs", []),
                    flags=b.get("flags", []),
                    n_faces_pred=b.get("n_faces_pred", 0),
                    n_faces_gt=b.get("n_faces_gt", 0),
                    valid_gate_fail=b.get("valid_gate_fail", False),
                ),
            )
        )
    agg = score_split(pairs)
    wall = time.time() - t_start
    violations_all = []
    for r in results:
        for v in r.get("violations", []):
            violations_all.append(f"{r['family_id']}:{v}")

    out = {
        "ok": True,
        "split": split,
        "intent_err": agg["intent_err"],
        "aggregate": agg,
        "per_task": [
            {
                "family_id": r["family_id"],
                "intent_err": r["breakdown"]["intent_err"],
                "shape_err": r["breakdown"]["shape_err"],
                "gen_err": r["breakdown"]["gen_err"],
                "robust_err": r["breakdown"]["robust_err"],
                "parsimony_pen": r["breakdown"]["parsimony_pen"],
                "flags": r["breakdown"].get("flags", []),
                "violations": r.get("violations", []),
                "wall_s": r.get("wall_s", 0.0),
            }
            for r in results
        ],
        "wall_s": wall,
        "n_tasks": len(results),
        "violations": violations_all,
        "solver_sha": sha256_file(solver_path),
        "resolution": resolution,
        "seed": seed,
    }
    if verbose:
        print(
            f"Done split={split} intent_err={agg['intent_err']:.4f} "
            f"shape={agg['shape_err']:.3f} gen={agg['gen_err']:.3f} "
            f"robust={agg['robust_err']:.3f} pars={agg['parsimony_pen']:.3f} "
            f"wall={wall:.1f}s"
        )
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(paths: Sequence[Path]) -> str:
    """Deterministic hash over a list of files (sorted by path)."""
    h = hashlib.sha256()
    files: List[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            for root, _, fnames in os.walk(p):
                for fn in fnames:
                    files.append(Path(root) / fn)
    for fp in sorted(files, key=lambda x: str(x.resolve())):
        rel = str(fp.resolve())
        h.update(rel.encode())
        h.update(b"\0")
        h.update(sha256_file(fp).encode())
        h.update(b"\0")
    return h.hexdigest()


RESULTS_HEADER = (
    "gen\tsha\tintent_err\tshape_err\tgen_err\trobust_err\tparsimony_pen\t"
    "wall_s\ttokens\tusd\taccepted\tnote\tviolations\tsplit\tn_tasks\n"
)


def append_results_tsv(path: Path, row: Dict[str, Any]) -> None:
    path = Path(path)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a") as f:
        if write_header:
            f.write(RESULTS_HEADER)
        f.write(
            "{gen}\t{sha}\t{intent_err:.6f}\t{shape_err:.6f}\t{gen_err:.6f}\t"
            "{robust_err:.6f}\t{parsimony_pen:.6f}\t{wall_s:.2f}\t{tokens}\t{usd}\t"
            "{accepted}\t{note}\t{violations}\t{split}\t{n_tasks}\n".format(
                gen=row.get("gen", 0),
                sha=row.get("sha", "")[:12],
                intent_err=float(row.get("intent_err", 1.0)),
                shape_err=float(row.get("shape_err", 1.0)),
                gen_err=float(row.get("gen_err", 1.0)),
                robust_err=float(row.get("robust_err", 1.0)),
                parsimony_pen=float(row.get("parsimony_pen", 1.0)),
                wall_s=float(row.get("wall_s", 0.0)),
                tokens=row.get("tokens", 0),
                usd=row.get("usd", 0.0),
                accepted=int(bool(row.get("accepted", False))),
                note=str(row.get("note", "")).replace("\t", " ").replace("\n", " ")[:200],
                violations=str(row.get("violations", "")).replace("\t", " ")[:200],
                split=row.get("split", "dev"),
                n_tasks=row.get("n_tasks", 0),
            )
        )


def load_per_task_intent(eval_result: Dict[str, Any]) -> List[float]:
    return [t["intent_err"] for t in eval_result.get("per_task", [])]
