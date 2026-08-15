#!/usr/bin/env python3
"""Immutable CAD eval + ratchet.

Three artifacts matter:

  prepare.py   this file — generate tasks, score solvers, run the loop
  solver.py    the only file the agent may edit
  program.md   human-written research brief

Metric: intent_err = mean shape error over {observed} ∪ {held-out members}.
shape_err is ½ relative volume error + ½ mean relative bbox-extent error.
Lower is better. Same solver twice → same number.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from hidden_eval import BUILDERS, FAMILIES


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _cq():
    import cadquery as cq

    return cq


def _as_solid(obj):
    if obj is None:
        raise ValueError("build() returned None")
    if hasattr(obj, "val"):
        obj = obj.val()
    return obj


def _props(solid) -> tuple[float, tuple[float, float, float]]:
    solid = _as_solid(solid)
    volume = float(solid.Volume())
    bb = solid.BoundingBox()
    return volume, (float(bb.xlen), float(bb.ylen), float(bb.zlen))


def shape_err(pred, gt) -> float:
    """Volume + bbox extents. Crash / empty → 1.0."""
    try:
        pv, pe = _props(pred)
        gv, ge = _props(gt)
    except Exception:
        return 1.0
    if gv <= 1e-12 or pv <= 1e-12:
        return 1.0
    vol_term = abs(pv - gv) / gv
    bbox_term = sum(abs(a - b) / max(b, 1e-9) for a, b in zip(pe, ge)) / 3.0
    return min(1.0, 0.5 * vol_term + 0.5 * bbox_term)


def _task_id(family_key: str, seed: int) -> str:
    digest = hashlib.sha256(f"autoregen-v1|{seed}|{family_key}".encode()).hexdigest()
    return f"t_{digest[:8]}"


def _export_step(solid, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _cq().exporters.export(_as_solid(solid), str(path))


def generate_dataset(root: Path, seed: int = 0) -> list[str]:
    """Write data/tasks (visible) and data/hidden (evaluator only)."""
    root = Path(root)
    tasks_dir = root / "data" / "tasks"
    hidden_dir = root / "data" / "hidden"
    if (root / "data").exists():
        shutil.rmtree(root / "data")
    tasks_dir.mkdir(parents=True)
    hidden_dir.mkdir(parents=True)
    ids: list[str] = []
    for family in FAMILIES:
        tid = _task_id(family["key"], seed)
        ids.append(tid)
        observed = family["observed"]
        solid = family["build"](observed)
        task_dir = tasks_dir / tid
        task_dir.mkdir()
        _export_step(solid, task_dir / "target.step")
        (task_dir / "params.json").write_text(
            json.dumps(
                {
                    "names": list(family["names"]),
                    "types": {n: "length" for n in family["names"]},
                    "ranges": family["ranges"],
                },
                indent=2,
            )
            + "\n"
        )
        spec = {
            "family": family["key"],
            "observed": observed,
            "heldout": family["heldout"],
        }
        dest = hidden_dir / tid
        dest.mkdir()
        (dest / "spec.json").write_text(json.dumps(spec, indent=2) + "\n")
    return ids


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Score:
    intent_err: float
    per_task: dict[str, float]
    n_tasks: int
    n_members: int


def solver_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _members(spec: dict, which: str) -> list[dict]:
    observed = [spec["observed"]]
    heldout = list(spec["heldout"])
    if which == "observed":
        return observed
    if which == "heldout":
        return heldout
    if which == "all":
        return observed + heldout
    raise ValueError(f"unknown members={which!r}")


def _run_build(source: str, params: dict):
    ns: dict = {}
    exec(compile(source, "<build>", "exec"), ns, ns)
    if "build" not in ns:
        raise RuntimeError("emitted module has no build()")
    return ns["build"](**params)


def score_solver(solver_path: Path, data_root: Path, *, members: str = "all") -> Score:
    """Score a solver. members='all' is the official metric."""
    solver_path = Path(solver_path)
    data_root = Path(data_root)
    tasks = sorted((data_root / "data" / "tasks").iterdir())
    if not tasks:
        raise FileNotFoundError(f"no tasks under {data_root}/data/tasks")

    try:
        solver = _load_module(solver_path, f"solver_{solver_sha(solver_path)}")
        solve = solver.solve
    except Exception:
        ids = [p.name for p in tasks]
        return Score(1.0, {i: 1.0 for i in ids}, len(ids), 0)

    per_task: dict[str, float] = {}
    n_members = 0
    for task_dir in tasks:
        spec_path = data_root / "data" / "hidden" / task_dir.name / "spec.json"
        spec = json.loads(spec_path.read_text())
        builder = BUILDERS[spec["family"]]
        vectors = _members(spec, members)
        n_members = len(vectors)
        try:
            source = solve(str(task_dir))
        except Exception:
            per_task[task_dir.name] = 1.0
            continue
        errs: list[float] = []
        for params in vectors:
            try:
                pred = _run_build(source, params)
                gt = builder(params)
                errs.append(shape_err(pred, gt))
            except Exception:
                errs.append(1.0)
        per_task[task_dir.name] = round(sum(errs) / len(errs), 8)

    intent = round(sum(per_task.values()) / len(per_task), 8)
    return Score(intent, per_task, len(per_task), n_members)


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------

LOG_HEADER = "gen\tstart_sha\tsolver_sha\tintent_err\tstatus\thypothesis\n"


@dataclass(frozen=True)
class Row:
    gen: int
    start_sha: str
    solver_sha: str
    intent_err: float
    status: str
    hypothesis: str


def parse_log(path: Path) -> list[Row]:
    rows: list[Row] = []
    text = Path(path).read_text()
    for line in text.splitlines()[1:]:
        if not line.strip():
            continue
        gen, start, sha, err, status, hyp = line.split("\t", 5)
        rows.append(
            Row(int(gen), start, sha, float(err), status, hyp)
        )
    return rows


def _append_row(path: Path, row: Row) -> None:
    path = Path(path)
    if not path.exists():
        path.write_text(LOG_HEADER)
    with path.open("a") as fh:
        hyp = row.hypothesis.replace("\t", " ").replace("\n", " ")
        fh.write(
            f"{row.gen}\t{row.start_sha}\t{row.solver_sha}\t"
            f"{row.intent_err:.8f}\t{row.status}\t{hyp}\n"
        )


def decide(best: float, new: float) -> str:
    return "keep" if new < best else "discard"


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def write_chart(log_path: Path, out_path: Path) -> None:
    rows = parse_log(log_path)
    if not rows:
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    gens = [r.gen for r in rows]
    errs = [r.intent_err for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.scatter(gens, errs, c="#888888", s=28, zorder=2, label="every step")
    frontier_x: list[int] = []
    frontier_y: list[float] = []
    best = None
    for row in rows:
        if row.status == "keep":
            best = row.intent_err
            frontier_x.append(row.gen)
            frontier_y.append(row.intent_err)
        elif best is not None:
            frontier_x.append(row.gen)
            frontier_y.append(best)
    if frontier_x:
        ax.step(frontier_x, frontier_y, where="post", color="#1d4ed8", lw=2, label="accepted")
        ax.scatter(frontier_x[:1], frontier_y[:1], c="#1d4ed8", s=36, zorder=3)
    ax.set_xlabel("generation")
    ax.set_ylabel("intent_err  (lower is better)")
    ax.set_title("design-intent recovery — keep-if-better")
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=False)
    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class LauncherError(RuntimeError):
    pass


def _load_dummy():
    here = Path(__file__).resolve().parent
    path = here / "tests" / "dummy_agent.py"
    if not path.is_file():
        raise LauncherError(f"dummy agent missing: {path}")
    return _load_module(path, "dummy_agent").DummyAgent()


def _grok_bin() -> str:
    found = shutil.which("grok")
    if not found:
        raise LauncherError("grok CLI not on PATH")
    return found


class GrokAgent:
    def __init__(self, model: str = "grok-4.6", effort: str = "medium") -> None:
        self.model = model
        self.effort = effort

    def propose(self, root: Path) -> str:
        prompt = (
            "You are doing ONE research step on a CAD design-intent eval.\n"
            "Read program.md, solver.py, and the last 40 lines of results.tsv if it exists.\n"
            "Make exactly one hypothesized improvement to solver.py.\n"
            "Write one line to .hypothesis.txt describing the change.\n"
            "Do not edit any other file.\n"
            "Do not run prepare.py and do not score yourself.\n"
            "Do not read data/hidden/, hidden_eval.py, tests/, or any directory outside this workspace.\n"
            "Do not start a loop — you will be invoked again after the harness scores this change.\n"
            "Finish after the edit.\n"
        )
        cmd = [
            _grok_bin(),
            "-p",
            prompt,
            "--model",
            self.model,
            "--reasoning-effort",
            self.effort,
            "--yolo",
            "--max-turns",
            "25",
            "--no-subagents",
            "--cwd",
            str(root),
            "--output-format",
            "plain",
        ]
        turn_log = root / "grok-turn.log"
        try:
            with turn_log.open("a") as fh:
                fh.write(f"\n--- turn {time.strftime('%H:%M:%S')} ---\n")
                fh.flush()
                subprocess.run(
                    cmd,
                    check=True,
                    cwd=root,
                    timeout=720,
                    stdout=fh,
                    stderr=fh,
                )
        except FileNotFoundError as exc:
            raise LauncherError("grok CLI not executable") from exc
        except subprocess.TimeoutExpired as exc:
            raise LauncherError(f"grok turn timed out: {exc}") from exc
        except subprocess.CalledProcessError as exc:
            raise LauncherError(f"grok turn failed: {exc}") from exc
        hyp_path = root / ".hypothesis.txt"
        if hyp_path.is_file() and hyp_path.read_text().strip():
            return hyp_path.read_text().strip().splitlines()[0]
        return f"grok {self.model} {self.effort} edit"


# ---------------------------------------------------------------------------
# Ratchet
# ---------------------------------------------------------------------------

def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "autoregen")
    env.setdefault("GIT_AUTHOR_EMAIL", "autoregen@local")
    env.setdefault("GIT_COMMITTER_NAME", "autoregen")
    env.setdefault("GIT_COMMITTER_EMAIL", "autoregen@local")
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=check,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _ensure_git(root: Path) -> None:
    if (root / ".git").is_dir():
        return
    _git(root, "init")
    _git(root, "add", "solver.py")
    if (root / "prepare.py").is_file():
        _git(root, "add", "prepare.py")
    if (root / "program.md").is_file():
        _git(root, "add", "program.md")
    _git(root, "commit", "-m", "baseline")


def _enforce_solver_only(root: Path) -> None:
    diff = _git(root, "diff", "--name-only", check=False).stdout.split()
    for name in diff:
        if name != "solver.py":
            _git(root, "checkout", "--", name, check=False)
    listed = _git(root, "ls-files", "--others", "--exclude-standard", check=False)
    allowed = {".hypothesis.txt", "results.tsv", "chart.png"}
    for name in listed.stdout.split():
        if name in allowed or name.startswith("data/"):
            continue
        path = root / name
        if path.is_file():
            path.unlink()


def _restore_solver(root: Path) -> None:
    _git(root, "checkout", "--", "solver.py")


def _commit_solver(root: Path, message: str) -> None:
    _git(root, "add", "solver.py")
    _git(root, "commit", "-m", message, check=False)


def run_loop(
    root: Path,
    *,
    agent: str,
    gens: int,
    model: str = "grok-4.6",
    effort: str = "medium",
    data_root: Path | None = None,
) -> Path:
    """Causal keep-if-better loop. Returns path to results.tsv."""
    root = Path(root)
    data_root = Path(data_root or root)
    if not (data_root / "data" / "tasks").is_dir():
        generate_dataset(data_root)
    if not (root / "solver.py").is_file():
        raise FileNotFoundError(f"no solver.py in {root}")
    _ensure_git(root)
    log_path = root / "results.tsv"
    if log_path.exists():
        log_path.unlink()

    if agent == "dummy":
        researcher = _load_dummy()
    elif agent == "grok":
        researcher = GrokAgent(model=model, effort=effort)
    else:
        raise ValueError(f"unknown agent {agent!r}")

    solver = root / "solver.py"
    scored = score_solver(solver, data_root)
    start = solver_sha(solver)
    _append_row(
        log_path,
        Row(0, start, start, scored.intent_err, "keep", "baseline"),
    )
    best = scored.intent_err
    accepted = start
    print(f"gen\t0\t{scored.intent_err:.8f}\tkeep\tbaseline", flush=True)

    for gen in range(1, gens + 1):
        start_sha = solver_sha(solver)
        if start_sha != accepted:
            raise RuntimeError(
                f"causal break at gen {gen}: solver {start_sha} != accepted {accepted}"
            )
        status = "keep"
        hypothesis = ""
        try:
            hypothesis = researcher.propose(root)
            _enforce_solver_only(root)
            try:
                probe = _load_module(solver, f"probe_{gen}")
                if not hasattr(probe, "solve"):
                    raise AttributeError("solve")
                crashed = False
            except Exception:
                crashed = True
            candidate = score_solver(solver, data_root)
            if crashed:
                status = "crash"
                err = 1.0
                sha = solver_sha(solver)
                _restore_solver(root)
            else:
                err = candidate.intent_err
                sha = solver_sha(solver)
                status = decide(best, err)
                if status == "keep":
                    best = err
                    accepted = sha
                    _commit_solver(root, f"gen {gen}: {hypothesis}")
                else:
                    _restore_solver(root)
        except LauncherError:
            raise
        except Exception:
            status = "crash"
            err = 1.0
            sha = solver_sha(solver)
            hypothesis = hypothesis or traceback.format_exc().splitlines()[-1]
            _restore_solver(root)

        _append_row(
            log_path,
            Row(gen, start_sha, sha, err, status, hypothesis or status),
        )
        print(
            f"gen\t{gen}\t{err:.8f}\t{status}\t{hypothesis}",
            flush=True,
        )

    write_chart(log_path, root / "chart.png")
    return log_path


def _prepare_workdir(src: Path, dest: Path, _agent: str) -> tuple[Path, Path]:
    """Agent workspace: solver + brief + visible tasks. GT stays in *.sealed."""
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "solver.py", dest / "solver.py")
    shutil.copy2(src / "program.md", dest / "program.md")
    sealed = dest.parent / f"{dest.name}.sealed"
    generate_dataset(sealed)
    tasks_src = sealed / "data" / "tasks"
    tasks_dst = dest / "data" / "tasks"
    if tasks_dst.exists():
        shutil.rmtree(tasks_dst)
    shutil.copytree(tasks_src, tasks_dst)
    return dest, sealed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_kv(**kwargs) -> None:
    for key, value in kwargs.items():
        print(f"{key}\t{value}", flush=True)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="autoregen — Karpathy-style CAD eval")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="write the synthetic task set")
    g.add_argument("--root", type=Path, default=Path("."))
    g.add_argument("--seed", type=int, default=0)

    s = sub.add_parser("score", help="score a solver")
    s.add_argument("--root", type=Path, default=Path("."))
    s.add_argument("--solver", type=Path, default=Path("solver.py"))
    s.add_argument("--members", choices=("all", "observed", "heldout"), default="all")

    lp = sub.add_parser("loop", help="causal keep-if-better loop")
    lp.add_argument("--agent", choices=("dummy", "grok"), required=True)
    lp.add_argument("--gens", type=int, default=10)
    lp.add_argument("--root", type=Path, default=None)
    lp.add_argument("--workdir", type=Path, default=None)
    lp.add_argument("--model", default="grok-4.6")
    lp.add_argument("--effort", default="medium")

    c = sub.add_parser("chart", help="draw the frontier from a log")
    c.add_argument("--log", type=Path, default=Path("results.tsv"))
    c.add_argument("--out", type=Path, default=Path("chart.png"))

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "generate":
        ids = generate_dataset(args.root, seed=args.seed)
        _print_kv(tasks=len(ids), root=args.root.resolve())
        return 0

    if args.cmd == "score":
        root = args.root.resolve()
        if not (root / "data" / "tasks").is_dir():
            generate_dataset(root)
        scored = score_solver(args.solver, root, members=args.members)
        _print_kv(
            intent_err=f"{scored.intent_err:.8f}",
            n_tasks=scored.n_tasks,
            n_members=scored.n_members,
        )
        return 0

    if args.cmd == "loop":
        src = Path.cwd()
        data_root = None
        if args.workdir is not None:
            root, data_root = _prepare_workdir(src, args.workdir.resolve(), args.agent)
        else:
            root = (args.root or src).resolve()
            if not (root / "data" / "tasks").is_dir():
                generate_dataset(root)
        started = time.time()
        try:
            log_path = run_loop(
                root,
                agent=args.agent,
                gens=args.gens,
                model=args.model,
                effort=args.effort,
                data_root=data_root,
            )
        except LauncherError as exc:
            print(f"launcher_error\t{exc}", file=sys.stderr)
            return 2
        rows = parse_log(log_path)
        keeps = [r for r in rows if r.status == "keep"]
        frontier = keeps[-1].intent_err if keeps else rows[-1].intent_err
        _print_kv(
            intent_err=f"{frontier:.8f}",
            steps=max(0, len(rows) - 1),
            accepted=max(0, len(keeps) - 1),
            log=str(log_path.resolve()),
            seconds=f"{time.time() - started:.1f}",
        )
        return 0

    if args.cmd == "chart":
        write_chart(args.log, args.out)
        _print_kv(chart=args.out.resolve())
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
