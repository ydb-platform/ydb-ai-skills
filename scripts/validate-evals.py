#!/usr/bin/env python3
"""Validate this repository's canonical Skill Eval cases without an agent runtime.

This is the repository contract, not a replacement for native Skill Eval
validation. In particular, model-scoring fields that the native reader would
ignore are rejected rather than silently changing a case's meaning.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
UNSUPPORTED_SCORING_FIELDS = {"threshold", "weight", "weights", "score", "scoring"}


class ValidationError(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValidationError(f"non-JSON numeric constant {value}")


def load_document(path: pathlib.Path) -> dict[str, object]:
    try:
        document = json.loads(
            path.read_text(),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise ValidationError(f"{path}: {error}") from error
    if not isinstance(document, dict):
        raise ValidationError(f"{path}: suite must be an object")
    return document


def discover_skills(root: pathlib.Path) -> tuple[str, ...]:
    return tuple(path.parent.name for path in sorted((root / "skills").glob("*/SKILL.md")))


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _suite(
    document: object, skill: str, case_key: str, errors: list[str]
) -> list[object]:
    if not isinstance(document, dict):
        errors.append("suite must be an object")
        return []
    if document.get("skill_name") != skill:
        errors.append(f"skill_name must be {skill!r}")
    unsupported = UNSUPPORTED_SCORING_FIELDS.intersection(document)
    if unsupported:
        errors.append(f"unsupported native scoring fields: {', '.join(sorted(unsupported))}")
    cases = document.get(case_key)
    if not isinstance(cases, list) or not cases:
        errors.append(f"{case_key} must be a non-empty array")
        return []
    return cases


def _case(
    case: object, index: int, ids: set[int], errors: list[str]
) -> bool:
    if not isinstance(case, dict):
        errors.append(f"case {index}: must be an object")
        return False
    case_id = case.get("id")
    if type(case_id) is not int or case_id <= 0:
        errors.append(f"case {index}: id must be a positive integer, not a boolean")
    elif case_id in ids:
        errors.append(f"case {index}: duplicate id {case_id}")
    else:
        ids.add(case_id)
    if not _text(case.get("prompt")):
        errors.append(f"case {index}: prompt must be a non-empty string")
    unsupported = UNSUPPORTED_SCORING_FIELDS.intersection(case)
    if unsupported:
        errors.append(
            f"case {index}: unsupported native scoring fields: {', '.join(sorted(unsupported))}"
        )
    return True


def validate_scenarios(document: object, skill: str) -> list[str]:
    errors: list[str] = []
    cases = _suite(document, skill, "evals", errors)
    ids: set[int] = set()
    names: set[str] = set()
    for index, case in enumerate(cases, 1):
        if not _case(case, index, ids, errors):
            continue
        name = case.get("name")
        if not _text(name):
            errors.append(f"case {index}: name must be a non-empty string")
        elif name in names:
            errors.append(f"case {index}: duplicate name {name!r}")
        else:
            names.add(name)
        expectations = case.get("expectations")
        if (
            not isinstance(expectations, list)
            or not expectations
            or not all(_text(value) for value in expectations)
        ):
            errors.append(f"case {index}: expectations must be a non-empty array of non-empty strings")
        # The native reader also permits expected_output as a fallback when
        # expectations is empty. This repository keeps explicit expectations.
        for field in ("expected_output", "covers"):
            if not _text(case.get(field)):
                errors.append(f"case {index}: {field} must be a non-empty string")
        if "category" in case and not _text(case["category"]):
            errors.append(f"case {index}: category must be a non-empty string when present")
        files = case.get("files")
        if not isinstance(files, list) or not all(_text(value) for value in files):
            errors.append(f"case {index}: files must be an array of non-empty strings")
    return errors


def validate_activations(document: object, skill: str) -> list[str]:
    errors: list[str] = []
    cases = _suite(document, skill, "cases", errors)
    if isinstance(document, dict) and (
        type(document.get("version")) is not int or document["version"] != 1
    ):
        errors.append("activation version must be 1")
    ids: set[int] = set()
    positive = negative = 0
    for index, case in enumerate(cases, 1):
        if not _case(case, index, ids, errors):
            continue
        should_activate = case.get("should_activate")
        if type(should_activate) is not bool:
            errors.append(f"case {index}: should_activate must be a boolean")
        elif should_activate:
            positive += 1
        else:
            negative += 1
        if "note" in case and not isinstance(case["note"], str):
            errors.append(f"case {index}: note must be a string when present")
    if positive < 5 or negative < 5:
        errors.append(
            f"need >=5 positive and >=5 negative activations; found {positive} positive and {negative} negative"
        )
    return errors


def validate_repository(root: pathlib.Path) -> list[str]:
    errors: list[str] = []
    scenarios: dict[str, dict[str, object]] = {}
    skills = discover_skills(root)
    if not skills:
        return ["no skills/*/SKILL.md files found"]
    for skill in skills:
        for kind, validate in (
            ("scenarios", validate_scenarios),
            ("activations", validate_activations),
        ):
            path = root / "skills" / skill / "evals" / f"{kind}.json"
            try:
                document = load_document(path)
            except ValidationError as error:
                errors.append(str(error))
                continue
            issues = validate(document, skill)
            errors.extend(f"{path.relative_to(root)}: {error}" for error in issues)
            if kind == "scenarios" and not issues:
                scenarios.update((f"{skill}:{case['name']}", case) for case in document["evals"])
    legacy_dirs = {root / "tests" / skill for skill in skills}
    legacy_dirs.update((root / "tests").glob("ydb-*"))
    for directory in sorted(legacy_dirs):
        for pattern in ("*.yaml", "*.yml"):
            for path in sorted(directory.glob(pattern)):
                errors.append(
                    f"{path.relative_to(root)}: duplicate legacy case source; edit skills/<skill>/evals/*.json"
                )
    if not errors:
        errors.extend(validate_runtime_checks(root, scenarios))
    return errors


def validate_runtime_checks(
    root: pathlib.Path, scenarios: dict[str, dict[str, object]]
) -> list[str]:
    path = root / "tests/runtime/scenario-checks.json"
    if not path.exists():
        return []
    try:
        metadata = load_document(path)
    except ValidationError as error:
        return [str(error)]
    errors: list[str] = []
    for key, entry in metadata.items():
        prefix = f"{path.relative_to(root)}: {key}"
        if key not in scenarios:
            errors.append(f"{prefix}: unknown canonical scenario")
            continue
        if not isinstance(entry, dict) or set(entry) - {"metric", "checks", "additional_checks"}:
            errors.append(f"{prefix}: expected metric/checks metadata without duplicate case text")
            continue
        if "metric" in entry and not _text(entry["metric"]):
            errors.append(f"{prefix}: metric must be a non-empty string")
        checks = entry.get("checks", {})
        if not isinstance(checks, dict):
            errors.append(f"{prefix}: checks must be an object keyed by expectation index")
            continue
        expectations = scenarios[key]["expectations"]
        for index, check in checks.items():
            if not index.isdecimal() or str(int(index)) != index or int(index) >= len(expectations):
                errors.append(f"{prefix}: invalid expectation index {index!r}")
                continue
            if (
                not isinstance(check, dict)
                or check.get("type") != "contains"
                or not _text(check.get("value"))
            ):
                errors.append(f"{prefix}: check {index} must be a contains check with a non-empty value")
                continue
            if check["value"] not in expectations[int(index)]:
                errors.append(f"{prefix}: contains value does not match expectation {index}")
        additional = entry.get("additional_checks", [])
        if not isinstance(additional, list):
            errors.append(f"{prefix}: additional_checks must be an array")
            continue
        for check in additional:
            if not isinstance(check, dict):
                errors.append(f"{prefix}: additional check must be an object")
                continue
            index = check.get("expectation")
            if type(index) is not int or not 0 <= index < len(expectations):
                errors.append(f"{prefix}: invalid additional expectation index {index!r}")
            elif check.get("type") != "contains" or not _text(check.get("value")):
                errors.append(f"{prefix}: additional check must be a contains check with a non-empty value")
            elif check["value"] not in expectations[index]:
                errors.append(f"{prefix}: additional contains value does not match expectation {index}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=ROOT)
    args = parser.parse_args()
    errors = validate_repository(args.root.resolve())
    if errors:
        print("validate-evals: violations found:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    print(f"validate-evals: ok ({len(discover_skills(args.root))} skill packages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
