import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/codex-eval-server.py"
SPEC = importlib.util.spec_from_file_location("codex_eval_server", HELPER)
ISOLATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ISOLATION)


class CodexIsolationTests(unittest.TestCase):
    def test_thread_overrides_cannot_restore_nested_inherited_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            flags = {**ISOLATION.ISOLATION, "mcp_servers.example.enabled": False,
                     "skills.config": [{"path": "/example/SKILL.md", "enabled": False}]}
            request = {"id": 12, "method": "thread/start", "params": {
                "cwd": workspace, "model": "chosen-model", "developerInstructions": "Task instruction",
                "config": {"features": {"plugins": True, "apps": True},
                           "mcp_servers": {"example": {"enabled": True}},
                           "web_search": "disabled", "model_reasoning_effort": "medium"}}}
            actual = ISOLATION.isolate_request(request, flags, [workspace])
            self.assertEqual(actual["id"], 12)
            config = actual["params"]["config"]
            self.assertIs(config["features.plugins"], False)
            self.assertIs(config["mcp_servers.example.enabled"], False)
            self.assertEqual(config["skills.config"], flags["skills.config"])
            self.assertNotIn("features", config)
            self.assertEqual(actual["params"]["model"], "chosen-model")
            self.assertIn("Task instruction", actual["params"]["developerInstructions"])
            self.assertIn("Do not read host skills", actual["params"]["developerInstructions"])
            self.assertTrue(request["params"]["config"]["features"]["plugins"], "do not mutate caller config")

    def test_foreign_workspaces_are_rejected_and_other_messages_are_unchanged(self):
        request = {"id": 1, "method": "thread/start", "params": {"cwd": "/unexpected"}}
        with self.assertRaisesRegex(ValueError, "prepared"):
            ISOLATION.isolate_request(request, {}, ["/expected"])
        notification = {"method": "initialized", "params": {}}
        self.assertIs(ISOLATION.isolate_request(notification, {}, []), notification)

    def test_skill_array_is_valid_toml_instead_of_json_objects(self):
        config = {"skills.config": [{"path": '/tmp/a "quote"/SKILL.md', "enabled": False}]}
        value = ISOLATION.cli_args(config)[1]
        self.assertEqual(value, 'skills.config=[{"path"="/tmp/a \\"quote\\"/SKILL.md","enabled"=false}]')

    def test_stdio_proxy_forwards_thread_config_and_closes_child_without_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve()
            fake = folder / "fake_cli.py"
            fake.write_text("import json,sys\nfor line in sys.stdin:\n print(json.dumps(json.loads(line)),flush=True)\n")
            flags = {**ISOLATION.ISOLATION, "skills.config": [{"path": "/host/SKILL.md", "enabled": False}]}
            manifest = folder / "manifest.json"
            manifest.write_text(json.dumps({"command": [sys.executable, str(fake)],
                                            "config": flags, "workspaces": [str(folder)]}))
            request = {"id": 7, "method": "thread/start", "params": {"cwd": str(folder),
                       "config": {"features": {"apps": False}, "web_search": "disabled"}}}
            result = subprocess.run([sys.executable, str(HELPER), "--serve", str(manifest),
                                     "app-server", "--listen", "stdio://"],
                                    input=json.dumps(request) + "\n", text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            actual = json.loads(result.stdout)
            self.assertEqual(actual["params"]["config"]["skills.config"], flags["skills.config"])
            self.assertIs(actual["params"]["config"]["features.plugins"], False)

    def test_preflight_fails_when_instruction_sources_are_missing(self):
        class FakeServer:
            def __init__(self, *args): pass
            def close(self): pass
            def rpc(self, method, params):
                if method == "config/read": return {"config": ISOLATION.ISOLATION}
                if method == "thread/start": return {"thread": {"id": "no-model"}, "model": "model", "reasoningEffort": "medium"}
                if method == "mcpServerStatus/list": return {"data": []}
                if method == "skills/list": return {"data": [{"skills": []}]}
                raise AssertionError(f"Unexpected RPC: {method}")
        with tempfile.TemporaryDirectory() as tmp, patch.object(ISOLATION, "Server", FakeServer):
            folder = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "instruction sources"):
                ISOLATION.preflight(folder / "wrapper", folder, folder, set(), folder, "model", "medium")
            self.assertFalse(json.loads((folder / "preflight.json").read_text())["passed"])


if __name__ == "__main__":
    unittest.main()
