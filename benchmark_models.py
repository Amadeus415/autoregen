#!/usr/bin/env python3
"""Run isolated, same-start recursive-improvement arms and validate them.

This is an orchestration layer only. Each arm receives the same immutable
harness, generated data, baseline solver, evaluation settings, and number of
research turns. The existing loop.sh remains the authority for ownership,
evaluation, paired gating, and commit/revert behavior.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv" / "bin" / "python"
RESULT_HEADER = (
    "gen\tsha\tintent_err\tshape_err\tgen_err\trobust_err\tparsimony_pen\t"
    "wall_s\ttokens\tusd\taccepted\tnote\tviolations\tsplit\tn_tasks\n"
)

ARMS = {
    "antigravity-flash-3.6-high": {
        "label": "Antigravity · Gemini 3.6 Flash High",
        "model": "gemini-3.6-flash-high",
        "driver": ROOT / "scripts" / "antigravity_agent.sh",
    },
    "grok-4.5-high": {
        "label": "Grok CLI · Grok 4.5 High",
        "model": "grok-4.5",
        "driver": ROOT / "scripts" / "grok_agent.sh",
    },
}


def run(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    log_path: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    if log_path is None:
        return subprocess.run(cmd, cwd=cwd, env=merged, text=True, check=check)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=merged,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
            log.flush()
        rc = proc.wait()
    completed = subprocess.CompletedProcess(cmd, rc, "", "")
    if check and rc:
        raise subprocess.CalledProcessError(rc, cmd)
    return completed


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_ref(ref: str, destination: Path) -> str:
    resolved = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=ROOT, text=True
    ).strip()
    archive = destination.parent / "base.tar"
    with archive.open("wb") as fh:
        subprocess.run(["git", "archive", resolved], cwd=ROOT, stdout=fh, check=True)
    destination.mkdir(parents=True)
    with tarfile.open(archive) as tf:
        # Reject path traversal explicitly while remaining compatible with
        # every supported Python version (3.10-3.13).
        members = tf.getmembers()
        root = destination.resolve()
        for member in members:
            target = (destination / member.name).resolve()
            if root != target and root not in target.parents:
                raise RuntimeError(f"unsafe archive member: {member.name}")
        tf.extractall(destination, members=members)
    archive.unlink()
    # Keep the historical baseline solver, but evaluate it with the current
    # hardened orchestration and immutable harness.
    shutil.copy2(ROOT / "loop.sh", destination / "loop.sh")
    shutil.copy2(ROOT / "prepare.py", destination / "prepare.py")
    shutil.copytree(ROOT / "harness", destination / "harness", dirs_exist_ok=True)
    return resolved


def init_baseline(template: Path, args: argparse.Namespace) -> dict[str, Any]:
    (template / "results.tsv").write_text(RESULT_HEADER, encoding="utf-8")
    run(["git", "init", "-q"], cwd=template)
    run(["git", "add", "-A"], cwd=template)
    run(
        [
            "git",
            "-c",
            "user.name=autoregen-benchmark",
            "-c",
            "user.email=autoregen@local",
            "commit",
            "-qm",
            "benchmark baseline",
        ],
        cwd=template,
    )
    run([str(PYTHON), "prepare.py", "generate", "--quick"], cwd=template)
    run([str(PYTHON), "prepare.py", "checksum", "--write"], cwd=template)
    run(
        [
            "git",
            "add",
            "HARNESS.sha256",
        ],
        cwd=template,
    )
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=template).returncode:
        run(
            [
                "git",
                "-c",
                "user.name=autoregen-benchmark",
                "-c",
                "user.email=autoregen@local",
                "commit",
                "-qm",
                "pin generated benchmark harness",
            ],
            cwd=template,
        )
    run(
        [
            str(PYTHON),
            "prepare.py",
            "gen0",
            "--quick",
            "--workers",
            str(args.workers),
            "--resolution",
            str(args.resolution),
            "--n-points",
            str(args.n_points),
            "--robust-n",
            str(args.robust_n),
        ],
        cwd=template,
    )
    baseline = json.loads((template / "best_per_task.json").read_text())
    return {
        "intent_err": baseline["intent_err"],
        "solver_sha256": sha256(template / "solver.py"),
        "harness_sha256": (template / "HARNESS.sha256").read_text().split()[0],
        "n_tasks": len(baseline["per_task"]),
    }


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def summarize_arm(arm_dir: Path, baseline: dict[str, Any], generations: int) -> dict[str, Any]:
    rows = read_rows(arm_dir / "results.tsv")
    dev = [r for r in rows if r.get("split") == "dev"]
    candidates = [r for r in dev if int(float(r["gen"])) > 0]
    accepted = [r for r in candidates if int(float(r.get("accepted", "0"))) == 1]
    final = float(json.loads((arm_dir / "best_per_task.json").read_text())["intent_err"])
    return {
        "status": "complete" if len(candidates) == generations else "incomplete",
        "baseline_intent_err": float(baseline["intent_err"]),
        "best_intent_err": final,
        "absolute_improvement": float(baseline["intent_err"]) - final,
        "relative_improvement_pct": (
            (float(baseline["intent_err"]) - final) / float(baseline["intent_err"]) * 100.0
        ),
        "candidate_generations": len(candidates),
        "accepted_generations": len(accepted),
        "violations": sum(bool(r.get("violations")) for r in candidates),
        "evaluation_wall_s": sum(float(r.get("wall_s") or 0) for r in candidates),
        "final_solver_sha256": sha256(arm_dir / "solver.py"),
    }


def sealed_validation(arm_dir: Path, args: argparse.Namespace, log: Path) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    for split in ("dev", "test", "test-ood"):
        out = arm_dir / f"final_{split}.json"
        run(
            [
                str(PYTHON),
                "prepare.py",
                "eval",
                "--split",
                split,
                "--workers",
                str(args.workers),
                "--resolution",
                str(args.resolution),
                "--n-points",
                str(args.n_points),
                "--robust-n",
                str(args.robust_n),
                "--out",
                str(out),
            ],
            cwd=arm_dir,
            log_path=log,
        )
        report = json.loads(out.read_text())
        reports[split] = {
            "ok": report["ok"],
            "intent_err": report["intent_err"],
            "n_tasks": report["n_tasks"],
            "violations": report["violations"],
            "solver_sha256": report["solver_sha"],
        }
    # Re-run dev unchanged: exact equality is the deterministic acceptance criterion.
    rerun = arm_dir / "final_dev_rerun.json"
    run(
        [
            str(PYTHON),
            "prepare.py",
            "eval",
            "--split",
            "dev",
            "--workers",
            str(args.workers),
            "--resolution",
            str(args.resolution),
            "--n-points",
            str(args.n_points),
            "--robust-n",
            str(args.robust_n),
            "--out",
            str(rerun),
        ],
        cwd=arm_dir,
        log_path=log,
    )
    rerun_report = json.loads(rerun.read_text())
    reports["determinism"] = {
        "first": reports["dev"]["intent_err"],
        "second": rerun_report["intent_err"],
        "absolute_delta": abs(reports["dev"]["intent_err"] - rerun_report["intent_err"]),
        "pass": abs(reports["dev"]["intent_err"] - rerun_report["intent_err"]) <= 1e-9,
    }
    return reports


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-ref", default="f88a29c", help="shared baseline commit")
    p.add_argument("--generations", type=int, default=3)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--resolution", type=int, default=48)
    p.add_argument("--n-points", type=int, default=4000)
    p.add_argument("--robust-n", type=int, default=8)
    p.add_argument("--run-id", default=None)
    p.add_argument("--arms", nargs="+", choices=sorted(ARMS), default=list(ARMS))
    p.add_argument(
        "--reuse-arm-from",
        type=Path,
        default=None,
        help="reuse individually complete+validated arms from a compatible prior run",
    )
    p.add_argument("--keep-work", action="store_true")
    p.add_argument("--preflight-only", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not PYTHON.exists():
        raise SystemExit(f"Python environment missing: {PYTHON}")
    if args.generations < 1:
        raise SystemExit("--generations must be >= 1")
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT / "benchmark_runs" / run_id
    work = ROOT / ".benchmark_work" / run_id
    if output.exists() or work.exists():
        raise SystemExit(f"run id already exists: {run_id}")
    output.mkdir(parents=True)
    work.mkdir(parents=True)

    template = work / "template"
    resolved = extract_ref(args.base_ref, template)
    baseline = init_baseline(template, args)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile": "quick-comparative",
        "base_ref": args.base_ref,
        "base_commit": resolved,
        "baseline": baseline,
        "settings": {
            "generations": args.generations,
            "workers": args.workers,
            "resolution": args.resolution,
            "n_points": args.n_points,
            "robust_n": args.robust_n,
            "data_seed": 42,
            "dev_tasks": baseline["n_tasks"],
        },
        "arms": {},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.preflight_only:
        print(json.dumps(manifest, indent=2))
        if not args.keep_work:
            shutil.rmtree(work)
        return 0

    reusable: dict[str, Any] = {}
    reuse_root: Path | None = None
    if args.reuse_arm_from is not None:
        reuse_root = args.reuse_arm_from.resolve()
        old = json.loads((reuse_root / "manifest.json").read_text())
        if (
            old.get("base_commit") != manifest["base_commit"]
            or old.get("settings") != manifest["settings"]
            or old.get("baseline", {}).get("harness_sha256") != baseline["harness_sha256"]
        ):
            raise SystemExit("reused run does not match this run's baseline/settings")
        reusable = old.get("arms", {})

    for arm_name in args.arms:
        spec = ARMS[arm_name]
        old_arm = reusable.get(arm_name, {})
        old_validation = old_arm.get("validation", {})
        if (
            reuse_root is not None
            and old_arm.get("status") == "complete"
            and old_validation.get("determinism", {}).get("pass")
            and not old_arm.get("violations")
            and all(old_validation.get(s, {}).get("ok") for s in ("dev", "test", "test-ood"))
        ):
            print(f"\n=== {spec['label']} (reused validated arm) ===", flush=True)
            shutil.copytree(reuse_root / arm_name, output / arm_name)
            manifest["arms"][arm_name] = old_arm
            (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            continue
        arm_dir = work / arm_name
        shutil.copytree(template, arm_dir)
        arm_out = output / arm_name
        arm_out.mkdir()
        print(f"\n=== {spec['label']} ===", flush=True)
        env = {
            "PYTHON": str(PYTHON),
            "MAX_GENS": str(args.generations),
            "WORKERS": str(args.workers),
            "RESOLUTION": str(args.resolution),
            "N_POINTS": str(args.n_points),
            "ROBUST_N": str(args.robust_n),
            "AGENT_CMD": str(spec["driver"]),
            "BRANCH": f"benchmark-{arm_name}",
        }
        loop_log = arm_out / "loop.log"
        loop_proc = run(["bash", "loop.sh"], cwd=arm_dir, env=env, log_path=loop_log, check=False)
        summary = summarize_arm(arm_dir, baseline, args.generations)
        summary.update(
            {"label": spec["label"], "model": spec["model"], "loop_exit_code": loop_proc.returncode}
        )
        if loop_proc.returncode == 0 and summary["status"] == "complete":
            summary["validation"] = sealed_validation(arm_dir, args, arm_out / "validation.log")
        else:
            summary["status"] = "failed"
        for name in ("results.tsv", "best_per_task.json", "last_eval.json", "last_gate.json", "solver.py"):
            source = arm_dir / name
            if source.exists():
                shutil.copy2(source, arm_out / name)
        manifest["arms"][arm_name] = summary
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    manifest["complete"] = all(a.get("status") == "complete" for a in manifest["arms"].values())
    manifest["valid"] = manifest["complete"] and all(
        a.get("validation", {}).get("determinism", {}).get("pass", False)
        and not a.get("violations")
        and all(a.get("validation", {}).get(s, {}).get("ok", False) for s in ("dev", "test", "test-ood"))
        for a in manifest["arms"].values()
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    run(
        [
            str(PYTHON),
            str(ROOT / "plots" / "make_chart.py"),
            "--benchmark-run",
            str(output),
            "--out",
            str(output / "chart.png"),
        ],
        cwd=ROOT,
    )
    shutil.copy2(output / "chart.png", ROOT / "plots" / "chart.png")
    if not args.keep_work:
        shutil.rmtree(work)
    print(f"Benchmark manifest: {output / 'manifest.json'}")
    print(f"Benchmark chart:    {output / 'chart.png'}")
    return 0 if manifest["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
