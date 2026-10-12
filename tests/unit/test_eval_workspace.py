import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("run_promptfoo", ROOT / "scripts/run-promptfoo.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class WorkspaceTests(unittest.TestCase):
    def test_answers_and_repository_instructions_are_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "workspace"
            RUNNER.prepare_workspace(ROOT, destination)
            installed = destination / ".agents/skills"
            expected = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
            self.assertEqual({p.name for p in installed.iterdir()}, expected)
            self.assertFalse(list(destination.rglob("scenarios.json")))
            self.assertFalse(list(destination.rglob("activations.json")))
            self.assertFalse((destination / "CLAUDE.md").exists())
            self.assertTrue((destination / ".git").is_dir())
            for name in expected:
                alias = destination / ".claude/skills" / name
                self.assertTrue((alias / "SKILL.md").is_file())
                self.assertTrue(alias.resolve().is_relative_to(destination.resolve()))

    def test_symlink_cannot_expose_files_outside_the_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            skill = root / "source/skills/example"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("example")
            (skill / "answers").symlink_to(ROOT / "tests")
            with self.assertRaisesRegex(ValueError, "symlinks"):
                RUNNER.prepare_workspace(root / "source", root / "workspace")


if __name__ == "__main__":
    unittest.main()
