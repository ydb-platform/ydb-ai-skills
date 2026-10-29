"""Reject unsupported exports before any historical grader requests are made."""

import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("grader_agreement", ROOT / "scripts/grader-agreement.py")
GRADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRADER)


class HistoricalGraderTests(unittest.TestCase):
    def export(self):
        return {
            "config": {"defaultTest": {"options": {"rubricPrompt": GRADER.RUBRIC_PROMPT_TEMPLATE.format(
                user_prompt="{{ user_prompt }}", output="{{ output }}", rubric="{{ rubric }}",
            )}}},
            "results": {"results": [{
                "provider": {"id": "historical-solver"},
                "testCase": {"description": "Old case", "assert": [{"type": "llm-rubric", "value": "Historical rubric"}]},
                "response": {"output": "Historical response"},
                "gradingResult": {"componentResults": [{"assertion": {"type": "llm-rubric"}, "pass": True}]},
            }]},
        }

    def test_accepts_one_historical_rubric(self):
        self.assertEqual(len(GRADER.cell_records(self.export())), 1)

    def test_rejects_new_prompt_or_unknown_prompt(self):
        for prompt in ("Binary verdict required", None):
            export = self.export()
            export["config"]["defaultTest"]["options"]["rubricPrompt"] = prompt
            with self.assertRaisesRegex(ValueError, "Historical-only"):
                GRADER.cell_records(export)

    def test_rejects_multiple_thresholded_transformed_or_canonical_criteria(self):
        for change in ("multiple", "threshold", "transform", "metadata"):
            with self.subTest(change=change):
                export = self.export()
                case = export["results"]["results"][0]["testCase"]
                if change == "multiple":
                    case["assert"].append(copy.deepcopy(case["assert"][0]))
                elif change == "metadata":
                    case["metadata"] = {"caseId": 123}
                else:
                    case["assert"][0][change] = 1 if change == "threshold" else "file://trace.cjs"
                with self.assertRaisesRegex(ValueError, "Historical-only"):
                    GRADER.cell_records(export)
