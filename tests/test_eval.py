"""Contracts for the immutable CAD evaluator.

These tests drive the shipped prepare.score_solver / generate_dataset
entry points. They do not hard-code expected scores.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prepare import (  # noqa: E402
    AntigravityAgent,
    CodexAgent,
    GrokAgent,
    generate_dataset,
    make_agent,
    score_solver,
)


# A real parametric-box solver used only in tests to prove the baseline
# is climbable. It is not shipped in solver.py.
_PARAMETRIC_BOX = '''\
from pathlib import Path
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
    elif {"width", "depth", "thick"} <= named:
        body = "return cq.Workplane('XY').box(width, depth, thick)"
    elif {"width", "depth", "plate_t"} <= named:
        body = "return cq.Workplane('XY').box(width, depth, plate_t)"
    return (
        "import cadquery as cq\\n\\n"
        f"def build({args}):\\n"
        f"    {body}\\n"
    )
'''

_LEAK_WORDS = (
    "plate",
    "hole",
    "fillet",
    "rib",
    "boss",
    "shell",
    "extrude",
    "revolve",
    "cylinder",
    "block",
    "tube",
    "counterbore",
    "helix",
    "loft",
    "l1_",
    "l2_",
    "l3_",
)


@pytest.fixture(scope="module")
def dataset(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("cad_eval")
    generate_dataset(root)
    return root


def test_same_solver_twice_identical_score(dataset: Path) -> None:
    solver = ROOT / "solver.py"
    first = score_solver(solver, dataset)
    second = score_solver(solver, dataset)
    assert first.intent_err == second.intent_err
    assert first.per_task == second.per_task
    assert first.n_tasks == second.n_tasks >= 1


def test_held_out_members_change_score_vs_observed_only(dataset: Path) -> None:
    solver = ROOT / "solver.py"
    observed = score_solver(solver, dataset, members="observed")
    full = score_solver(solver, dataset, members="all")
    assert observed.n_members != full.n_members
    assert observed.intent_err != full.intent_err


def test_task_identities_do_not_encode_family_verbs(dataset: Path) -> None:
    task_root = dataset / "data" / "tasks"
    ids = sorted(p.name for p in task_root.iterdir() if p.is_dir())
    assert ids, "generator wrote no tasks"
    for tid in ids:
        lowered = tid.lower()
        for word in _LEAK_WORDS:
            assert word not in lowered, f"task id {tid!r} leaks {word!r}"
        spec = json.loads((dataset / "data" / "hidden" / tid / "spec.json").read_text())
        visible = json.loads((task_root / tid / "params.json").read_text())
        assert "family" not in visible
        assert "value" not in visible
        assert "values" not in visible
        assert set(visible["names"]) == set(spec["observed"])


def test_params_json_withholds_member_values(dataset: Path) -> None:
    for task_dir in (dataset / "data" / "tasks").iterdir():
        visible = json.loads((task_dir / "params.json").read_text())
        hidden = json.loads(
            (dataset / "data" / "hidden" / task_dir.name / "spec.json").read_text()
        )
        assert set(visible) <= {"names", "types", "ranges"}
        assert "observed" not in visible
        assert "heldout" not in visible
        assert "family" not in visible
        # The observed vector lives only in the sealed spec.
        assert hidden["observed"]
        assert hidden["heldout"]


def test_baseline_has_no_dormant_family_emit_paths() -> None:
    src = (ROOT / "solver.py").read_text()
    assert "hidden" not in src
    assert "data/gt" not in src
    tree = ast.parse(src)
    forbidden = {
        "hole",
        "fillet",
        "rib",
        "boss",
        "shell",
        "counterbore",
        "tube",
        "helix",
        "pattern",
        "revolve",
        "loft",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value.lower()
            for word in forbidden:
                assert word not in text, f"baseline string leaks {word!r}"
        if isinstance(node, ast.Name) and node.id.lower() in forbidden:
            raise AssertionError(f"baseline identifier {node.id!r} is a family emit path")


def test_baseline_is_mediocre_and_climbable(dataset: Path, tmp_path: Path) -> None:
    baseline = score_solver(ROOT / "solver.py", dataset)
    assert 0.0 < baseline.intent_err < 1.0
    better = tmp_path / "parametric_box.py"
    better.write_text(_PARAMETRIC_BOX)
    improved = score_solver(better, dataset)
    assert improved.intent_err < baseline.intent_err


def test_broken_build_scores_one(dataset: Path, tmp_path: Path) -> None:
    broken = tmp_path / "broken.py"
    broken.write_text(
        "def solve(task_dir: str) -> str:\n"
        "    return 'def build(**kwargs):\\n    raise RuntimeError(\"boom\")\\n'\n"
    )
    scored = score_solver(broken, dataset)
    assert scored.intent_err == 1.0
    assert all(v == 1.0 for v in scored.per_task.values())


def test_grok_agent_pins_4_6_medium(tmp_path: Path) -> None:
    agent = GrokAgent()
    assert agent.model == "grok-4.6"
    assert agent.effort == "medium"
    cmd = agent.command(tmp_path)
    assert cmd[0].endswith("grok") or cmd[0] == "grok"
    assert "--always-approve" in cmd
    assert "--yolo" not in cmd
    assert cmd[cmd.index("--model") + 1] == "grok-4.6"
    assert cmd[cmd.index("--reasoning-effort") + 1] == "medium"


def test_antigravity_agent_pins_gemini_37_flash_high(tmp_path: Path) -> None:
    agent = AntigravityAgent()
    assert agent.model == "gemini-3.7-flash-high"
    assert agent.effort == "high"
    cmd = agent.command(tmp_path)
    assert cmd[0].endswith("agy") or cmd[0] == "agy"
    assert cmd[cmd.index("--model") + 1] == "gemini-3.7-flash-high"
    assert cmd[cmd.index("--effort") + 1] == "high"
    assert "--dangerously-skip-permissions" in cmd
    assert "--new-project" in cmd
    assert "--add-dir" in cmd
    assert str(tmp_path.resolve()) in cmd
    assert "--print" in cmd


def test_codex_agent_pins_terra_high(tmp_path: Path) -> None:
    agent = CodexAgent()
    assert agent.model == "gpt-5.6-terra"
    assert agent.effort == "high"
    cmd = agent.command(tmp_path)
    assert cmd[0:2] == [cmd[0], "exec"]
    assert cmd[0].endswith("codex") or cmd[0] == "codex"
    assert cmd[cmd.index("--model") + 1] == "gpt-5.6-terra"
    assert 'model_reasoning_effort="high"' in cmd
    assert "--approve-for-me" in cmd
    assert "--ephemeral" in cmd


def test_make_agent_routes_named_harnesses() -> None:
    grok = make_agent("grok", "grok-4.5", "high")
    agy = make_agent("antigravity", "gemini-3.7-flash-high", "high")
    codex = make_agent("codex", "gpt-5.6-terra", "high")
    assert isinstance(grok, GrokAgent) and grok.model == "grok-4.5"
    assert isinstance(agy, AntigravityAgent)
    assert isinstance(codex, CodexAgent)
    with pytest.raises(ValueError, match="unknown agent"):
        make_agent("cursor", "x", "high")


def test_plots_render_from_example_log(tmp_path: Path) -> None:
    import plots

    log = ROOT / "examples" / "grok-4.6-medium.tsv"
    written = plots.write_all([("grok-4.6", log)], tmp_path)
    assert (tmp_path / "race.png").is_file()
    assert (tmp_path / "loop.png").is_file()
    assert (tmp_path / "progress-grok-4.6.png").is_file()
    assert all(p.is_file() and p.stat().st_size > 0 for p in written)
    rows = plots.parse_log(log)
    stats = plots.summarize(rows)
    assert stats["keeps"] == 12
    assert stats["start"] > 0.2
    assert stats["end"] == 0.0


def test_cli_score_prints_scalar_and_log_path(dataset: Path, tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "prepare.py"),
            "score",
            "--root",
            str(dataset),
            "--solver",
            str(ROOT / "solver.py"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = {
        row.split("\t", 1)[0]: row.split("\t", 1)[1]
        for row in result.stdout.strip().splitlines()
        if "\t" in row
    }
    assert "intent_err" in lines
    err = float(lines["intent_err"])
    assert 0.0 < err <= 1.0
    # Same process path as the library API — not a hardcoded number.
    assert err == score_solver(ROOT / "solver.py", dataset).intent_err
