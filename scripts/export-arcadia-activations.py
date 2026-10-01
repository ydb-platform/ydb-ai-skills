#!/usr/bin/env python3
"""Generate Arcadia activation cases from the local Promptfoo routing suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROUTING_DIR = ROOT / "tests" / "routing"
SKILLS = tuple(
    skill_dir.name
    for skill_dir in sorted((ROOT / "skills").iterdir())
    if (skill_dir / "SKILL.md").is_file()
    and (ROOT / "tests" / skill_dir.name).is_dir()
)
DESCRIPTION_RE = re.compile(r"^description:\s*(.+?)\s*$")
PROMPT_RE = re.compile(r"^(\s*)user_prompt:\s*\|[-+]?\s*$")


class CaseError(ValueError):
    pass


def block(lines: list[str], pattern: re.Pattern[str], path: pathlib.Path) -> str:
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        key_indent = len(match.group(1))
        values: list[str] = []
        for candidate in lines[index + 1 :]:
            if not candidate.strip():
                values.append("")
                continue
            indent = len(candidate) - len(candidate.lstrip(" "))
            if indent <= key_indent:
                break
            values.append(candidate)
        indents = [len(v) - len(v.lstrip(" ")) for v in values if v.strip()]
        if not indents:
            break
        dedent = min(indents)
        return "\n".join(v[dedent:] if v.strip() else "" for v in values).strip()
    raise CaseError(f"{path}: missing user_prompt block")


def expected_target(lines: list[str], path: pathlib.Path) -> str:
    for index, line in enumerate(lines):
        if line.strip() != "- type: regex":
            continue
        for candidate in lines[index + 1 :]:
            stripped = candidate.strip()
            if stripped.startswith("- type:"):
                break
            if stripped.startswith("value:"):
                value = stripped.split(":", 1)[1].strip()
                for skill in SKILLS:
                    if skill in value:
                        return skill
                if "none" in value:
                    return "none"
                raise CaseError(f"{path}: unsupported positive regex {value!r}")
    raise CaseError(f"{path}: expected one deterministic positive regex assertion")


def stable_id(name: str) -> int:
    digest = hashlib.sha256(f"routing/{name}".encode()).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def routing_cases() -> list[dict[str, object]]:
    result = []
    for path in sorted(ROUTING_DIR.glob("*.yaml")):
        lines = path.read_text().splitlines()
        match = next((DESCRIPTION_RE.match(line) for line in lines if DESCRIPTION_RE.match(line)), None)
        if not match:
            raise CaseError(f"{path}: missing description")
        result.append({
            "id": stable_id(path.stem),
            "name": path.stem,
            "prompt": block(lines, PROMPT_RE, path),
            "target": expected_target(lines, path),
            "note": match.group(1),
        })
    if not result:
        raise CaseError(f"{ROUTING_DIR}: no routing cases")
    return result


def document(skill: str, cases: list[dict[str, object]]) -> dict[str, object]:
    exported = [
        {
            "id": case["id"],
            "prompt": case["prompt"],
            "should_activate": case["target"] == skill,
            "note": f"{case['note']} Expected router target: {case['target']}.",
        }
        for case in cases
    ]
    positive = sum(bool(case["should_activate"]) for case in exported)
    negative = len(exported) - positive
    if positive < 5 or negative < 5:
        raise CaseError(
            f"{skill}: activation suite needs at least 5 positive and 5 negative cases; "
            f"found {positive} positive and {negative} negative"
        )
    return {"version": 1, "skill_name": skill, "cases": exported}


def render(value: dict[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        cases = routing_cases()
        stale = []
        for skill in SKILLS:
            output = ROOT / "skills" / skill / "evals" / "activations.json"
            expected = render(document(skill, cases))
            if args.check:
                if not output.is_file() or output.read_text() != expected:
                    stale.append(output)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(expected)
                print(f"wrote {output.relative_to(ROOT)}")
        if stale:
            for path in stale:
                print(f"stale: {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        if args.check:
            print(f"Arcadia activations: ok ({len(cases)} routing cases × {len(SKILLS)} skills)")
        return 0
    except CaseError as error:
        print(f"activation export failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
