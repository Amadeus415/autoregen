"""Causal keep/discard ratchet — the loop, not the scorer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prepare import (  # noqa: E402
    _prepare_workdir,
    decide,
    generate_dataset,
    parse_log,
    run_loop,
    score_solver,
    solver_sha,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.check_call(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _workspace(tmp_path: Path) -> Path:
    generate_dataset(tmp_path)
    for name in ("solver.py", "prepare.py", "program.md"):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "dummy_agent.py").write_bytes(
        (ROOT / "tests" / "dummy_agent.py").read_bytes()
    )
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "eval@local")
    _git(tmp_path, "config", "user.name", "eval")
    _git(tmp_path, "add", "solver.py", "prepare.py", "program.md")
    _git(tmp_path, "commit", "-m", "baseline")
    return tmp_path


def test_workdir_does_not_contain_ground_truth(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    root, sealed = _prepare_workdir(ROOT, dest, "dummy")
    assert (root / "solver.py").is_file()
    assert (root / "program.md").is_file()
    assert (root / "data" / "tasks").is_dir()
    assert not (root / "prepare.py").exists()
    assert not (root / "hidden_eval.py").exists()
    assert not (root / "data" / "hidden").exists()
    assert not (root / "tests").exists()
    assert (sealed / "data" / "hidden").is_dir()
    assert list((sealed / "data" / "hidden").iterdir())


def test_decide_keep_only_on_strict_improvement() -> None:
    assert decide(best=0.50, new=0.49) == "keep"
    assert decide(best=0.50, new=0.50) == "discard"
    assert decide(best=0.50, new=0.51) == "discard"


def test_keep_on_improvement_reset_on_no_improvement(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    baseline_sha = solver_sha(root / "solver.py")
    baseline = score_solver(root / "solver.py", root)

    (root / "solver.py").write_text(_better_solver())
    improved = score_solver(root / "solver.py", root)
    assert improved.intent_err < baseline.intent_err
    assert decide(baseline.intent_err, improved.intent_err) == "keep"
    _git(root, "add", "solver.py")
    _git(root, "commit", "-m", "keep")
    kept_sha = solver_sha(root / "solver.py")
    assert kept_sha != baseline_sha

    (root / "solver.py").write_text("def solve(task_dir: str) -> str:\n    return 'nope'\n")
    worse = score_solver(root / "solver.py", root)
    assert worse.intent_err >= improved.intent_err
    assert decide(improved.intent_err, worse.intent_err) == "discard"
    subprocess.check_call(["git", "checkout", "--", "solver.py"], cwd=root)
    assert solver_sha(root / "solver.py") == kept_sha


def test_dummy_loop_ten_causal_steps_twice(tmp_path: Path) -> None:
    first = tmp_path / "run-a"
    second = tmp_path / "run-b"
    logs = []
    for dest in (first, second):
        dest.mkdir()
        _workspace(dest)
        log_path = run_loop(dest, agent="dummy", gens=15)
        logs.append(log_path)
        rows = parse_log(log_path)
        agent_rows = [r for r in rows if r.gen >= 1]
        keeps = [r for r in rows if r.gen >= 1 and r.status == "keep"]
        assert len(agent_rows) >= 10
        assert len(keeps) >= 10, f"only {len(keeps)} accepted steps: {[r.status for r in agent_rows]}"
        last_keep = rows[0].solver_sha
        for row in agent_rows:
            assert row.hypothesis.strip()
            assert row.status in {"keep", "discard", "crash"}
            assert 0.0 <= row.intent_err <= 1.0
            assert row.start_sha == last_keep, (
                f"gen {row.gen} started from {row.start_sha}, "
                f"not last accepted {last_keep}"
            )
            if row.status == "keep":
                last_keep = row.solver_sha
        assert (dest / "results.tsv").read_text().strip()
        # Frontier file equals last accepted solver.
        assert solver_sha(dest / "solver.py") == last_keep

    a = parse_log(logs[0])
    b = parse_log(logs[1])
    assert [r.status for r in a] == [r.status for r in b]
    assert [r.intent_err for r in a] == [r.intent_err for r in b]


def test_resume_appends_without_resetting_frontier(tmp_path: Path) -> None:
    dest = tmp_path / "run"
    dest.mkdir()
    _workspace(dest)
    first = run_loop(dest, agent="dummy", gens=3)
    before = parse_log(first)
    kept_sha = [r for r in before if r.status == "keep"][-1].solver_sha
    assert solver_sha(dest / "solver.py") == kept_sha
    second = run_loop(dest, agent="dummy", gens=2, resume=True)
    after = parse_log(second)
    assert [r.gen for r in after[: len(before)]] == [r.gen for r in before]
    assert [r.solver_sha for r in after[: len(before)]] == [r.solver_sha for r in before]
    assert after[-1].gen == before[-1].gen + 2
    assert after[len(before)].start_sha == kept_sha
    last_keep = [r for r in after if r.status == "keep"][-1].solver_sha
    assert solver_sha(dest / "solver.py") == last_keep


def test_cli_loop_prints_scalar_and_nonempty_log(tmp_path: Path) -> None:
    workdir = tmp_path / "agent"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "prepare.py"),
            "loop",
            "--agent",
            "dummy",
            "--gens",
            "15",
            "--workdir",
            str(workdir),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    lines = {
        row.split("\t", 1)[0]: row.split("\t", 1)[1]
        for row in result.stdout.strip().splitlines()
        if "\t" in row
    }
    assert "intent_err" in lines
    assert "log" in lines
    log_path = Path(lines["log"].strip())
    assert log_path.is_file()
    rows = parse_log(log_path)
    assert len([r for r in rows if r.gen >= 1]) >= 10
    assert len([r for r in rows if r.gen >= 1 and r.status == "keep"]) >= 10
    assert float(lines["intent_err"]) == rows[-1].intent_err or float(
        lines["intent_err"]
    ) == min(r.intent_err for r in rows if r.status == "keep")


def _better_solver() -> str:
    return '''from pathlib import Path
import json


def solve(task_dir: str) -> str:
    import cadquery as cq

    task = Path(task_dir)
    names = json.loads((task / "params.json").read_text())["names"]
    args = ", ".join(names)
    named = set(names)
    wp = cq.importers.importStep(str(task / "target.step"))
    bb = wp.val().BoundingBox()
    dx, dy, dz = bb.xlen, bb.ylen, bb.zlen
    body = f"return cq.Workplane('XY').box({dx:.6f}, {dy:.6f}, {dz:.6f})"
    if {"width", "depth", "height"} <= named:
        body = "return cq.Workplane('XY').box(width, depth, height)"
    return (
        "import cadquery as cq\\n\\n"
        f"def build({args}):\\n"
        f"    {body}\\n"
    )
'''
