import importlib.util
import tempfile
import unittest
from pathlib import Path


class SmokeTests(unittest.TestCase):
    def test_both_workflows_with_real_failing_then_passing_checks(self):
        path = Path(__file__).resolve().parents[1] / "examples/smoke.py"
        spec = importlib.util.spec_from_file_location("smoke_example", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            result = module.smoke(Path(directory) / "run")
            self.assertEqual(result["debate"], "CONSENSUS")
            self.assertEqual(result["adversarial"], "PASS")
            self.assertEqual(result["attacks"], 2)
            self.assertTrue(Path(result["worktree"]).is_dir())
            log = Path(result["reports"][1]).with_name("ADVERSARIAL_LOG.md").read_text()
            self.assertIn("TypeError", log)
            self.assertIn("SATISFIED", log)
