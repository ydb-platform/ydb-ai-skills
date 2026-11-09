#!/usr/bin/env python3
"""Run agent evals in disposable workspaces without the repository's answers."""

from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPTFOO_VERSION = "0.125.1"


def prepare_workspace(source: pathlib.Path, destination: pathlib.Path) -> None:
    """Copy installable content, never symlink back to the authoring checkout."""
    destination.mkdir(parents=True, exist_ok=True)
    # A separate root prevents the clients from inheriting repository instructions.
    subprocess.run(["git", "init", "--quiet", str(destination)], check=True)
    for skill in sorted((source / "skills").iterdir()):
        if not (skill / "SKILL.md").is_file():
            continue
        target = destination / ".agents" / "skills" / skill.name
        for item in sorted(skill.rglob("*")):
            relative = item.relative_to(skill)
            if any(part in {"evals", "tests", "__pycache__"} for part in relative.parts):
                continue
            if item.is_symlink():
                raise ValueError(f"Eval workspace does not accept skill symlinks: {item}")
            if item.is_file():
                copied = target / relative
                copied.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, copied)
        claude_target = destination / ".claude" / "skills" / skill.name
        claude_target.parent.mkdir(parents=True, exist_ok=True)
        # The link points only inside this temporary workspace.
        claude_target.symlink_to(pathlib.Path("../../.agents/skills") / skill.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=pathlib.Path)
    parser.add_argument("--model", default=os.environ.get("YDB_EVAL_MODEL", "gpt-6.1-sol"))
    parser.add_argument("--reasoning-effort", default=os.environ.get("YDB_EVAL_REASONING_EFFORT", "medium"))
    parser.add_argument("--artifacts-dir", type=pathlib.Path,
                        help="Keep preflight, raw evidence and default results here (default: a new temp directory)")
    parser.add_argument("--preflight-only", action="store_true", help="Check Codex isolation without model calls")
    parser.add_argument("promptfoo_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    config = args.config.resolve()
    if not config.is_file():
        parser.error(f"config does not exist: {config}")
    extra = args.promptfoo_args
    if extra[:1] == ["--"]:
        extra = extra[1:]
    uses_codex = "openai:codex-app-server" in config.read_text()
    if args.preflight_only and not uses_codex:
        parser.error("--preflight-only requires a Codex app-server config")
    try:
        with tempfile.TemporaryDirectory(prefix="ydb-agent-evals-") as temp:
            workspace = pathlib.Path(temp)
            solver = workspace / "solver"
            judge = workspace / "judge"
            prepare_workspace(ROOT, solver)
            judge.mkdir()
            subprocess.run(["git", "init", "--quiet", str(judge)], check=True)
            env = os.environ.copy()
            env["YDB_EVAL_WORKSPACE"] = str(solver)
            env["YDB_EVAL_JUDGE_WORKSPACE"] = str(judge)
            if uses_codex:
                artifacts = args.artifacts_dir.resolve() if args.artifacts_dir else pathlib.Path(
                    tempfile.mkdtemp(prefix="ydb-eval-results-"))
                if artifacts.exists() and any(artifacts.iterdir()):
                    raise ValueError(f"artifacts directory must be empty; use a new directory: {artifacts}")
                artifacts.mkdir(parents=True, exist_ok=True)
                spec = importlib.util.spec_from_file_location("codex_eval_server", ROOT / "scripts/codex-eval-server.py")
                isolation = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(isolation)
                wrapper = isolation.prepare(ROOT, solver, judge, artifacts, args.model, args.reasoning_effort)
                env["YDB_EVAL_CODEX_WRAPPER"] = str(wrapper)
                env["YDB_EVAL_MODEL"] = args.model
                env["YDB_EVAL_REASONING_EFFORT"] = args.reasoning_effort
                env["YDB_EVAL_EVIDENCE_DIR"] = str(artifacts / "evidence")
                env.setdefault("PROMPTFOO_CONFIG_DIR", str(artifacts / "promptfoo-state"))
                if not any(arg in {"-o", "--output"} or arg.startswith("--output=") for arg in extra):
                    extra = [*extra, "--output", str(artifacts / "results.json")]
                print(f"Codex isolation preflight passed; artifacts: {artifacts}", flush=True)
                print("Global user AGENTS.md remains inherited and is fingerprinted in preflight.json.", flush=True)
                if args.preflight_only:
                    return 0
            print("Agent workspace contains only the installed skills; evals stay with the runner.", flush=True)
            return subprocess.run(
                ["npx", f"promptfoo@{PROMPTFOO_VERSION}", "eval", "-c", str(config), *extra],
                cwd=ROOT, env=env,
            ).returncode
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f"Agent eval failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
