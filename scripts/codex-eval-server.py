#!/usr/bin/env python3
"""Isolate Codex eval tool discovery at both process and thread boundaries.

Promptfoo 0.125.1 sends cli_config again on thread/start. Startup-only
overrides do not survive that boundary. This stdio proxy reapplies the same
discovered exclusions there; it never reads or copies login credentials.
"""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import queue
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time


ISOLATION = {
    "features.apps": False,
    "features.plugins": False,
    "features.remote_plugin": False,
    "features.skill_mcp_dependency_install": False,
    "features.memories": False,
    "features.hooks": False,
    "features.multi_agent": False,
    "features.skill_search": False,
    "features.tool_suggest": False,
    "skills.bundled.enabled": False,
    # Global user AGENTS.md is not covered by this limit; report it in preflight.
    "project_doc_max_bytes": 0,
    "developer_instructions": "",
}
WORKSPACE_INSTRUCTION = (
    "Use only the current workspace and its installed skills for local task material. "
    "Do not read host skills, other checkouts, home configuration, logs, credentials, "
    "or evaluation/grading files. Do not search parent directories. "
    "Use remote sources only when the task and configured network access allow it."
)


def toml_literal(value):
    """Unlike Promptfoo 0.125.1, serialize objects inside arrays as TOML."""
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k) + "=" + toml_literal(v) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(toml_literal(v) for v in value) + "]"
    return json.dumps(value)


def cli_args(config):
    return [arg for key, value in config.items() for arg in ("-c", key + "=" + toml_literal(value))]


def flatten(config, prefix=""):
    result = {}
    for key, value in config.items():
        name = prefix + key
        if isinstance(value, dict):
            result.update(flatten(value, name + "."))
        else:
            result[name] = value
    return result


def isolate_request(message, config, workspaces):
    """Preserve request IDs and task settings; replace only isolation settings."""
    if message.get("method") not in {"thread/start", "thread/resume", "thread/fork"}:
        return message
    params = dict(message.get("params") or {})
    cwd = str(Path(params.get("cwd", os.getcwd())).resolve())
    if cwd not in workspaces:
        raise ValueError("Codex eval thread must use a prepared solver or judge workspace")
    params["config"] = {**flatten(params.get("config") or {}), **config}
    instructions = params.get("developerInstructions") or ""
    params["developerInstructions"] = WORKSPACE_INSTRUCTION + "\n\n" + instructions
    return {**message, "params": params}


class Server:
    """Small sequential JSON-RPC client for no-model discovery and preflight."""

    def __init__(self, command, cwd):
        self.process = subprocess.Popen(
            [*command, "app-server", "--listen", "stdio://"], cwd=cwd,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
        )
        self.messages = queue.Queue()
        self.counter = 0
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.rpc("initialize", {"clientInfo": {"name": "ydb-eval-preflight", "version": "1"},
                                    "capabilities": {"experimentalApi": True}})
            self._send({"method": "initialized", "params": {}})
        except Exception:
            self.close()
            raise

    def _read(self):
        for line in self.process.stdout:
            try:
                self.messages.put(json.loads(line))
            except json.JSONDecodeError:
                continue
        self.messages.put(None)

    def _send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def rpc(self, method, params):
        self.counter += 1
        self._send({"id": self.counter, "method": method, "params": params})
        deadline = time.monotonic() + 30
        while True:
            try:
                response = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty as error:
                raise RuntimeError(f"Codex preflight timed out: {method}") from error
            if response is None:
                raise RuntimeError(f"Codex app-server closed during {method}")
            if response.get("id") != self.counter:
                continue
            if "error" in response:
                # Do not print arbitrary config/error payloads containing host settings.
                raise RuntimeError(f"Codex preflight RPC failed: {method}")
            return response["result"]

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        for pipe in (self.process.stdin, self.process.stdout):
            pipe.close()


def list_skills(server, cwd):
    response = server.rpc("skills/list", {"cwds": [str(cwd)], "forceReload": True})
    if any(row.get("errors") for row in response["data"]):
        raise RuntimeError("Codex skill discovery returned errors")
    return [skill for row in response["data"] for skill in row["skills"]]


def codex_command(root):
    local = root / "node_modules/@openai/codex/bin/codex.js"
    node = shutil.which("node")
    if node and local.is_file():
        return [node, str(local)]
    command = shutil.which("codex")
    if not command:
        raise ValueError("Codex CLI not found; run npm install or put codex on PATH")
    return [command]


def prepare(root, solver, judge, artifacts, model, effort):
    command = codex_command(root)
    # Disable plugins before listing MCP: a plugin name is not a standalone
    # transport and adding mcp_servers.<plugin>.enabled creates invalid config.
    listed = subprocess.run(
        [*command, *cli_args(ISOLATION), "mcp", "list", "--json"], cwd=solver,
        check=True, capture_output=True, text=True, timeout=30,
    )
    names = sorted(entry["name"] for entry in json.loads(listed.stdout))
    # Codex 0.161.0 splits override paths on dots without unquoting segments.
    # Fail closed for ambiguous names rather than accidentally enabling a server.
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in names):
        raise ValueError("MCP names containing dots/quotes cannot be isolated by this Codex CLI version")
    config = {**ISOLATION, **{f"mcp_servers.{name}.enabled": False for name in names}}
    server = Server([*command, *cli_args(config)], solver)
    try:
        effective = server.rpc("config/read", {"includeLayers": False})["config"]
        if effective.get("model_instructions_file"):
            raise ValueError("Custom model_instructions_file is incompatible with isolated evals")
        skills = list_skills(server, solver) + list_skills(server, judge)
    finally:
        server.close()
    allowed = {str(p.resolve()) for p in (solver / ".agents/skills").glob("*/SKILL.md")}
    disabled = sorted({str(Path(s["path"]).resolve()) for s in skills
                       if str(Path(s["path"]).resolve()) not in allowed})
    config["skills.config"] = [{"path": path, "enabled": False} for path in disabled]
    manifest = artifacts / "isolation.json"
    manifest.write_text(json.dumps({"command": command, "config": config,
                                   "workspaces": [str(solver.resolve()), str(judge.resolve())]}, indent=2) + "\n")
    manifest.chmod(0o600)
    wrapper = artifacts / "codex-eval-server"
    helper = Path(__file__).resolve()
    wrapper.write_text("#!/bin/sh\nexec " + " ".join(map(shlex.quote,
                       [sys.executable, str(helper), "--serve", str(manifest)])) + ' "$@"\n')
    wrapper.chmod(0o700)
    preflight(wrapper, solver, judge, allowed, artifacts, model, effort)
    return wrapper


def preflight(wrapper, solver, judge, allowed, artifacts, model, effort):
    report = {"no_model_turn_requested": True, "threads": [], "passed": False,
              "limitation": "Global user AGENTS.md remains inherited; workspace-only developer instructions apply. This is not OS-level filesystem isolation."}
    server = Server([str(wrapper)], solver)
    try:
        effective = flatten(server.rpc("config/read", {"includeLayers": False})["config"])
        if any(effective.get(key) != value for key, value in ISOLATION.items()):
            raise RuntimeError("Codex did not apply all required isolation settings")
        for role, cwd in (("solver", solver), ("judge", judge)):
            # Deliberately send the same partial config that used to undo startup
            # isolation. The wrapper must enforce isolation on the actual thread.
            start = server.rpc("thread/start", {
                "model": model, "cwd": str(cwd), "approvalPolicy": "on-request",
                "sandbox": "read-only", "config": {"web_search": "disabled",
                    "model_reasoning_effort": effort, "features": {"apps": False}},
                "ephemeral": True, "serviceName": "promptfoo",
            })
            thread_id = start["thread"]["id"]
            status = server.rpc("mcpServerStatus/list", {
                "threadId": thread_id, "limit": 100, "detail": "toolsAndAuthOnly",
            })
            servers = status.get("data", [])
            while status.get("nextCursor"):
                status = server.rpc("mcpServerStatus/list", {
                    "threadId": thread_id, "limit": 100, "detail": "toolsAndAuthOnly",
                    "cursor": status["nextCursor"],
                })
                servers.extend(status.get("data", []))
            enabled = {str(Path(s["path"]).resolve()) for s in list_skills(server, cwd) if s["enabled"]}
            if "instructionSources" not in start:
                raise RuntimeError("Codex did not report instruction sources; isolation cannot be verified")
            global_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
            permitted_sources = {(global_home / filename).resolve() for filename in ("AGENTS.md", "AGENTS.override.md")}
            sources = []
            for source in start["instructionSources"] or []:
                path = Path(source).resolve()
                if path not in permitted_sources:
                    raise RuntimeError(f"Codex {role} inherited unexpected instruction files")
                data = path.read_bytes()
                sources.append({"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            info = {"role": role, "model": start.get("model"),
                    "reasoning_effort": start.get("reasoningEffort"),
                    "mcp_tools_count": sum(len(s.get("tools", {})) for s in servers),
                    "enabled_skills": sorted(enabled),
                    "instruction_sources": sources}
            report["threads"].append(info)
            if info["mcp_tools_count"] or enabled != (allowed if role == "solver" else set()):
                raise RuntimeError(f"Codex {role} inherited unexpected tools or skills")
            if info["model"] != model or info["reasoning_effort"] != effort:
                raise RuntimeError(f"Codex {role} did not accept the requested model/effort")
            server.rpc("thread/unsubscribe", {"threadId": thread_id})
        report["passed"] = True
    finally:
        server.close()
        (artifacts / "preflight.json").write_text(json.dumps(report, indent=2) + "\n")


def serve(manifest_path, args):
    manifest = json.loads(Path(manifest_path).read_text())
    config = manifest["config"]
    # Generated TOML is appended last and takes precedence over CLI overrides.
    process = subprocess.Popen([*manifest["command"], *args, *cli_args(config)], stdin=subprocess.PIPE)

    def forward():
        try:
            for line in sys.stdin:
                message = isolate_request(json.loads(line), config, manifest["workspaces"])
                process.stdin.write((json.dumps(message) + "\n").encode())
                process.stdin.flush()
        except (ValueError, BrokenPipeError, OSError):
            print("Codex eval proxy rejected a request or lost its connection", file=sys.stderr)
            process.terminate()
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass

    threading.Thread(target=forward, daemon=True).start()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda signum, frame: process.send_signal(signum))
    return process.wait()


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "--serve":
        sys.exit("Use scripts/run-promptfoo.py to prepare this Codex eval proxy")
    sys.exit(serve(sys.argv[2], sys.argv[3:]))
