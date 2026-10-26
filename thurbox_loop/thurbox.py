"""Public Thurbox CLI adapter; result artifacts, never latched status, finish turns."""

from __future__ import annotations

import json
import math
import re
import stat
import sys
import tempfile
import time
import uuid
from pathlib import Path

from .adversarial import git
from .core import atomic_write, dumps, validate
from .runtime import execute


def strict_json(text: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"invalid JSON constant: {value}")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


class Thurbox:
    def __init__(self, command: list[str] | None = None, *, timeout: float = 30,
                 journal: Path | None = None):
        self.command = command or ["thurbox-cli"]
        self.timeout, self.journal = timeout, journal
        self.events: list[dict] = []

    def call(self, *args: str, timeout: float | None = None) -> dict:
        result = execute([*self.command, *args, "--json"], Path.cwd(), timeout=timeout or self.timeout,
                         limit=2_000_000)
        if result["status"] == "TIMEOUT":
            raise TimeoutError(f"Thurbox {' '.join(args[:2])} exceeded its deadline")
        if result["status"] != "PASS" or result["truncated"]:
            detail = result["stderr"]
            try:
                failure = strict_json(result["stdout"])
                if isinstance(failure, dict) and isinstance(failure.get("error"), str):
                    detail = failure["error"]
            except ValueError:
                pass
            raise RuntimeError(f"Thurbox {' '.join(args[:2])} failed ({result['status']}): "
                               f"{detail[:1000] or 'no diagnostic returned'}")
        value = strict_json(result["stdout"])
        if not isinstance(value, dict) or value.get("ok") is False:
            raise ValueError("Thurbox returned invalid or unsuccessful JSON")
        return value

    def record(self, event: dict) -> None:
        self.events.append(event)
        if self.journal:
            atomic_write(self.journal, dumps(self.events) + "\n")

    def create_session(self, cwd: Path, *, agent: str | None = None, extra: list[str] | None = None) -> dict:
        args = ["session", "create", "--name", "loop-" + uuid.uuid4().hex[:16], "--repo-path", str(cwd)]
        if agent is not None:
            args += ["--agent", agent]
        result = self.call(*args, *(extra or []))
        if not isinstance(result.get("id"), str) or not result["id"]:
            raise ValueError("Thurbox create returned no session id")
        self.record(dict(event="created", id=result["id"], agent=agent, cwd=result.get("cwd")))
        return result

    def stop(self, identifier: str) -> None:
        self.call("session", "stop", identifier)
        self.record(dict(event="stopped", id=identifier))

    def create_worktree(self, repo: Path, run_id: str, *, base: str = "HEAD") -> dict:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,47}", run_id):
            raise ValueError("invalid run id")
        branch = "adversarial/" + run_id
        # A harmless holder lets Thurbox own worktree creation and retention.
        session = self.create_session(repo, extra=["--command", sys.executable, "--arg", "-c",
            "--arg", "import time; time.sleep(604800)", "--worktree-branch", branch, "--base-branch", base])
        try:
            path = Path(session.get("cwd", "")).resolve()
            if path == repo.resolve() or not path.is_dir() or not session.get("worktrees"):
                raise ValueError("Thurbox did not create an isolated worktree")
            if git(path, "branch", "--show-current").strip() != branch:
                raise ValueError("isolated worktree has an unexpected branch")
            common = lambda p: Path(git(p, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()).resolve()
            if common(path) != common(repo):
                raise ValueError("isolated worktree belongs to another repository")
            return dict(branch=branch, path=str(path), holder_session=session["id"],
                        baseline_commit=git(path, "rev-parse", "HEAD").strip())
        finally:
            self.stop(session["id"])


class ThurboxAgent:
    def __init__(self, name: str, thurbox: Thurbox, *, timeout: float = 600, poll_interval: float = 0.25):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("agent timeout must be positive and finite")
        self.name, self.thurbox, self.timeout = name, thurbox, timeout
        self.poll_interval = poll_interval

    def run(self, *, prompt: str, cwd: Path, mode: str, schema: dict) -> dict:
        with tempfile.TemporaryDirectory(prefix="thurbox-loop-") as directory:
            root = Path(directory)
            nonce = uuid.uuid4().hex
            result_path = root / "result.json"
            prompt_path = root / "prompt.md"
            contract = dict(result_path=str(result_path), nonce=nonce, mode=mode, schema=schema)
            instructions = ("\nRead the contract above and perform the task below. Write ONLY the result artifact "
                "outside the repository. Project access mode is " + mode + ". For read_only, do not edit "
                "project files; tests may use temporary outputs. Do not send human-facing messages. "
                "When ALL work is finished, atomically write a UTF-8 JSON object with exactly two fields: "
                "nonce (the exact nonce above) and result (matching the schema above). Write to a temporary "
                "file in the same directory, then rename to result_path. No Markdown fences. Do not write "
                "the result until work and checks finish; make no further project changes afterwards. "
                "If permissions prevent this, report blocked in the pane instead of bypassing permissions.\n\n")
            atomic_write(prompt_path, dumps(contract).replace("\n", " ") + instructions + prompt)
            session = self.thurbox.create_session(cwd, agent=self.name)
            identifier = session["id"]
            error = None
            try:
                deadline = time.monotonic() + self.timeout
                sent = self.thurbox.call("session", "send", identifier,
                    json.dumps(str(prompt_path)) + "\nRead this task file and follow its result contract.",
                    timeout=min(self.thurbox.timeout, self.timeout))
                if sent.get("submitted") is False:
                    raise RuntimeError("Thurbox did not submit the prompt")
                while time.monotonic() < deadline:
                    if result_path.exists() or result_path.is_symlink():
                        info = result_path.lstat()
                        if not stat.S_ISREG(info.st_mode) or info.st_size > 2_000_000:
                            raise ValueError("agent result must be a regular JSON file under 2 MB")
                        envelope = strict_json(result_path.read_text(encoding="utf-8"))
                        if not isinstance(envelope, dict) or set(envelope) != {"nonce", "result"} or envelope["nonce"] != nonce:
                            raise ValueError("agent result has invalid envelope or stale nonce")
                        validate(envelope["result"], schema)
                        return envelope["result"]
                    status = self.thurbox.call("session", "get", identifier,
                        timeout=max(0.01, min(self.thurbox.timeout, deadline - time.monotonic())))
                    if status.get("state") in {"lost", "stopped", "deleted"} or status.get("stopped"):
                        raise RuntimeError(f"agent session {identifier} exited without a result")
                    time.sleep(min(self.poll_interval, max(0, deadline - time.monotonic())))
                raise TimeoutError(f"agent {self.name} did not produce a result within {self.timeout}s; session {identifier}")
            except BaseException as caught:
                error = caught
                raise
            finally:
                try:
                    self.thurbox.stop(identifier)
                except Exception as stop_error:
                    raise RuntimeError(f"Unable to stop session {identifier}; manual intervention required. "
                                       f"Turn error: {error}. Stop error: {stop_error}") from stop_error
