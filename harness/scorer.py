"""intent_err scorer: shape / gen / robust / parsimony terms."""

from __future__ import annotations

import json
import math
import traceback
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import geom
from .generator import ParamSpec, cast_params, load_build_fn


# weights from design spec v0
W_SHAPE = 0.35
W_GEN = 0.45
W_ROBUST = 0.15
W_PARSIMONY = 0.05

DEFAULT_RESOLUTION = 64  # 128 is heavy; 64 for dev loop speed, override on test
DEFAULT_N_POINTS = 8000
DEFAULT_TAU = 0.05
ROBUST_N = 12
ROBUST_PERTURB_FRAC = 0.15


@dataclass
class TermBreakdown:
    shape_err: float
    gen_err: float
    robust_err: float
    parsimony_pen: float
    intent_err: float
    member_shape_errs: List[float] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    n_faces_pred: int = 0
    n_faces_gt: int = 0
    valid_gate_fail: bool = False


def clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def latin_hypercube(n: int, d: int, rng: np.random.Generator) -> np.ndarray:
    """Simple LHS in [0, 1]^d."""
    h = np.zeros((n, d))
    for j in range(d):
        perm = rng.permutation(n)
        h[:, j] = (perm + rng.random(n)) / n
    return h


def perturb_params(
    base: Dict[str, float],
    param_specs: List[dict],
    n: int = ROBUST_N,
    frac: float = ROBUST_PERTURB_FRAC,
    seed: int = 0,
) -> List[Dict[str, float]]:
    rng = np.random.default_rng(seed)
    names = [p["name"] for p in param_specs]
    types = {p["name"]: p["type"] for p in param_specs}
    ranges = {p["name"]: p["range"] for p in param_specs}
    d = len(names)
    lhs = latin_hypercube(n, d, rng)
    out = []
    for i in range(n):
        vec = {}
        for j, name in enumerate(names):
            lo, hi = ranges[name]
            center = base[name]
            if types[name] == "int":
                # ±1 on integer params (mapped via LHS to {-1,0,+1} roughly)
                delta = int(np.round((lhs[i, j] - 0.5) * 2))  # -1,0,1-ish
                val = int(round(center)) + delta
                val = int(np.clip(val, int(lo), int(hi)))
                vec[name] = float(val)
            else:
                span = abs(center) * frac
                # map lhs [0,1] -> [-span, +span]
                delta = (lhs[i, j] * 2 - 1) * span
                val = float(np.clip(center + delta, lo, hi))
                vec[name] = val
        out.append(vec)
    return out


def parsimony_penalty(n_faces_pred: int, n_faces_gt: int) -> float:
    if n_faces_gt <= 0:
        return 1.0 if n_faces_pred > 0 else 0.0
    return clamp01((n_faces_pred / n_faces_gt - 1.0) / 4.0)


def score_member(
    pred_build: Callable,
    gt_build: Callable,
    vec: Dict[str, float],
    param_specs: List[dict],
    resolution: int,
    n_points: int,
    seed: int,
) -> Tuple[float, Optional[Any], Optional[Any], str]:
    """Returns (shape_err, pred_solid, gt_solid, flag)."""
    specs_as = [
        type("P", (), {"name": p["name"], "type": p["type"], "unit": p.get("unit", "mm"), "range": tuple(p["range"]), "default": 0.0})()
        for p in param_specs
    ]
    # simpler cast
    kwargs = {}
    for p in param_specs:
        v = vec[p["name"]]
        kwargs[p["name"]] = int(round(v)) if p["type"] == "int" else float(v)

    try:
        gt_solid = gt_build(**kwargs)
    except Exception as e:
        return 1.0, None, None, f"gt_build_fail:{e}"

    try:
        pred_solid = pred_build(**kwargs)
    except Exception as e:
        return 1.0, None, gt_solid, f"pred_build_fail:{type(e).__name__}"

    if not geom.is_valid_solid(pred_solid):
        return 1.0, pred_solid, gt_solid, "pred_invalid"

    try:
        err = geom.shape_error(
            pred_solid,
            gt_solid,
            resolution=resolution,
            n_points=n_points,
            tau=DEFAULT_TAU,
            seed=seed,
        )
        return float(err), pred_solid, gt_solid, "ok"
    except Exception as e:
        return 1.0, pred_solid, gt_solid, f"score_fail:{type(e).__name__}"


def score_task(
    pred_src: str,
    gt_dir: Path,
    task_dir: Path,
    resolution: int = DEFAULT_RESOLUTION,
    n_points: int = DEFAULT_N_POINTS,
    robust_n: int = ROBUST_N,
    seed: int = 0,
) -> TermBreakdown:
    """
    Score a submitted build-module source against sealed GT for one task.
    """
    flags: List[str] = []

    # validity gate: import
    try:
        pred_build = load_build_fn(pred_src)
    except Exception as e:
        return TermBreakdown(
            shape_err=1.0,
            gen_err=1.0,
            robust_err=1.0,
            parsimony_pen=1.0,
            intent_err=1.0,
            flags=[f"import_fail:{e}"],
            valid_gate_fail=True,
        )

    members_path = gt_dir / "members.json"
    meta_path = gt_dir / "meta.json"
    program_path = gt_dir / "program.py"
    params_path = task_dir / "params.json"

    if not members_path.exists() or not program_path.exists():
        return TermBreakdown(
            shape_err=1.0,
            gen_err=1.0,
            robust_err=1.0,
            parsimony_pen=1.0,
            intent_err=1.0,
            flags=["missing_gt"],
            valid_gate_fail=True,
        )

    members = json.loads(members_path.read_text())
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    params_doc = json.loads(params_path.read_text())
    param_specs = params_doc["params"]
    gt_src = program_path.read_text()
    try:
        gt_build = load_build_fn(gt_src)
    except Exception as e:
        return TermBreakdown(
            shape_err=1.0,
            gen_err=1.0,
            robust_err=1.0,
            parsimony_pen=1.0,
            intent_err=1.0,
            flags=[f"gt_import_fail:{e}"],
            valid_gate_fail=True,
        )

    observed = members["observed"]
    heldout = members["heldout"]

    # shape_err on observed
    shape_err, pred_obs, gt_obs, flag = score_member(
        pred_build, gt_build, observed, param_specs, resolution, n_points, seed
    )
    flags.append(f"obs:{flag}")
    member_errs = [shape_err]

    # gen_err on held-out
    held_errs = []
    for i, vec in enumerate(heldout):
        err, _, _, flag = score_member(
            pred_build, gt_build, vec, param_specs, resolution, n_points, seed + 10 + i
        )
        held_errs.append(err)
        member_errs.append(err)
        flags.append(f"hold{i}:{flag}")
    gen_err = float(np.mean(held_errs)) if held_errs else 1.0

    # robust_err: LHS perturbation of observed
    robust_fail = 0
    try:
        perturbs = perturb_params(observed, param_specs, n=robust_n, seed=seed + 99)
        for i, vec in enumerate(perturbs):
            kwargs = {
                p["name"]: (int(round(vec[p["name"]])) if p["type"] == "int" else float(vec[p["name"]]))
                for p in param_specs
            }
            try:
                s = pred_build(**kwargs)
                if not geom.is_valid_solid(s):
                    robust_fail += 1
            except Exception:
                robust_fail += 1
        robust_err = robust_fail / max(robust_n, 1)
    except Exception as e:
        robust_err = 1.0
        flags.append(f"robust_fail:{e}")

    # parsimony on observed
    n_faces_pred = 0
    n_faces_gt = 0
    if pred_obs is not None:
        try:
            n_faces_pred = geom.count_faces(pred_obs)
        except Exception:
            n_faces_pred = 0
    if gt_obs is not None:
        try:
            n_faces_gt = geom.count_faces(gt_obs)
        except Exception:
            n_faces_gt = 1
    parsimony_pen = parsimony_penalty(n_faces_pred, n_faces_gt)

    intent = (
        W_SHAPE * shape_err
        + W_GEN * gen_err
        + W_ROBUST * robust_err
        + W_PARSIMONY * parsimony_pen
    )
    return TermBreakdown(
        shape_err=float(shape_err),
        gen_err=float(gen_err),
        robust_err=float(robust_err),
        parsimony_pen=float(parsimony_pen),
        intent_err=float(clamp01(intent)),
        member_shape_errs=member_errs,
        flags=flags,
        n_faces_pred=n_faces_pred,
        n_faces_gt=n_faces_gt,
        valid_gate_fail=False,
    )


def score_split(
    results: List[Tuple[str, TermBreakdown]],
) -> Dict[str, float]:
    """Aggregate mean intent_err and term means over tasks."""
    if not results:
        return {
            "intent_err": 1.0,
            "shape_err": 1.0,
            "gen_err": 1.0,
            "robust_err": 1.0,
            "parsimony_pen": 1.0,
            "n_tasks": 0,
        }
    return {
        "intent_err": float(np.mean([r.intent_err for _, r in results])),
        "shape_err": float(np.mean([r.shape_err for _, r in results])),
        "gen_err": float(np.mean([r.gen_err for _, r in results])),
        "robust_err": float(np.mean([r.robust_err for _, r in results])),
        "parsimony_pen": float(np.mean([r.parsimony_pen for _, r in results])),
        "n_tasks": len(results),
    }


def paired_bootstrap_gate(
    old_per_task: Sequence[float],
    new_per_task: Sequence[float],
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> Dict[str, Any]:
    """
    Accept change if 95% CI of mean(old - new) excludes 0 (and mean improvement > 0).
    Paired bootstrap over tasks.
    """
    old = np.asarray(old_per_task, dtype=np.float64)
    new = np.asarray(new_per_task, dtype=np.float64)
    if len(old) != len(new) or len(old) == 0:
        return {"accept": False, "reason": "length_mismatch", "mean_diff": 0.0}

    delta = old - new  # positive => improvement (lower is better for intent_err)
    mean_diff = float(delta.mean())
    rng = np.random.default_rng(seed)
    n = len(delta)
    boots = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boots[b] = delta[idx].mean()
    lo = float(np.quantile(boots, alpha / 2))
    hi = float(np.quantile(boots, 1 - alpha / 2))
    # require improvement: mean_diff > 0 and CI excludes 0
    accept = (mean_diff > 0) and (lo > 0)
    return {
        "accept": bool(accept),
        "mean_diff": mean_diff,
        "ci_lo": lo,
        "ci_hi": hi,
        "n_tasks": n,
        "reason": "improved" if accept else "not_significant_or_worse",
    }
