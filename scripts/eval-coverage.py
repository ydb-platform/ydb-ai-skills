#!/usr/bin/env python3
"""Report and validate requirement, rule, and activation coverage."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = tuple(
    skill_dir.name
    for skill_dir in sorted((ROOT / "skills").iterdir())
    if (skill_dir / "SKILL.md").is_file()
    and (ROOT / "tests" / skill_dir.name).is_dir()
)
RULE_RE = re.compile(r"^### (RULE-[A-Z]+-\d+):", re.MULTILINE)


def load_json(path: pathlib.Path):
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []

    scenarios: dict[str, dict[str, object]] = {}
    expectation_count = 0
    category_counts: Counter[str] = Counter()
    for skill in SKILLS:
        doc = load_json(ROOT / "skills" / skill / "evals" / "scenarios.json")
        for case in doc.get("evals", []):
            key = f"{skill}:{case['name']}"
            scenarios[key] = case
            expectation_count += len(case.get("expectations", []))
            category_counts[f"{skill}/{case.get('category', 'uncategorized')}"] += 1

    manifest = load_json(ROOT / "evals" / "coverage.json")
    requirements = manifest.get("requirements", [])
    ids: set[str] = set()
    total_weight = covered_weight = 0
    critical_total = critical_covered = 0
    missing_requirements = []
    by_skill = defaultdict(lambda: [0, 0])
    for req in requirements:
        req_id = req.get("id")
        if not isinstance(req_id, str) or not req_id or req_id in ids:
            errors.append(f"invalid or duplicate requirement id: {req_id!r}")
            continue
        ids.add(req_id)
        weight = req.get("weight")
        cases = req.get("cases")
        skill = req.get("skill")
        if skill not in SKILLS or not isinstance(weight, int) or weight <= 0:
            errors.append(f"{req_id}: invalid skill or weight")
            continue
        if not isinstance(cases, list) or not cases:
            errors.append(f"{req_id}: cases must be non-empty")
            cases = []
        missing = [case for case in cases if case not in scenarios]
        covered = bool(cases) and not missing
        if missing:
            errors.append(f"{req_id}: unknown scenario(s): {', '.join(missing)}")
        total_weight += weight
        by_skill[skill][1] += weight
        if weight >= 3:
            critical_total += weight
        if covered:
            covered_weight += weight
            by_skill[skill][0] += weight
            if weight >= 3:
                critical_covered += weight
        else:
            missing_requirements.append(req_id)

    rule_locations: dict[str, list[str]] = defaultdict(list)
    rule_covered: dict[str, bool] = {}
    for path in sorted((ROOT / "skills").glob("*/rules/**/*.md")):
        skill = path.relative_to(ROOT / "skills").parts[0]
        for rule_id in RULE_RE.findall(path.read_text()):
            qualified = f"{skill}:{rule_id}"
            rule_locations[rule_id].append(str(path.relative_to(ROOT)))
            rule_covered[qualified] = any(
                key.startswith(f"{skill}:")
                and rule_id in json.dumps(case, ensure_ascii=False)
                for key, case in scenarios.items()
            )
    duplicates = {rule: paths for rule, paths in rule_locations.items() if len(paths) > 1}
    for rule, paths in duplicates.items():
        errors.append(f"duplicate rule id {rule}: {', '.join(paths)}")
    uncovered_rules = sorted(rule for rule, covered in rule_covered.items() if not covered)
    if uncovered_rules:
        errors.append(f"uncovered rules: {', '.join(uncovered_rules)}")

    activation = {}
    for skill in SKILLS:
        doc = load_json(ROOT / "skills" / skill / "evals" / "activations.json")
        cases = doc.get("cases", [])
        positive = sum(case.get("should_activate") is True for case in cases)
        negative = sum(case.get("should_activate") is False for case in cases)
        activation[skill] = {"positive": positive, "negative": negative, "total": len(cases)}
        if positive < 5 or negative < 5:
            errors.append(f"{skill}: need >=5 positive and >=5 negative activations")

    result = {
        "requirements": {
            "covered": len(requirements) - len(missing_requirements),
            "total": len(requirements),
            "weighted_coverage_percent": round(100 * covered_weight / total_weight, 1) if total_weight else 0,
            "critical_coverage_percent": round(100 * critical_covered / critical_total, 1) if critical_total else 0,
            "by_skill": {skill: round(100 * values[0] / values[1], 1) for skill, values in by_skill.items()},
            "missing": missing_requirements,
        },
        "rules": {
            "covered": sum(rule_covered.values()),
            "total": len(rule_covered),
            "coverage_percent": round(100 * sum(rule_covered.values()) / len(rule_covered), 1) if rule_covered else 0,
            "uncovered": uncovered_rules,
            "duplicate_ids": duplicates,
        },
        "suite": {
            "scenarios": len(scenarios),
            "expectations": expectation_count,
            "categories": dict(sorted(category_counts.items())),
            "activations": activation,
        },
        "errors": errors,
    }

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        req = result["requirements"]
        rules = result["rules"]
        print(f"Behavior coverage: {req['weighted_coverage_percent']:.1f}% ({req['covered']}/{req['total']} requirements)")
        print(f"Critical coverage: {req['critical_coverage_percent']:.1f}%")
        print(f"Explicit rule coverage: {rules['coverage_percent']:.1f}% ({rules['covered']}/{rules['total']})")
        print(f"Response suite: {len(scenarios)} scenarios, {expectation_count} expectations")
        for skill, counts in activation.items():
            print(f"Activation {skill}: {counts['positive']} positive, {counts['negative']} negative")
        if errors:
            print("Coverage validation errors:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)

    return 1 if args.check and errors else 0


if __name__ == "__main__":
    sys.exit(main())
