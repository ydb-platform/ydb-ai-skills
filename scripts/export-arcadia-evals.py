#!/usr/bin/env python3
"""Generate Arcadia Skill Eval scenarios from the promptfoo test cases.

The promptfoo YAML files under tests/<skill>/ are the editable source.  The
generated skills/<skill>/evals/scenarios.json files travel with each skill when
it is synchronized to Arcadia.

This parser deliberately supports the small YAML subset used by this repo, so
generation has no third-party dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL_TEST_DIRS = {
    skill_dir.name: ROOT / "tests" / skill_dir.name
    for skill_dir in sorted((ROOT / "skills").iterdir())
    if (skill_dir / "SKILL.md").is_file()
    and (ROOT / "tests" / skill_dir.name).is_dir()
}

DESCRIPTION_RE = re.compile(r"^description:\s*(.+?)\s*$")
BLOCK_KEY_RE = {
    "user_prompt": re.compile(r"^(\s*)user_prompt:\s*\|[-+]?\s*$"),
    "rubric": re.compile(r"^(\s*)value:\s*\|[-+]?\s*$"),
}


class CaseError(ValueError):
    """A promptfoo case cannot be converted safely."""


def extract_block(lines: list[str], pattern: re.Pattern[str], path: pathlib.Path) -> str:
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue

        key_indent = len(match.group(1))
        block: list[str] = []
        for candidate in lines[index + 1 :]:
            if not candidate.strip():
                block.append("")
                continue
            indent = len(candidate) - len(candidate.lstrip(" "))
            if indent <= key_indent:
                break
            block.append(candidate)

        non_empty_indents = [
            len(item) - len(item.lstrip(" ")) for item in block if item.strip()
        ]
        if not non_empty_indents:
            raise CaseError(f"{path}: empty block for {pattern.pattern}")
        dedent = min(non_empty_indents)
        value = "\n".join(
            item[dedent:] if item.strip() else "" for item in block
        ).strip()
        if not value:
            raise CaseError(f"{path}: empty block for {pattern.pattern}")
        return value

    raise CaseError(f"{path}: missing block for {pattern.pattern}")


def flush_bullet(
    target: list[str], words: list[str], failure_condition: bool
) -> None:
    if not words:
        return
    value = " ".join(words).strip()
    if failure_condition:
        value = f"Avoids this failure condition: {value}"
    target.append(value)
    words.clear()


def rubric_expectations(rubric: str, path: pathlib.Path) -> list[str]:
    expectations: list[str] = []
    current: list[str] = []
    failure_condition = False
    ignoring_partial_credit = False

    for raw_line in rubric.splitlines():
        stripped = raw_line.strip()
        lowered = stripped.lower()

        if lowered.startswith("full fail if the response:"):
            flush_bullet(expectations, current, failure_condition)
            failure_condition = True
            ignoring_partial_credit = False
            continue

        if lowered.startswith("partial credit"):
            flush_bullet(expectations, current, failure_condition)
            ignoring_partial_credit = True
            continue

        if lowered.startswith("fail if "):
            flush_bullet(expectations, current, failure_condition)
            expectations.append(f"Avoids this failure condition: {stripped[8:]}")
            ignoring_partial_credit = False
            continue

        if stripped.startswith("- "):
            flush_bullet(expectations, current, failure_condition)
            ignoring_partial_credit = False
            current.append(stripped[2:])
            continue

        if not stripped:
            flush_bullet(expectations, current, failure_condition)
            continue

        if current:
            current.append(stripped)
        elif ignoring_partial_credit:
            continue
        elif lowered in {"the response should:"}:
            continue

    flush_bullet(expectations, current, failure_condition)

    if not expectations:
        prose = " ".join(line.strip() for line in rubric.splitlines() if line.strip())
        if prose:
            expectations.append(prose)
    if not expectations:
        raise CaseError(f"{path}: rubric has no expectations")
    return expectations


def stable_id(skill_name: str, case_name: str) -> int:
    digest = hashlib.sha256(f"{skill_name}/{case_name}".encode()).digest()
    # Arcadia examples use numeric ids. Keep them positive and deterministic
    # without making ids of existing cases move when a new case is inserted.
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def parse_case(skill_name: str, path: pathlib.Path) -> dict[str, object]:
    lines = path.read_text().splitlines()
    description_match = next(
        (DESCRIPTION_RE.match(line) for line in lines if DESCRIPTION_RE.match(line)),
        None,
    )
    if not description_match:
        raise CaseError(f"{path}: missing top-level description")

    description = description_match.group(1)
    prompt = extract_block(lines, BLOCK_KEY_RE["user_prompt"], path)
    rubric = extract_block(lines, BLOCK_KEY_RE["rubric"], path)
    expectations = rubric_expectations(rubric, path)
    name = path.stem

    return {
        "id": stable_id(skill_name, name),
        "name": name,
        "category": name.split("-", 1)[0],
        "prompt": prompt,
        "expected_output": (
            f"A correct response for “{description}”, including this primary "
            f"requirement: {expectations[0]}"
        ),
        "files": [],
        "expectations": expectations,
        "covers": description,
    }


def build_document(skill_name: str, tests_dir: pathlib.Path) -> dict[str, object]:
    cases = [parse_case(skill_name, path) for path in sorted(tests_dir.glob("*.yaml"))]
    if not cases:
        raise CaseError(f"{tests_dir}: no promptfoo YAML cases")

    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise CaseError(f"{tests_dir}: deterministic id collision")

    return {
        "skill_name": skill_name,
        "description": (
            "Generated from the promptfoo cases under "
            f"tests/{skill_name}; edit the YAML sources, then regenerate."
        ),
        "evals": cases,
    }


def validate_document(document: dict[str, object], expected_skill: str) -> None:
    if document.get("skill_name") != expected_skill:
        raise CaseError(f"skill_name must be {expected_skill!r}")
    cases = document.get("evals")
    if not isinstance(cases, list) or not cases:
        raise CaseError("evals must be a non-empty array")

    ids: set[int] = set()
    names: set[str] = set()
    required = {
        "id",
        "name",
        "prompt",
        "expected_output",
        "files",
        "expectations",
        "covers",
    }
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise CaseError(f"case {index}: must be an object")
        missing = required - case.keys()
        if missing:
            raise CaseError(f"case {index}: missing fields {sorted(missing)}")
        case_id = case["id"]
        name = case["name"]
        if not isinstance(case_id, int) or case_id <= 0 or case_id in ids:
            raise CaseError(f"case {index}: id must be a unique positive integer")
        if not isinstance(name, str) or not name or name in names:
            raise CaseError(f"case {index}: name must be a unique non-empty string")
        ids.add(case_id)
        names.add(name)
        for field in ("prompt", "expected_output", "covers"):
            if not isinstance(case[field], str) or not case[field].strip():
                raise CaseError(f"case {name}: {field} must be a non-empty string")
        if not isinstance(case["files"], list):
            raise CaseError(f"case {name}: files must be an array")
        if (
            not isinstance(case["expectations"], list)
            or not case["expectations"]
            or not all(
                isinstance(value, str) and value.strip()
                for value in case["expectations"]
            )
        ):
            raise CaseError(f"case {name}: expectations must be non-empty strings")


def render(document: dict[str, object]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if generated scenarios are missing or out of date",
    )
    args = parser.parse_args()

    total = 0
    stale: list[pathlib.Path] = []
    try:
        for skill_name, tests_dir in SKILL_TEST_DIRS.items():
            document = build_document(skill_name, tests_dir)
            validate_document(document, skill_name)
            output = ROOT / "skills" / skill_name / "evals" / "scenarios.json"
            expected = render(document)
            total += len(document["evals"])

            if args.check:
                if not output.is_file() or output.read_text() != expected:
                    stale.append(output)
                continue

            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(expected)
            print(f"arcadia-evals: wrote {len(document['evals'])} cases to {output.relative_to(ROOT)}")
    except (CaseError, OSError) as error:
        print(f"arcadia-evals: {error}", file=sys.stderr)
        return 1

    if stale:
        print("arcadia-evals: generated files are missing or stale:", file=sys.stderr)
        for path in stale:
            print(f"  {path.relative_to(ROOT)}", file=sys.stderr)
        print("run: python3 scripts/export-arcadia-evals.py", file=sys.stderr)
        return 1

    if args.check:
        print(f"arcadia-evals: ok ({total} scenarios across {len(SKILL_TEST_DIRS)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
