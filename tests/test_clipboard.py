"""Exercise bounded clipboard reads using disposable local processes, no clipboard access."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("bark_clipboard", Path(__file__).resolve().parents[1] / "helpers/bark.py")
bark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bark)


class ClipboardTests(unittest.TestCase):
    def read(self, program):
        popen = subprocess.Popen
        processes = []
        def launch(command, **kwargs):
            self.assertEqual(command, ["/usr/bin/wl-paste", "--no-newline", "--type", "text"])
            process = popen(["/usr/bin/python3", "-I", "-c", program], **kwargs)
            processes.append(process)
            return process
        try:
            with patch.object(bark.subprocess, "Popen", side_effect=launch):
                return bark.read_clipboard()
        finally:
            self.assertTrue(all(p.poll() is not None for p in processes))

    def test_preserves_unicode_and_newlines(self):
        self.assertEqual(self.read('import sys; sys.stdout.buffer.write("Hello 👋\\n".encode())'), "Hello 👋\n")

    def test_empty_invalid_and_oversized_clipboards(self):
        for program in ('pass', 'print(" ")', 'import sys; sys.stdout.buffer.write(b"\\xff")',
                        'print("x"*32001)', 'raise SystemExit(1)'):
            with self.subTest(program=program), self.assertRaises(bark.BarkError):
                self.read(program)

    def test_hung_clipboard_is_killed(self):
        with self.assertRaisesRegex(bark.BarkError, "timed out"):
            self.read('import time; time.sleep(20)')

    def test_clipboard_action_never_sends(self):
        with tempfile.TemporaryDirectory() as config, patch.dict(os.environ, XDG_CONFIG_HOME=config):
            with patch.object(bark, "read_clipboard", return_value="Draft"), patch.object(bark, "post") as post:
                result = bark.dispatch({"action": "clipboard"})
            self.assertEqual(result, {"ok": True, "text": "Draft", "devices": []})
            post.assert_not_called()

    def test_missing_clipboard_program_is_redacted(self):
        with patch.object(bark.subprocess, "Popen", side_effect=FileNotFoundError("private path")):
            with self.assertRaisesRegex(bark.BarkError, "Install wl-clipboard") as caught:
                bark.read_clipboard()
        self.assertNotIn("private path", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
