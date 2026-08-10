#!/usr/bin/env python3
"""Independently re-score saved benchmark solvers on the root immutable data."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.eval import evaluate, sha256_tree
from prepare import harness_paths


ROOT = Path(__file__).resolve().parent


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def compact(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": result["ok"],
        "intent_err": result["intent_err"],
        "n_tasks": result["n_tasks"],
        "violations": result["violations"],
        "solver_sha256": result["solver_sha"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    settings = manifest["settings"]

    expected_harness = (ROOT / "HARNESS.sha256").read_text().split()[0]
    actual_harness = sha256_tree(harness_paths(ROOT))
    if expected_harness != actual_harness:
        raise SystemExit("root HARNESS.sha256 mismatch")
    data_manifest = json.loads((ROOT / "data" / "manifest.json").read_text())
    expected_sizes = {"train": 12, "dev": 8, "test": 4, "test-ood": 2}
    if data_manifest.get("seed") != settings.get("data_seed"):
        raise SystemExit("root data seed differs from benchmark")
    if data_manifest.get("sizes_written") != expected_sizes:
        raise SystemExit("root data sizes differ from quick benchmark profile")

    audit: dict[str, Any] = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "harness_sha256": actual_harness,
        "data_manifest_sha256": file_sha256(ROOT / "data" / "manifest.json"),
        "arms": {},
    }
    all_pass = True
    for arm_name, arm in manifest["arms"].items():
        solver = run_dir / arm_name / "solver.py"
        solver_hash_ok = file_sha256(solver) == arm["final_solver_sha256"]
        arm_audit: dict[str, Any] = {"solver_hash_pass": solver_hash_ok, "splits": {}}
        all_pass = all_pass and solver_hash_ok
        for split in ("dev", "test", "test-ood"):
            result = evaluate(
                ROOT,
                split=split,
                solver_path=solver,
                workers=settings["workers"],
                resolution=settings["resolution"],
                n_points=settings["n_points"],
                robust_n=settings["robust_n"],
                verbose=True,
            )
            out = run_dir / arm_name / f"independent_{split}.json"
            out.write_text(json.dumps(result, indent=2), encoding="utf-8")
            expected = arm["validation"][split]
            match = (
                result["ok"]
                and not result["violations"]
                and result["n_tasks"] == expected["n_tasks"]
                and abs(result["intent_err"] - expected["intent_err"]) <= 1e-9
                and result["solver_sha"] == expected["solver_sha256"]
            )
            arm_audit["splits"][split] = {**compact(result), "matches_isolated_run": match}
            all_pass = all_pass and match

        rerun = evaluate(
            ROOT,
            split="dev",
            solver_path=solver,
            workers=settings["workers"],
            resolution=settings["resolution"],
            n_points=settings["n_points"],
            robust_n=settings["robust_n"],
            verbose=True,
        )
        delta = abs(rerun["intent_err"] - arm_audit["splits"]["dev"]["intent_err"])
        arm_audit["determinism"] = {"absolute_delta": delta, "pass": delta <= 1e-9}
        all_pass = all_pass and arm_audit["determinism"]["pass"]
        audit["arms"][arm_name] = arm_audit

    audit["pass"] = all_pass
    (run_dir / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    manifest["independent_audit"] = {
        "pass": all_pass,
        "harness_sha256": actual_harness,
        "report": "audit.json",
    }
    manifest["valid"] = bool(manifest.get("complete") and manifest.get("valid") and all_pass)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    chart = run_dir / "chart.png"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "plots" / "make_chart.py"),
            "--benchmark-run",
            str(run_dir),
            "--out",
            str(chart),
        ],
        cwd=ROOT,
        check=True,
    )
    shutil.copy2(chart, ROOT / "plots" / "chart.png")
    print(json.dumps(manifest["independent_audit"], indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
