#!/usr/bin/env python3
"""Validate YDB skill scenarios and activations with local Arcadia tooling."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = tuple(
    skill_dir.name
    for skill_dir in sorted((ROOT / "skills").iterdir())
    if (skill_dir / "SKILL.md").is_file()
    and (ROOT / "tests" / skill_dir.name).is_dir()
)
CASE_TYPES = ("scenarios", "activations")


def run(command: list[str], cwd: pathlib.Path) -> None:
    print(f"\n$ {shlex.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def locate_swebench(ya: pathlib.Path, cwd: pathlib.Path) -> pathlib.Path:
    result = subprocess.run(
        [str(ya), "tool", "swebench", "--print-path"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    for line in reversed((result.stdout + "\n" + result.stderr).splitlines()):
        candidate = pathlib.Path(line.strip())
        if candidate.name == "swebenchcli" and candidate.is_file():
            return candidate
    raise ValueError("ya tool swebench --print-path did not return an executable")


def paths(skill: str) -> tuple[pathlib.Path, dict[str, pathlib.Path]]:
    skill_root = ROOT / "skills" / skill
    return skill_root / "SKILL.md", {
        case_type: skill_root / "evals" / f"{case_type}.json"
        for case_type in CASE_TYPES
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate both YDB skill case types with local Arcadia SWE Bench."
    )
    parser.add_argument(
        "--arcadia-root",
        type=pathlib.Path,
        default=pathlib.Path(os.environ.get("ARCADIA_ROOT", "~/arcadia")).expanduser(),
    )
    parser.add_argument(
        "--run-case",
        metavar="SKILL:NAME",
        help="run one model-judged response scenario, for example ydb-core:onboarding",
    )
    parser.add_argument(
        "--run-activations",
        action="store_true",
        help="run complete positive/negative activation suites for all skills",
    )
    parser.add_argument(
        "--build-datasets",
        action="store_true",
        help="build both complete local datasets without calling a model",
    )
    parser.add_argument("--agent", default="claude")
    parser.add_argument("--judge-agent", default=None)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help="result directory for a model run; defaults to temporary directories",
    )
    args = parser.parse_args()

    arcadia_root = args.arcadia_root.resolve()
    ya = arcadia_root / "ya"
    if not ya.is_file():
        print(f"Arcadia ya executable not found: {ya}", file=sys.stderr)
        return 1

    try:
        swebench = locate_swebench(ya, arcadia_root)
        run([sys.executable, "scripts/export-arcadia-evals.py", "--check"], ROOT)
        run([sys.executable, "scripts/export-arcadia-activations.py", "--check"], ROOT)
        run([sys.executable, "scripts/eval-coverage.py", "--check"], ROOT)
        run([sys.executable, "scripts/validate-skills.py"], ROOT)

        for skill in SKILLS:
            skill_file, case_files = paths(skill)
            run(
                [str(swebench), "skill", "validate", "--token", "local-validation", "--skill", str(skill_file)],
                arcadia_root,
            )
            for case_type, case_file in case_files.items():
                run(
                    [str(swebench), "skill", "discover", "cases", "--token", "local-validation", "--skill", str(skill_file), "--case-type", case_type],
                    arcadia_root,
                )
                if args.build_datasets:
                    dataset_output = pathlib.Path(
                        tempfile.mkdtemp(prefix=f"ydb-skill-{case_type}-{skill}-")
                    )
                    run(
                        [str(swebench), "dataset", "build-from", "skill", "--token", "local-validation", "--skill", str(skill_file), "--cases", str(case_file), "--case-type", case_type, "--dataset-output", str(dataset_output)],
                        arcadia_root,
                    )
                    print(f"Dataset: {dataset_output}")

        if args.run_case:
            if ":" not in args.run_case:
                raise ValueError("--run-case must use SKILL:NAME")
            skill, name = args.run_case.split(":", 1)
            if skill not in SKILLS or not name:
                raise ValueError(f"--run-case skill must be one of {', '.join(SKILLS)}")
            skill_file, case_files = paths(skill)
            scenarios = json.loads(case_files["scenarios"].read_text())
            matches = [case for case in scenarios.get("evals", []) if case.get("name") == name]
            if len(matches) != 1:
                raise ValueError(f"--run-case name must match exactly one scenario; found {len(matches)}")
            output = args.output or pathlib.Path(
                tempfile.mkdtemp(prefix=f"ydb-skill-eval-{skill}-{name}-")
            )
            run(
                [str(swebench), "skill", "local-eval", "--token", "local-validation", "--skill", str(skill_file), "--cases", str(case_files["scenarios"]), "--case-type", "scenarios", "--include-id", str(matches[0]["id"]), "--agent", args.agent, "--judge-agent", args.judge_agent or args.agent, "--arcadia", "isolated", "--output", str(output), "--fail-on-incomplete"],
                arcadia_root,
            )
            print(f"\nModel-judged report: {output / 'report.html'}")

        if args.run_activations:
            for skill in SKILLS:
                skill_file, case_files = paths(skill)
                output = (
                    args.output / f"activations-{skill}"
                    if args.output
                    else pathlib.Path(tempfile.mkdtemp(prefix=f"ydb-skill-activations-{skill}-"))
                )
                run(
                    [str(swebench), "skill", "local-eval", "--token", "local-validation", "--skill", str(skill_file), "--cases", str(case_files["activations"]), "--case-type", "activations", "--agent", args.agent, "--arcadia", "isolated", "--output", str(output), "--fail-on-incomplete"],
                    arcadia_root,
                )
                print(f"\nActivation report: {output / 'report.html'}")
    except (subprocess.CalledProcessError, ValueError) as error:
        print(f"\nvalidation failed: {error}", file=sys.stderr)
        return 1

    print("\nArcadia eval validation: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
