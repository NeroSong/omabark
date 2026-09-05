"""Execute the real CLI with a disposable helper whose HTTP transport is stubbed."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

PROJECT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plugin = self.root / "plugin with spaces"
        (self.plugin / "helpers").mkdir(parents=True)
        shutil.copy2(PROJECT / "omabark", self.plugin / "omabark")
        helper = (PROJECT / "helpers/bark.py").read_text()
        stub = '''def post(server, payload):
    import pathlib
    with open(os.environ["CAPTURE"], "a") as capture:
        capture.write(json.dumps({"server": server, "payload": payload}) + "\\n")
    if os.environ.get("FAIL") == "1":
        raise BarkError("Simulated rejection")
    if os.environ.get("FAIL") == "partial" and "(2/" in payload["title"]:
        raise BarkError("Simulated rejection")

'''
        (self.plugin / "helpers/bark.py").write_text(helper.replace('if __name__ == "__main__":', stub + 'if __name__ == "__main__":'))
        self.env = dict(os.environ, XDG_CONFIG_HOME=str(self.root / "config"), CAPTURE=str(self.root / "requests"))
        config = self.root / "config/omabark"
        config.mkdir(parents=True, mode=0o700)
        self.config = config / "devices.json"
        self.config.write_text(json.dumps({"version": 1, "devices": [{
            "id": "a" * 32, "name": "Apple device", "title": "From my laptop",
            "server": "https://example.invalid", "key": "private_test_key"}]}))
        self.config.chmod(0o600)

    def run_cli(self, *args, data=b"", **env):
        return subprocess.run([str(self.plugin / "omabark"), *args], input=data,
                              capture_output=True, env=dict(self.env, **env), timeout=5)

    def requests(self):
        return [json.loads(line) for line in (self.root / "requests").read_text().splitlines()]

    def test_argument_text_and_saved_title(self):
        text = '中文 👋\n"quotes" & $(touch /tmp/not-executed)'
        result = self.run_cli("send", text)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = self.requests()[0]["payload"]
        self.assertEqual(payload["body"], text)
        self.assertEqual(payload["title"], "From my laptop")
        self.assertNotIn(b"private_test_key", result.stdout + result.stderr)

    def test_stdin_preserves_trailing_newline(self):
        raw = "你好\nsecond line\n".encode()
        for args in (("send",), ("send", "-")):
            result = self.run_cli(*args, data=raw)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all(r["payload"]["body"].encode() == raw for r in self.requests()))

    def test_dash_prefixed_message(self):
        result = self.run_cli("send", "--", "--literal")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.requests()[0]["payload"]["body"], "--literal")

    def test_json_success(self):
        result = self.run_cli("send", "--json", "hello")
        self.assertEqual(json.loads(result.stdout), {"ok": True, "sent": 1, "total": 1})
        self.assertEqual(result.stderr, b"")

    def test_empty_invalid_utf8_and_oversize(self):
        for raw in (b"", b" \n", b"\xff", b"x" * 32001):
            result = self.run_cli("send", data=raw)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
        self.assertFalse((self.root / "requests").exists())

    def test_missing_configuration(self):
        self.config.unlink()
        result = self.run_cli("send", "hello")
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"Configure your Apple device", result.stderr)
        self.assertFalse((self.root / "requests").exists())

    def test_failure_and_partial_result(self):
        result = self.run_cli("send", "hello", FAIL="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"0/1 parts accepted", result.stderr)
        result = self.run_cli("send", "--json", "x" * 2000, FAIL="partial")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["sent"], 1)

    def test_symlink_launcher(self):
        link = self.root / "omabark"
        link.symlink_to(self.plugin / "omabark")
        result = subprocess.run([str(link), "send", "hello"], capture_output=True, env=self.env, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_does_not_send(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"send", result.stdout)
        self.assertFalse((self.root / "requests").exists())

    def test_usage_exit_code(self):
        result = self.run_cli("unknown")
        self.assertEqual(result.returncode, 2)

    def test_interrupt_stops_worker_before_later_send(self):
        helper = self.plugin / "helpers/bark.py"
        helper.write_text('''import os, pathlib, sys, time
sys.stdin.read()
root = pathlib.Path(os.environ["CAPTURE"])
root.with_suffix(".ready").touch()
time.sleep(1)
root.touch()
''')
        process = subprocess.Popen([str(self.plugin / "omabark"), "send", "hello"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=self.env, start_new_session=True)
        try:
            deadline = time.monotonic() + 3
            while not (self.root / "requests.ready").exists():
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.01)
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 130, stderr)
            self.assertEqual(stdout, b"")
            time.sleep(1.1)
            self.assertFalse((self.root / "requests").exists(), "Worker continued after interruption")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    unittest.main()
