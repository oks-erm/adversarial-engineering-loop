import subprocess
import sys
import unittest
from pathlib import Path
import tomllib

class SplitTests(unittest.TestCase):
    def test_workflow_cli_no_longer_exposes_account_switching(self):
        result = subprocess.run([sys.executable, '-m', 'thurbox_loop', '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('accounts', result.stdout)
        self.assertIn('adversarial', result.stdout)
        self.assertIn('debate', result.stdout)

    def test_manifest_delivers_only_workflow_runtime(self):
        root = Path(__file__).resolve().parents[1]
        manifest = tomllib.loads((root / 'extension.toml').read_text())
        self.assertFalse(any('accounts' in item['path'].lower() for item in manifest['files']))
