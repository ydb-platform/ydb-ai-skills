"""Regression checks for canonical-case integrity and portable skill packages."""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[2]


def load_script(filename: str):
    spec = importlib.util.spec_from_file_location(filename, REPO / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NATIVE = load_script("validate-evals.py")
SKILLS = load_script("validate-skills.py")
COVERAGE = load_script("eval-coverage.py")


def scenario_suite(skill="ydb-sample"):
    return {
        "skill_name": skill,
        "evals": [{
            "id": 1,
            "name": "example",
            "prompt": "Explain a YDB query.\n",
            "expected_output": "A grounded explanation.",
            "expectations": ["Use correct YDB syntax.\nFull fail if syntax is invented.\n"],
            "files": [],
            "covers": "Query explanation",
        }],
    }


def activation_suite(skill="ydb-sample"):
    return {
        "version": 1,
        "skill_name": skill,
        "cases": [
            {"id": index + 1, "prompt": f"Request {index + 1}", "should_activate": index < 5}
            for index in range(10)
        ],
    }


class NativeEvalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ydb-native-evals-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.write_skill("ydb-sample")

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def write_skill(self, name):
        package = self.root / "skills" / name
        package.mkdir(parents=True)
        (package / "SKILL.md").write_text(f"---\nname: {name}\ndescription: YDB queries\n---\n")
        self.write_json(package / "evals/scenarios.json", scenario_suite(name))
        self.write_json(package / "evals/activations.json", activation_suite(name))
        return package

    def write_coverage(self, requirements=None):
        if requirements is None:
            requirements = [{"id": "sample.query", "skill": "ydb-sample", "weight": 1,
                             "cases": ["ydb-sample:example"]}]
        self.write_json(self.root / "evals/coverage.json", {"requirements": requirements})

    def test_discovers_packages_without_legacy_test_directories(self):
        self.assertFalse((self.root / "tests").exists())
        self.assertEqual(NATIVE.discover_skills(self.root), ("ydb-sample",))
        self.assertEqual(NATIVE.validate_repository(self.root), [])
        self.write_skill("ydb-new")
        (self.root / "skills/ydb-new/evals/scenarios.json").unlink()
        self.assertTrue(any("ydb-new" in e for e in NATIVE.validate_repository(self.root)))

    def test_validation_does_not_normalize_prompts_or_rubrics(self):
        document = scenario_suite()
        before = copy.deepcopy(document)
        self.assertEqual(NATIVE.validate_scenarios(document, "ydb-sample"), [])
        self.assertEqual(document, before)

    def test_rejects_boolean_and_duplicate_scenario_ids(self):
        document = scenario_suite()
        document["evals"][0]["id"] = True
        self.assertTrue(any("positive integer" in e for e in NATIVE.validate_scenarios(document, "ydb-sample")))
        document = scenario_suite()
        other = dict(document["evals"][0], name="different")
        document["evals"].append(other)
        self.assertTrue(any("duplicate id" in e for e in NATIVE.validate_scenarios(document, "ydb-sample")))

    def test_rejects_duplicate_scenario_names(self):
        document = scenario_suite()
        document["evals"].append(dict(document["evals"][0], id=2))
        self.assertTrue(any("duplicate name" in e for e in NATIVE.validate_scenarios(document, "ydb-sample")))

    def test_rejects_blank_content_and_non_string_expectations(self):
        for field, value in (("name", "  "), ("prompt", "\n"), ("expectations", []),
                             ("expectations", [False]), ("expected_output", ""), ("covers", " ")):
            with self.subTest(field=field, value=value):
                document = scenario_suite()
                document["evals"][0][field] = value
                self.assertTrue(any(field in e for e in NATIVE.validate_scenarios(document, "ydb-sample")))

    def test_rejects_native_unsupported_scoring_fields(self):
        document = scenario_suite()
        document["evals"][0]["threshold"] = 0.8
        self.assertTrue(any("threshold" in e for e in NATIVE.validate_scenarios(document, "ydb-sample")))
        document = scenario_suite()
        document["weights"] = [1]
        self.assertTrue(any("weights" in e for e in NATIVE.validate_scenarios(document, "ydb-sample")))

    def test_skill_name_must_match_package(self):
        self.assertTrue(any("skill_name" in e for e in NATIVE.validate_scenarios(scenario_suite(), "other")))
        self.assertTrue(any("skill_name" in e for e in NATIVE.validate_activations(activation_suite(), "other")))

    def test_activation_requires_boolean_values_not_truthy_strings(self):
        for value in ("false", 0, 1, None):
            with self.subTest(value=value):
                document = activation_suite()
                document["cases"][0]["should_activate"] = value
                self.assertTrue(any("must be a boolean" in e for e in NATIVE.validate_activations(document, "ydb-sample")))

    def test_activation_ids_and_balance_are_checked(self):
        document = activation_suite()
        document["cases"][1]["id"] = document["cases"][0]["id"]
        self.assertTrue(any("duplicate id" in e for e in NATIVE.validate_activations(document, "ydb-sample")))
        document = activation_suite()
        document["cases"].pop(0)
        self.assertTrue(any("found 4 positive" in e for e in NATIVE.validate_activations(document, "ydb-sample")))

    def test_bad_json_and_duplicate_object_keys_have_diagnostics(self):
        path = self.package / "evals/scenarios.json"
        for content, message in (("{", "Expecting"), ('{"evals": [], "evals": []}', "duplicate JSON field")):
            with self.subTest(content=content):
                path.write_text(content)
                errors = NATIVE.validate_repository(self.root)
                self.assertTrue(any(message in e and "scenarios.json" in e for e in errors))

    def test_legacy_case_copy_is_rejected(self):
        path = self.root / "tests/ydb-sample/example.yaml"
        path.parent.mkdir(parents=True)
        path.write_text("description: stale copy\n")
        self.assertTrue(any("duplicate legacy case source" in e for e in NATIVE.validate_repository(self.root)))

    def test_runtime_checks_must_reference_existing_cases_and_expectations(self):
        path = self.root / "tests/runtime/scenario-checks.json"
        self.write_json(path, {"ydb-sample:missing": {"checks": {}}})
        self.assertTrue(any("unknown canonical scenario" in e for e in NATIVE.validate_repository(self.root)))
        self.write_json(path, {"ydb-sample:example": {"checks": {"1": {"type": "contains", "value": "YDB"}}}})
        self.assertTrue(any("invalid expectation index" in e for e in NATIVE.validate_repository(self.root)))

    def test_runtime_contains_checks_cannot_drift_from_canonical_text(self):
        path = self.root / "tests/runtime/scenario-checks.json"
        metadata = {"ydb-sample:example": {"checks": {"0": {"type": "contains", "value": "YDB"}}}}
        self.write_json(path, metadata)
        self.assertEqual(NATIVE.validate_repository(self.root), [])
        metadata["ydb-sample:example"]["checks"]["0"]["value"] = "unrelated criterion"
        self.write_json(path, metadata)
        self.assertTrue(any("does not match expectation" in e for e in NATIVE.validate_repository(self.root)))

    def test_additional_runtime_checks_preserve_and_reference_whole_rubric(self):
        path = self.root / "tests/runtime/scenario-checks.json"
        check = {"expectation": 0, "type": "contains", "value": "YDB"}
        self.write_json(path, {"ydb-sample:example": {"additional_checks": [check]}})
        self.assertEqual(NATIVE.validate_repository(self.root), [])
        for index in (1, -1, True):
            with self.subTest(index=index):
                bad = dict(check, expectation=index)
                self.write_json(path, {"ydb-sample:example": {"additional_checks": [bad]}})
                self.assertTrue(any("invalid additional expectation index" in e
                                    for e in NATIVE.validate_repository(self.root)))
        self.write_json(path, {"ydb-sample:example": {
            "additional_checks": [dict(check, value="not in the rubric")],
        }})
        self.assertTrue(any("does not match expectation" in e
                            for e in NATIVE.validate_repository(self.root)))

    def test_coverage_reads_canonical_cases_without_tests_directory(self):
        self.write_coverage()
        result = COVERAGE.calculate_coverage(self.root)
        self.assertEqual(result["requirements"]["covered"], 1)
        self.assertEqual(result["suite"]["scenarios"], 1)
        self.assertEqual(result["errors"], [])

    def test_coverage_rule_ids_require_an_exact_expectation_reference(self):
        self.write_coverage()
        rules = self.package / "rules/example.md"
        rules.parent.mkdir()
        rules.write_text("### RULE-GO-01: Test rule\n")
        document = scenario_suite()
        document["evals"][0]["covers"] = "RULE-GO-01"
        document["evals"][0]["expectations"] = ["Cite RULE-GO-010."]
        self.write_json(self.package / "evals/scenarios.json", document)
        result = COVERAGE.calculate_coverage(self.root)
        self.assertEqual(result["rules"]["uncovered"], ["ydb-sample:RULE-GO-01"])

    def test_malformed_coverage_exits_cleanly(self):
        self.write_coverage()
        (self.root / "evals/coverage.json").write_text("not JSON")
        output = io.StringIO()
        with mock.patch.object(COVERAGE, "ROOT", self.root), \
             mock.patch.object(sys, "argv", ["eval-coverage.py", "--check"]), \
             contextlib.redirect_stderr(output):
            self.assertEqual(COVERAGE.main(), 1)
        self.assertIn("Coverage validation failed", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_malformed_requirement_does_not_count_as_covered(self):
        self.write_coverage([{"id": "bad", "skill": "ydb-sample", "weight": True,
                             "cases": ["ydb-sample:example"]}])
        result = COVERAGE.calculate_coverage(self.root)
        self.assertEqual(result["requirements"]["covered"], 0)
        self.assertTrue(result["errors"])

    def check_links(self, content):
        path = self.package / "SKILL.md"
        path.write_text(content)
        violations = []
        with mock.patch.object(SKILLS, "ROOT", self.root), \
             mock.patch.object(SKILLS, "SKILLS_DIR", self.root / "skills"):
            SKILLS.check_links(path, violations)
        return violations

    def test_package_links_cannot_escape_even_if_target_exists(self):
        self.write_skill("ydb-other")
        for target in ("../ydb-other/SKILL.md", "%2e%2e/ydb-other/SKILL.md"):
            with self.subTest(target=target):
                self.assertTrue(any("escapes the skill package" in e for e in self.check_links(f"[Other]({target})")))

    def test_package_links_cannot_escape_through_a_symlink(self):
        self.write_skill("ydb-other")
        (self.package / "linked.md").symlink_to(self.root / "skills/ydb-other/SKILL.md")
        self.assertTrue(any("escapes the skill package" in e for e in self.check_links("[Other](linked.md)")))

    def test_internal_links_and_external_urls_are_valid(self):
        (self.package / "reference.md").write_text("# Reference\n")
        self.assertEqual(self.check_links("[Local](reference.md#section) [Web](https://ydb.tech/docs/) [Here](#local)"), [])

    def test_description_limit_uses_decoded_characters(self):
        path = self.package / "SKILL.md"
        for length, should_fail in ((1024, False), (1025, True)):
            with self.subTest(length=length):
                path.write_text(f'---\nname: ydb-sample\ndescription: {json.dumps("я" * length)}\n---\n')
                violations = []
                with mock.patch.object(SKILLS, "ROOT", self.root):
                    SKILLS.check_skill_md(path, violations)
                self.assertEqual(any("exceeds 1024" in e for e in violations), should_fail)


if __name__ == "__main__":
    unittest.main()
