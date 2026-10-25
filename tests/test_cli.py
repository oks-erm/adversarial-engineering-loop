import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import challenge, final, position, rebuttal
from test_adversarial import assessment, attack, build, finding, response

PROJECT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        for args in [["init", "-q"], ["config", "user.name", "Test"],
                     ["config", "user.email", "test@example.invalid"],
                     ["commit", "--allow-empty", "-qm", "baseline"]]:
            subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)
        self.wrapper = self.root / "thurbox-cli"
        self.wrapper.write_text(f"#!{sys.executable}\nexec(compile(open({str(PROJECT / 'tests/fake_thurbox.py')!r}).read(), 'fake', 'exec'))\n")
        self.wrapper.chmod(0o755)

    def cli(self, workflow, replies, *extra):
        replies_path = self.root / "replies.json"
        replies_path.write_text(json.dumps(replies))
        result = subprocess.run([sys.executable, "-m", "thurbox_loop", workflow,
            "A real CLI test task", "--repo", str(self.repo), "--output", str(self.root / "output"),
            "--thurbox-cli", str(self.wrapper), "--agent-timeout", "2", *extra],
            cwd=PROJECT, capture_output=True, text=True,
            env=dict(os.environ, FAKE_THURBOX_ROOT=str(self.root), FAKE_REPLIES_PATH=str(replies_path)))
        return result

    def test_debate_cli_end_to_end(self):
        replies = [position(), position(), challenge("a-1"), challenge("b-1"),
                   rebuttal("b-1"), rebuttal("a-1"), final(), final()]
        result = self.cli("debate", replies, "--criterion", "Simplicity")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["outcome"], "CONSENSUS")
        self.assertTrue((self.root / "output/DEBATE_REPORT.md").exists())

    def test_adversarial_cli_repairs_and_retains_isolated_worktree(self):
        result = self.cli("adversarial", [build(), attack("CHANGES_REQUIRED", [finding()]),
            build([response()]), attack(assessments=[assessment()])],
            "--check", f'{sys.executable} -c "print(123)"')
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["outcome"], "PASS")
        self.assertEqual(value["rounds"], 2)
        self.assertNotEqual(Path(value["worktree"]["path"]), self.repo)
        self.assertTrue(Path(value["worktree"]["path"]).exists())
        self.assertEqual(subprocess.check_output(["git", "-C", str(self.repo), "status", "--porcelain"], text=True), "")

    def test_invalid_rounds_do_not_create_session(self):
        result = self.cli("adversarial", [], "--max-rounds", "0")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "calls.jsonl").exists())

    def test_malformed_agent_output_is_nonzero_with_report(self):
        result = self.cli("debate", [{}])
        self.assertEqual(result.returncode, 1)
        self.assertTrue((self.root / "output/DEBATE_REPORT.md").exists())

    def test_config_trusted_checks_and_invalid_types(self):
        from thurbox_loop.cli import load_config
        path = self.root / "config.toml"
        path.write_text('[adversarial.checks]\ncommands = ["python -m unittest"]\n')
        self.assertEqual(load_config(path), [["python", "-m", "unittest"]])
        path.write_text('[adversarial.checks]\ncommands = "oops"\n')
        with self.assertRaises(ValueError):
            load_config(path)

    def test_extension_payload_covers_all_runtime_files(self):
        manifest = tomllib.loads((PROJECT / "extension.toml").read_text())
        paths = {f["source"] if "source" in f else f["path"] for f in manifest["files"]}
        expected = {str(p.relative_to(PROJECT)) for p in (PROJECT / "thurbox_loop").glob("*.py")}
        self.assertTrue(expected <= paths, expected - paths)
        for item in manifest["files"]:
            self.assertTrue((PROJECT / item.get("source", item["path"])).is_file())

    def test_launcher_help(self):
        result = subprocess.run([str(PROJECT / "bin/thurbox-loop"), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("adversarial", result.stdout)

    def test_installed_payload_runs_without_source_checkout_imports(self):
        manifest = tomllib.loads((PROJECT / "extension.toml").read_text())
        home = self.root / "extension-home"
        for item in manifest["files"]:
            target = home / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT / item.get("source", item["path"]), target)
            if item.get("executable"):
                target.chmod(0o755)
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        result = subprocess.run([str(home / "bin/thurbox-loop"), "debate", "--help"],
                                cwd=self.root, capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--criterion", result.stdout)
