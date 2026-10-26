import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from thurbox_loop.accounts_ui import install


class UiInstallTests(unittest.TestCase):
    def test_additive_idempotent_install_and_preserved_custom_pane(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'plugins').mkdir()
            layout = root / 'layout.lua'
            layout.write_text('untouched layout')
            calls = []
            def call(*args):
                calls.append(args)
                return {'dir': str(root)} if args == ('plugin', 'dir') else {'ok': True}
            with patch('thurbox_loop.accounts_ui.Thurbox') as adapter:
                adapter.return_value.call.side_effect = call
                first = install('/path/with space/thurbox-cli', root / 'dátá', '/path/claude')
                pane = Path(first['pane'])
                content = pane.read_text()
                self.assertNotIn('@BASE@', content)
                self.assertNotIn('@ARGS@', content)
                self.assertNotIn(r'\u00', content)
                self.assertIn('dátá', content)
                self.assertIn('capabilities = { "run", "program" }', content)
                self.assertEqual(layout.read_text(), 'untouched layout')
                self.assertFalse((root.parent / 'ui.json').exists())
                second = install('/path/with space/thurbox-cli', root / 'dátá', '/path/claude')
                self.assertIsNone(second['backup'])
                self.assertEqual(pane.read_text(), content)
                self.assertIn(('plugin', 'check'), calls)
                pane.write_text(content + '\n-- my custom pane')
                with self.assertRaisesRegex(ValueError, 'custom edits'):
                    install('thurbox-cli', root / 'dátá', 'claude')
                self.assertEqual(pane.read_text(), content + '\n-- my custom pane')
