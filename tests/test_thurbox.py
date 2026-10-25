import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ThurboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {"FAKE_THURBOX_ROOT": str(self.root)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        from thurbox_loop.thurbox import Thurbox
        self.tb = Thurbox([sys.executable, str(Path(__file__).with_name("fake_thurbox.py"))], timeout=2)

    def agent(self):
        from thurbox_loop.thurbox import ThurboxAgent
        return ThurboxAgent("custom-agent", self.tb, timeout=0.4, poll_interval=0.02)

    def run_agent(self):
        from thurbox_loop.core import TEXT, obj
        return self.agent().run(prompt="Inspect code read-only", cwd=self.root, mode="read_only", schema=obj(answer=TEXT))

    def calls(self):
        return [json.loads(line) for line in (self.root / "calls.jsonl").read_text().splitlines()]

    def test_fresh_registered_session_structured_result_and_stop(self):
        self.assertEqual(self.run_agent(), {"answer": "ok"})
        calls = self.calls()
        self.assertEqual(calls[0][:2], ["session", "create"])
        self.assertIn("custom-agent", calls[0])
        self.assertEqual(calls[-1][:2], ["session", "stop"])
        self.assertEqual(len(self.tb.events), 2)

    def test_malformed_wrong_nonce_schema_and_crash_fail_and_stop(self):
        for mode in ["malformed", "nonce", "schema", "crash"]:
            with self.subTest(mode=mode), patch.dict(os.environ, {"FAKE_RESULT_MODE": mode}):
                with self.assertRaises((ValueError, RuntimeError)):
                    self.run_agent()
                self.assertEqual(self.calls()[-1][:2], ["session", "stop"])

    def test_latched_state_does_not_count_as_completion(self):
        with patch.dict(os.environ, {"FAKE_RESULT_MODE": "no-result"}):
            with self.assertRaises(TimeoutError):
                self.run_agent()
        self.assertEqual(self.calls()[-1][:2], ["session", "stop"])

    def test_stop_failure_prevents_next_workflow_turn(self):
        with patch.dict(os.environ, {"FAKE_STOP_FAIL": "1"}):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                self.run_agent()

    def init_repo(self):
        repo = self.root / "repo"
        repo.mkdir()
        for args in [["init", "-q"], ["config", "user.name", "Test"],
                     ["config", "user.email", "test@example.invalid"],
                     ["commit", "--allow-empty", "-qm", "baseline"]]:
            subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
        return repo

    def test_worktree_is_isolated_and_retained(self):
        repo = self.init_repo()
        worktree = self.tb.create_worktree(repo, "safe-test")
        path = Path(worktree["path"])
        self.assertNotEqual(path.resolve(), repo.resolve())
        self.assertEqual(worktree["branch"], "adversarial/safe-test")
        self.assertTrue(path.exists())
        self.assertEqual(self.calls()[-1][:2], ["session", "stop"])

    def test_worktree_cannot_fall_back_to_caller_checkout(self):
        repo = self.init_repo()
        with patch.dict(os.environ, {"FAKE_BAD_WORKTREE": "1"}):
            with self.assertRaisesRegex(ValueError, "isolated"):
                self.tb.create_worktree(repo, "bad-test")

    def test_invalid_run_id_rejected_before_subprocess(self):
        with self.assertRaises(ValueError):
            self.tb.create_worktree(self.root, "../../main")
        self.assertFalse((self.root / "calls.jsonl").exists())
