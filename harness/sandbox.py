"""Restricted solver execution. No network, no GT access, timeouts."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Paths the solver must never touch (checked via static AST + runtime env)
FORBIDDEN_PATH_SUBSTRINGS = (
    "data/gt",
    "data\\gt",
    "/gt/",
    "\\gt\\",
    "prepare.py",
    "HARNESS.sha256",
)


class SandboxViolation(Exception):
    pass


def static_check_source(src: str) -> List[str]:
    """AST-level checks for obvious GT reads / network / escapes."""
    violations = []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"syntax_error:{e}"]

    forbidden_calls = {
        "urlopen",
        "urlretrieve",
        "Request",
        "socket",
        "connect",
        "system",
        "popen",
        "Popen",
        "fork",
        "execv",
        "execve",
    }
    forbidden_imports = {
        "socket",
        "http",
        "http.client",
        "urllib",
        "urllib.request",
        "requests",
        "subprocess",
        "multiprocessing",
        "ctypes",
        "importlib",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden_imports or alias.name in forbidden_imports:
                    violations.append(f"forbidden_import:{alias.name}")
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.split(".")[0] in forbidden_imports or mod in forbidden_imports:
                violations.append(f"forbidden_import_from:{mod}")
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in forbidden_calls:
                violations.append(f"forbidden_call:{name}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for frag in FORBIDDEN_PATH_SUBSTRINGS:
                if frag in node.value:
                    violations.append(f"forbidden_path_literal:{frag}")
        if isinstance(node, ast.JoinedStr):
            # f-strings — skip deep check
            pass
    return violations


def run_solver_on_task(
    solver_path: Path,
    task_dir: Path,
    scratch_dir: Path,
    timeout_s: float = 90.0,
    repo_root: Optional[Path] = None,
) -> Tuple[Optional[str], List[str], float]:
    """
    Execute solver.solve(task_dir) in a subprocess.

    Returns (build_module_source | None, violations, wall_s).
    """
    solver_path = Path(solver_path).resolve()
    task_dir = Path(task_dir).resolve()
    scratch_dir = Path(scratch_dir).resolve()
    scratch_dir.mkdir(parents=True, exist_ok=True)
    out_path = scratch_dir / "build_module.py"
    err_path = scratch_dir / "solver_stderr.txt"
    meta_path = scratch_dir / "solver_meta.json"

    # Static check solver.py itself
    try:
        solver_src = solver_path.read_text()
        static_v = static_check_source(solver_src)
    except Exception as e:
        return None, [f"solver_read_fail:{e}"], 0.0

    runner = textwrap.dedent(
        f"""\
        import json, sys, time, traceback
        from pathlib import Path

        solver_path = Path({str(solver_path)!r})
        task_dir = Path({str(task_dir)!r})
        out_path = Path({str(out_path)!r})
        meta_path = Path({str(meta_path)!r})
        repo_root = Path({str(repo_root or solver_path.parent)!r})

        # Block GT reads via open wrapper (best-effort)
        import builtins
        _real_open = builtins.open
        FORBIDDEN = ("data/gt", "data\\\\gt", "/gt/", "prepare.py")

        def _safe_open(file, *args, **kwargs):
            s = str(file)
            for frag in FORBIDDEN:
                if frag in s:
                    raise PermissionError(f"sandbox forbidden path: {{s}}")
            # also block absolute paths into gt
            try:
                p = Path(s).resolve()
                if (repo_root / "data" / "gt") in p.parents or p == (repo_root / "data" / "gt"):
                    raise PermissionError(f"sandbox forbidden gt: {{s}}")
                if p.name == "prepare.py" and p.parent == repo_root:
                    raise PermissionError("sandbox forbidden prepare.py")
            except PermissionError:
                raise
            except Exception:
                pass
            return _real_open(file, *args, **kwargs)

        builtins.open = _safe_open

        sys.path.insert(0, str(solver_path.parent))
        # strip network-ish env
        for k in list(__import__("os").environ):
            if k.startswith("http_proxy") or k.startswith("HTTP") or k.startswith("ALL_PROXY"):
                __import__("os").environ.pop(k, None)

        t0 = time.time()
        meta = {{"ok": False, "error": None, "wall_s": 0.0}}
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("solver_mod", solver_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "solve"):
                raise RuntimeError("solver.py must define solve(task_dir) -> str")
            src = mod.solve(str(task_dir))
            if not isinstance(src, str):
                raise TypeError("solve() must return str (Python source of build module)")
            out_path.write_text(src)
            meta["ok"] = True
        except Exception as e:
            meta["error"] = traceback.format_exc()
            out_path.write_text("")
        meta["wall_s"] = time.time() - t0
        meta_path.write_text(json.dumps(meta))
        if not meta["ok"]:
            sys.exit(2)
        """
    )

    runner_path = scratch_dir / "_run_solver.py"
    runner_path.write_text(runner)

    env = os.environ.copy()
    # Encourage offline
    env["AUTORGEN_SANDBOX"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    # Remove proxy vars
    for k in list(env):
        if "proxy" in k.lower():
            env.pop(k, None)

    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(runner_path)],
            cwd=str(scratch_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        wall = time.time() - t0
        err_path.write_text(proc.stderr or "")
        violations = list(static_v)
        if proc.returncode != 0:
            meta = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                except Exception:
                    pass
            violations.append(f"solver_exit:{proc.returncode}")
            if meta.get("error"):
                violations.append("solver_exception")
            return None, violations, wall

        src = out_path.read_text() if out_path.exists() else ""
        if not src.strip():
            return None, violations + ["empty_build_module"], wall

        # Static check emitted module too
        emit_v = static_check_source(src)
        violations.extend(emit_v)
        if emit_v:
            return None, violations, wall

        return src, violations, wall
    except subprocess.TimeoutExpired:
        wall = time.time() - t0
        return None, static_v + ["solver_timeout"], wall
    except Exception as e:
        wall = time.time() - t0
        return None, static_v + [f"sandbox_error:{e}"], wall


def eval_build_member(
    build_src: str,
    kwargs: Dict[str, Any],
    timeout_s: float = 20.0,
    scratch_dir: Optional[Path] = None,
) -> Tuple[Optional[Path], str]:
    """
    Run build(**kwargs) in subprocess, export STEP to scratch.
    Returns (step_path | None, flag).
    """
    if scratch_dir is None:
        scratch_dir = Path(tempfile.mkdtemp(prefix="autoregen_member_"))
    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    step_path = scratch_dir / "out.step"
    mod_path = scratch_dir / "build_mod.py"
    mod_path.write_text(build_src)
    runner = textwrap.dedent(
        f"""\
        import json, sys
        from pathlib import Path
        import importlib.util
        kwargs = json.loads({json.dumps(json.dumps(kwargs))})
        mod_path = Path({str(mod_path)!r})
        step_path = Path({str(step_path)!r})
        spec = importlib.util.spec_from_file_location("build_mod", mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        solid = mod.build(**kwargs)
        import cadquery as cq
        if hasattr(solid, "val"):
            cq.exporters.export(solid, str(step_path))
        else:
            cq.exporters.export(solid, str(step_path))
        """
    )
    rpath = scratch_dir / "_eval_member.py"
    rpath.write_text(runner)
    try:
        proc = subprocess.run(
            [sys.executable, str(rpath)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(scratch_dir),
        )
        if proc.returncode != 0 or not step_path.exists():
            return None, f"member_fail:{proc.stderr[-200:] if proc.stderr else proc.returncode}"
        return step_path, "ok"
    except subprocess.TimeoutExpired:
        return None, "member_timeout"
    except Exception as e:
        return None, f"member_error:{e}"
