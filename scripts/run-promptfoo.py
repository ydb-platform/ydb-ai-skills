#!/usr/bin/env python3
"""Run agent evals in disposable workspaces without the repository's answers."""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent


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
    parser.add_argument("promptfoo_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    config = args.config.resolve()
    if not config.is_file():
        parser.error(f"config does not exist: {config}")
    extra = args.promptfoo_args
    if extra[:1] == ["--"]:
        extra = extra[1:]
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
            print("Agent workspace contains only the installed skills; evals stay with the runner.", flush=True)
            return subprocess.run(
                ["npx", "promptfoo@latest", "eval", "-c", str(config), *extra],
                cwd=ROOT, env=env,
            ).returncode
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Agent eval failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
