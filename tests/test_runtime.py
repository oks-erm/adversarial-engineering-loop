import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


class RuntimeTests(unittest.TestCase):
    def test_checks_use_literal_arguments_and_preserve_exit_evidence(self):
        from thurbox_loop.runtime import run_checks
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = run_checks([[sys.executable, "-c", "import sys; print(sys.argv[1]); sys.exit(3)",
                                   "$(touch SHOULD_NOT_EXIST); echo nope"]], root)
            self.assertEqual(results[0]["status"], "FAIL")
            self.assertEqual(results[0]["exit_code"], 3)
            self.assertIn("$(touch", results[0]["stdout"])
            self.assertFalse((root / "SHOULD_NOT_EXIST").exists())

    def test_timeout_is_bounded_and_reported(self):
        from thurbox_loop.runtime import run_checks
        start = time.monotonic()
        results = run_checks([[sys.executable, "-c", "import time; time.sleep(10)"]], Path.cwd(), timeout=0.1)
        self.assertEqual(results[0]["status"], "TIMEOUT")
        self.assertLess(time.monotonic() - start, 3)

    def test_missing_program_is_check_failure(self):
        from thurbox_loop.runtime import run_checks
        self.assertEqual(run_checks([["thurbox-loop-program-does-not-exist"]], Path.cwd())[0]["status"], "ERROR")

    def test_oversized_output_is_bounded(self):
        from thurbox_loop.runtime import execute
        result = execute([sys.executable, "-c", "print('X' * 100000)"], Path.cwd(), timeout=2, limit=1024)
        self.assertTrue(result["truncated"])
        self.assertLess(len(result["stdout"]), 1200)

    def test_redaction_in_json_keeps_valid_json(self):
        from thurbox_loop.core import Store
        import json
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"TEST_API_KEY": 'secret"with\\quotes'}):
            store = Store(Path(directory) / "run", "test", {})
            store.json("value.json", {"message": os.environ["TEST_API_KEY"]})
            self.assertEqual(json.loads((store.root / "value.json").read_text())["message"], "[REDACTED]")
            self.assertEqual((store.root / "value.json").stat().st_mode & 0o777, 0o600)

    def test_invalid_check_config_rejected(self):
        from thurbox_loop.runtime import normalize_commands
        for commands in ["pytest", [[]], [["pytest", 5]], [""], [[""]]]:
            with self.subTest(commands=commands), self.assertRaises(ValueError):
                normalize_commands(commands)

    def test_shell_split_config_supports_quotes(self):
        from thurbox_loop.runtime import normalize_commands
        self.assertEqual(normalize_commands(['python -c "print(1)"']), [["python", "-c", "print(1)"]])
