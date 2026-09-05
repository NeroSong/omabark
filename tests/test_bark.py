import importlib.util
from http.client import IncompleteRead
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

HELPER = Path(__file__).resolve().parents[1] / "helpers" / "bark.py"
spec = importlib.util.spec_from_file_location("bark", HELPER)
bark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bark)


class BarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp.name})
        env.start()
        self.addCleanup(env.stop)

    def device(self):
        with patch.object(bark, "post"):
            return bark.dispatch({"action": "save", "name": "My iPhone", "key": "secret_key",
                                  "server": "https://example.invalid"})["selected"]

    def test_save_tests_before_persisting(self):
        def accept(server, payload):
            self.assertEqual(bark.dispatch({"action": "list"})["devices"], [])
            self.assertEqual(payload["body"], "Test notification from OmaBark.")
            self.assertEqual(payload["device_key"], "test_key")
        with patch.object(bark, "post", side_effect=accept) as post:
            result = bark.dispatch({"action": "save", "name": "Test", "key": "test_key"})
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["devices"]), 1)
        post.assert_called_once()

    def test_failed_test_does_not_save_or_change_devices(self):
        self.device()
        config = Path(self.temp.name) / "omabark/devices.json"
        before = config.read_bytes()
        with patch.object(bark, "post", side_effect=bark.BarkError("Test rejected")):
            with self.assertRaises(bark.BarkError):
                bark.dispatch({"action": "save", "name": "Other", "key": "other_key"})
        self.assertEqual(config.read_bytes(), before)

    def test_failed_first_test_does_not_create_devices_file(self):
        with patch.object(bark, "post", side_effect=bark.BarkError("Offline")):
            with self.assertRaises(bark.BarkError):
                bark.dispatch({"action": "save", "name": "Test", "key": "test_key"})
        self.assertFalse((Path(self.temp.name) / "omabark/devices.json").exists())

    def test_private_storage_and_redaction(self):
        selected = self.device()
        root = Path(self.temp.name) / "omabark"
        self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((root / "devices.json").stat().st_mode), 0o600)
        result = bark.dispatch({"action": "list"})
        self.assertNotIn("secret_key", json.dumps(result))
        self.assertEqual(result["devices"][0]["id"], selected)

    def test_copied_url(self):
        self.assertEqual(bark.registration({"url": "https://api.day.app/ABC_123/test/body"}),
                         ("https://api.day.app", "ABC_123"))

    def test_custom_base_path(self):
        self.assertEqual(bark.registration({"server": "https://example.invalid/bark/", "key": "key"}),
                         ("https://example.invalid/bark", "key"))

    def test_default_server_selection_matches_destination(self):
        self.assertEqual(bark.registration({"serverMode": "default", "url": "https://api.day.app/key/test"}),
                         ("https://api.day.app", "key"))
        with self.assertRaises(bark.BarkError):
            bark.registration({"serverMode": "default", "url": "https://example.invalid/key/test"})

    def test_single_device_replaces_previous_after_success(self):
        first = self.device()
        with patch.object(bark, "post"):
            result = bark.dispatch({"action": "save", "title": "Laptop", "key": "new_key"})
        self.assertEqual(len(result["devices"]), 1)
        self.assertEqual(result["selected"], first)
        self.assertEqual(result["devices"][0]["title"], "Laptop")
        with bark.storage() as directory:
            self.assertEqual(bark.read_devices(directory)[0]["key"], "new_key")

    def test_title_default_and_saved_title_used_for_send(self):
        first = self.device()
        with patch.object(bark, "post") as post:
            bark.dispatch({"action": "send", "id": first, "title": "ignored", "body": "hello"})
        self.assertEqual(post.call_args.args[1]["title"], "From Omarchy")
        with patch.object(bark, "post"):
            bark.dispatch({"action": "save", "title": "My laptop", "reuseExisting": True,
                           "server": "https://example.invalid"})
        with patch.object(bark, "post") as post:
            bark.dispatch({"action": "send", "body": "hello"})
        self.assertEqual(post.call_args.args[1]["title"], "My laptop")

    def test_reuse_key_cannot_change_server(self):
        self.device()
        with patch.object(bark, "post") as post:
            with self.assertRaises(bark.BarkError):
                bark.dispatch({"action": "save", "reuseExisting": True, "server": "https://other.invalid"})
        post.assert_not_called()

    def test_legacy_multiple_devices_exposes_only_first(self):
        self.device()
        with bark.storage() as directory:
            devices = bark.read_devices(directory)
            other = dict(devices[0], id="b" * 32, key="second_key")
            devices.append(other)
            bark.save_devices(directory, devices)
        result = bark.dispatch({"action": "list"})
        self.assertEqual(len(result["devices"]), 1)
        with bark.storage() as directory:
            self.assertEqual(len(bark.read_devices(directory)), 2)

    def test_bad_servers(self):
        for url in ("http://example.org", "https://user:pass@example.org", "https://example.org?x=1",
                    "https://example.org/#fragment", "https://", "https://host:bad", "https://host\n"):
            with self.subTest(url=url):
                # Trailing whitespace is intentionally trimmed.
                if url.endswith("\n"):
                    continue
                with self.assertRaises(bark.BarkError):
                    bark.endpoint(url)

    def test_bad_key(self):
        with self.assertRaises(bark.BarkError):
            bark.registration({"key": "$(touch /tmp/no); /"})

    def test_symlink_file_rejected(self):
        self.device()
        target = Path(self.temp.name) / "outside"
        target.write_text("do not modify")
        config = Path(self.temp.name) / "omabark/devices.json"
        config.unlink()
        config.symlink_to(target)
        with self.assertRaises(OSError):
            bark.dispatch({"action": "list"})
        self.assertEqual(target.read_text(), "do not modify")

    def test_symlink_directory_rejected(self):
        (Path(self.temp.name) / "omabark").symlink_to(self.temp.name)
        with self.assertRaises(OSError):
            bark.dispatch({"action": "list"})

    def test_world_readable_file_rejected(self):
        self.device()
        (Path(self.temp.name) / "omabark/devices.json").chmod(0o644)
        with self.assertRaises(bark.BarkError):
            bark.dispatch({"action": "list"})

    def test_shared_directory_rejected(self):
        self.device()
        (Path(self.temp.name) / "omabark").chmod(0o755)
        with self.assertRaises(bark.BarkError):
            bark.dispatch({"action": "list"})

    def test_lock_symlink_rejected(self):
        self.device()
        target = Path(self.temp.name) / "outside"
        target.write_text("unchanged")
        lock = Path(self.temp.name) / "omabark/.lock"
        lock.unlink()
        lock.symlink_to(target)
        with self.assertRaises(OSError):
            bark.dispatch({"action": "list"})
        self.assertEqual(target.read_text(), "unchanged")

    def test_fifo_storage_rejected_without_blocking(self):
        self.device()
        config = Path(self.temp.name) / "omabark/devices.json"
        config.unlink()
        os.mkfifo(config, 0o600)
        result = subprocess.run(["/usr/bin/python3", "-I", str(HELPER)],
            input=b'{"action":"list"}', capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertEqual(result.stderr, b"")

    def test_concurrent_change_during_test_is_not_overwritten(self):
        self.device()
        def change_configuration(*args):
            with bark.storage() as directory:
                devices = bark.read_devices(directory)
                devices[0]["title"] = "Changed elsewhere"
                bark.save_devices(directory, devices)
        with patch.object(bark, "post", side_effect=change_configuration):
            with self.assertRaisesRegex(bark.BarkError, "Configuration changed"):
                bark.dispatch({"action": "save", "title": "Stale", "key": "new_key"})
        self.assertEqual(bark.dispatch({"action": "list"})["devices"][0]["title"], "Changed elsewhere")

    def test_corrupt_storage_not_overwritten(self):
        self.device()
        config = Path(self.temp.name) / "omabark/devices.json"
        config.write_text("bad json")
        with self.assertRaises(bark.BarkError):
            self.device()
        self.assertEqual(config.read_text(), "bad json")

    def test_remove_and_stale_id(self):
        selected = self.device()
        self.assertEqual(bark.dispatch({"action": "remove", "id": selected})["devices"], [])
        with self.assertRaises(bark.BarkError):
            bark.dispatch({"action": "send", "id": selected, "body": "x"})

    def test_unicode_split_is_lossless(self):
        message = '你好 👩🏽‍💻\n"quotes" \\ $(touch /tmp/no) & / ?\n' * 300
        pieces = bark.chunks(message)
        self.assertEqual("".join(pieces), message)
        self.assertTrue(all(len(p.encode()) <= bark.CHUNK_BYTES for p in pieces))

    def test_partial_failure_is_not_retried(self):
        selected = self.device()
        with patch.object(bark, "post", side_effect=[None, bark.BarkError("offline")]) as post:
            result = bark.dispatch({"action": "send", "id": selected, "body": "x" * 4000})
        self.assertEqual(post.call_count, 2)
        self.assertFalse(result["ok"])
        self.assertEqual((result["sent"], result["total"]), (1, 3))

    def test_request_preserves_text_and_keeps_key_out_of_url(self):
        payload = {"body": '你好\n" & / $(whoami)', "device_key": "secret_key"}
        with patch.object(bark.request, "build_opener") as factory:
            factory.return_value.open.return_value = io.BytesIO(b'{"code":200}')
            bark.post("https://example.invalid", payload)
            req = factory.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, "https://example.invalid/push")
            self.assertEqual(json.loads(req.data), payload)
            self.assertEqual(req.method, "POST")
            self.assertIsInstance(factory.call_args.args[0], bark.NoRedirect)

    def test_network_and_server_errors_are_redacted(self):
        for exception in (URLError("secret_key"), HTTPError("secret_key", 302, "secret_key", {}, None)):
            with patch.object(bark.request, "build_opener") as factory:
                factory.return_value.open.side_effect = exception
                with self.assertRaises(bark.BarkError) as caught:
                    bark.post("https://example.invalid", {})
                self.assertNotIn("secret_key", str(caught.exception))

    def test_api_rejection_and_invalid_response(self):
        for response in (b'{"code":400,"message":"secret_key"}', b'[]', b'bad', b'x' * 16385):
            with patch.object(bark.request, "build_opener") as factory:
                factory.return_value.open.return_value = io.BytesIO(response)
                with self.assertRaises(bark.BarkError) as caught:
                    bark.post("https://example.invalid", {})
                self.assertNotIn("secret_key", str(caught.exception))

    def test_input_limits(self):
        selected = self.device()
        for body in ("", " \n", "你" * 11000):
            with self.assertRaises(bark.BarkError):
                bark.dispatch({"action": "send", "id": selected, "body": body})

    def test_worker_stdin_protocol(self):
        result = subprocess.run(["/usr/bin/python3", "-I", str(HELPER)],
            input=b'{"action":"list"}', capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"ok": True, "devices": []})
        self.assertEqual(result.stderr, b"")

    def test_worker_alarm_bounds_blocked_stdin(self):
        helper = Path(self.temp.name) / "alarm_fixture.py"
        helper.write_text(HELPER.read_text().replace("signal.alarm(165)", "signal.alarm(1)"))
        with subprocess.Popen(["/usr/bin/python3", "-I", str(helper)], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                raise
            stdout, stderr = process.communicate()
        self.assertEqual(process.returncode, 1)
        self.assertIn("Worker timed out", json.loads(stdout)["message"])
        self.assertEqual(stderr, b"")

    def test_no_redirect(self):
        self.assertIsNone(bark.NoRedirect().redirect_request(None, None, 307, "", {}, "https://evil.invalid"))

    def test_broken_http_preserves_partial_result_without_leaking_body(self):
        self.device()
        with patch.object(bark.request.OpenerDirector, "open", side_effect=IncompleteRead(b"secret_response")):
            result = bark.dispatch({"action": "send", "body": "hello"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["total"], 1)
        self.assertNotIn("secret_response", json.dumps(result))
        self.assertIn("Cannot confirm delivery", result["message"])

    def test_deeply_nested_input_returns_safe_json(self):
        result = subprocess.run(["/usr/bin/python3", "-I", str(HELPER)],
            input=b"[" * 2000 + b"0" + b"]" * 2000, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertIn(json.loads(result.stdout)["message"], ("Invalid input.", "Expected a JSON object."))
        self.assertEqual(result.stderr, b"")

    def test_deeply_nested_storage_is_preserved(self):
        self.device()
        config = Path(self.temp.name) / "omabark/devices.json"
        raw = "[" * 2000 + "0" + "]" * 2000
        config.write_text(raw)
        with self.assertRaises(bark.BarkError):
            bark.dispatch({"action": "list"})
        self.assertEqual(config.read_text(), raw)

    def test_deeply_nested_response_is_rejected(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"[" * 2000 + b"0" + b"]" * 2000
        with patch.object(bark.request.OpenerDirector, "open", return_value=response):
            with self.assertRaises(bark.BarkError):
                bark.post("https://example.invalid", {"body": "hello"})

    def test_json_escapes_fit_payload_budget(self):
        text = "\x00\t\n\\\"" * 1000
        parts = bark.chunks(text)
        self.assertEqual("".join(parts), text)
        for part in parts:
            self.assertLessEqual(len(json.dumps(part, ensure_ascii=False)[1:-1].encode()), 1800)

    def test_total_send_deadline_reports_partial_count(self):
        selected = self.device()
        with patch.object(bark.time, "monotonic", side_effect=[0, 1, 121]), patch.object(bark, "post") as post:
            result = bark.dispatch({"action": "send", "id": selected, "body": "x" * 2000})
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result["sent"], 1)
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
