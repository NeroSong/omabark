#!/usr/bin/python3
"""One-shot Bark worker. JSON on stdin/stdout; secrets never go in argv."""
import fcntl
from http.client import HTTPException
import json
import os
import re
import selectors
import signal
import socket
import ssl
import stat
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from urllib import error, parse, request

MAX_INPUT = 200000
MAX_TEXT = 32000
CHUNK_BYTES = 1800


class BarkError(Exception):
    pass


def read_clipboard():
    # Read only on an explicit paste action, outside the desktop event loop.
    # Bound both bytes and wall time even if the clipboard owner never closes.
    deadline = time.monotonic() + 3
    try:
        process = subprocess.Popen(["/usr/bin/wl-paste", "--no-newline", "--type", "text"],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        raise BarkError("Cannot read clipboard. Install wl-clipboard and use a Wayland session.") from None
    try:
        raw = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise BarkError("Clipboard timed out. Copy text and try again.")
                block = os.read(process.stdout.fileno(), MAX_TEXT + 1 - len(raw))
                if not block:
                    break
                raw.extend(block)
                if len(raw) > MAX_TEXT:
                    raise BarkError("Clipboard exceeds 32,000 UTF-8 bytes.")
        if process.wait(timeout=max(0.01, deadline - time.monotonic())) != 0:
            raise BarkError("Clipboard has no readable text.")
        text = raw.decode("utf-8")
        return string(text, "Clipboard text", MAX_TEXT)
    except subprocess.TimeoutExpired:
        raise BarkError("Clipboard timed out. Copy text and try again.") from None
    except UnicodeError:
        raise BarkError("Clipboard must contain valid UTF-8 text.") from None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def string(value, name, limit, required=True):
    if not isinstance(value, str) or len(value.encode("utf-8")) > limit:
        raise BarkError(f"{name} is invalid or too long.")
    if required and not value.strip():
        raise BarkError(f"Enter {name.lower()}.")
    return value


def endpoint(value):
    value = string(value, "Server URL", 2048).strip().rstrip("/")
    try:
        url = parse.urlsplit(value)
        port = url.port
    except ValueError:
        raise BarkError("Enter a valid HTTPS server URL.") from None
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or any(c.isspace() for c in value)
            or "\\" in value or (port is not None and port == 0)):
        raise BarkError("Use an HTTPS server URL without credentials, query or fragment.")
    return value


def registration(data):
    # Bark's copied test URL is /key/title/body; a custom base path is instead
    # configured explicitly with Server URL + Device key.
    copied = data.get("url", "").strip()
    if copied:
        url = parse.urlsplit(endpoint(copied))
        parts = url.path.strip("/").split("/")
        server = f"{url.scheme}://{url.netloc}"
        key = parts[0]
    else:
        server = endpoint(data.get("server", "https://api.day.app"))
        key = data.get("key", "").strip()
    if data.get("serverMode") == "default" and server != "https://api.day.app":
        raise BarkError("This URL uses another server. Select Custom server to add it.")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", key):
        raise BarkError("Enter a valid Bark device key or copied test URL.")
    return server, key


def private_fd(name, flags, dir_fd):
    fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=dir_fd)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        os.close(fd)
        raise BarkError("Device storage must be an owner-only regular file (0600).")
    return fd


@contextmanager
def storage():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    if not os.path.isabs(base):
        raise BarkError("XDG_CONFIG_HOME must be an absolute path.")
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, "omabark")
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(directory)
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise BarkError("Device storage directory must have owner-only permissions (0700).")
        lock = private_fd(".lock", os.O_RDWR | os.O_CREAT, directory)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield directory
        finally:
            os.close(lock)
    finally:
        os.close(directory)


def read_devices(directory):
    try:
        fd = private_fd("devices.json", os.O_RDONLY, directory)
    except FileNotFoundError:
        return []
    with os.fdopen(fd, "rb") as file:
        raw = file.read(32769)
    if len(raw) > 32768:
        raise BarkError("Device storage is too large.")
    try:
        saved = json.loads(raw)
        devices = saved["devices"]
        if saved["version"] != 1 or not isinstance(devices, list) or len(devices) > 20:
            raise ValueError
        ids = set()
        for device in devices:
            string(device["name"], "Device name", 80)
            string(device.get("title", "From Omarchy"), "Title", 120, required=False)
            if not re.fullmatch(r"[0-9a-f]{32}", device["id"]) or device["id"] in ids:
                raise ValueError
            ids.add(device["id"])
            registration(device)
        return devices
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        raise BarkError("Device storage is invalid. Restore it from a private backup.") from None


def save_devices(directory, devices):
    name = ".devices-" + uuid.uuid4().hex
    fd = private_fd(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump({"version": 1, "devices": devices}, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, "devices.json", src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(name, dir_fd=directory)
        except FileNotFoundError:
            pass


def public(devices):
    # Older files may contain multiple devices. Use only the first without
    # rewriting private data merely by opening the panel.
    return [{"id": d["id"], "server": d["server"],
             "title": d.get("title", "").strip() or "From Omarchy"} for d in devices[:1]]


def chunks(text):
    parts, current, size = [], [], 0
    for char in text:
        # Count JSON escapes too: control characters must not exceed APNs'
        # payload budget even when their raw UTF-8 representation is small.
        width = len(json.dumps(char, ensure_ascii=False)[1:-1].encode("utf-8"))
        if size + width > CHUNK_BYTES:
            parts.append("".join(current))
            current, size = [], 0
        current.append(char)
        size += width
    if current:
        parts.append("".join(current))
    return parts


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(server, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(server + "/push", data=body, headers={
        "Content-Type": "application/json; charset=utf-8", "User-Agent": "omabark/0.3.0"
    }, method="POST")
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=8) as response:
            raw = response.read(16385)
            if len(raw) > 16384:
                raise BarkError("Bark returned an oversized response.")
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get("code") != 200:
                raise BarkError("Bark rejected the notification. Check the device key.")
    except error.HTTPError as exc:
        code = exc.code
        exc.close()
        raise BarkError(f"Bark returned HTTP {code}. Check the server and device key.") from None
    except (error.URLError, TimeoutError, socket.timeout, ssl.SSLError, OSError, HTTPException):
        raise BarkError("Cannot confirm delivery. Check your connection before sending again.") from None
    except (ValueError, UnicodeError, RecursionError):
        raise BarkError("Bark returned an invalid response.") from None


def test_and_save(data):
    title = string(data.get("title", ""), "Title", 120, required=False).strip() or "From Omarchy"
    with storage() as directory:
        original = read_devices(directory)
    if data.get("reuseExisting") is True:
        if not original:
            raise BarkError("Enter your Bark URL or device key.")
        server = endpoint(data.get("server", "https://api.day.app"))
        if server != original[0]["server"]:
            raise BarkError("Enter a device key for the new server.")
        key = original[0]["key"]
    else:
        server, key = registration(data)
    # A successful test is required on every save path. Do not persist keys
    # or hold the storage lock while waiting for the chosen server.
    post(server, {"device_key": key, "title": title,
                  "body": "Test notification from OmaBark.",
                  "group": "OmaBark", "level": "active"})
    with storage() as directory:
        devices = read_devices(directory)
        if devices != original:
            raise BarkError("Configuration changed during the test. Please test again.")
        device = {"id": original[0]["id"] if original else uuid.uuid4().hex,
                  "name": "Apple device", "title": title, "server": server, "key": key}
        save_devices(directory, [device])
    return {"ok": True, "devices": public([device]), "selected": device["id"]}


def dispatch(data):
    if not isinstance(data, dict):
        raise BarkError("Expected a JSON object.")
    action = data.get("action")
    if action not in ("list", "save", "remove", "send", "clipboard"):
        raise BarkError("Unknown action.")
    if action == "save":
        return test_and_save(data)
    if action == "clipboard":
        text = read_clipboard()
        with storage() as directory:
            return {"ok": True, "text": text, "devices": public(read_devices(directory))}
    with storage() as directory:
        devices = read_devices(directory)
        if action == "list":
            return {"ok": True, "devices": public(devices)}
        device = devices[0] if devices else None
        if device and data.get("id") not in (None, device["id"]):
            device = None
        if device is None:
            raise BarkError("Configure your Apple device first.")
        if action == "remove":
            devices.remove(device)
            save_devices(directory, devices)
            return {"ok": True, "devices": public(devices)}
        body = string(data.get("body"), "Message", MAX_TEXT)
        title = device.get("title", "").strip() or "From Omarchy"
        parts = chunks(body)
    # Release storage lock before network I/O. No automatic retry: a timeout
    # can happen after APNs accepted a notification.
    sent = 0
    deadline = time.monotonic() + 120
    for index, part in enumerate(parts):
        heading = title if len(parts) == 1 else f"{title or 'Bark'} ({index + 1}/{len(parts)})"
        try:
            if time.monotonic() >= deadline:
                raise BarkError("Time limit reached; remaining parts were not sent.")
            post(device["server"], {"device_key": device["key"], "body": part,
                 "title": heading, "group": "OmaBark", "level": "active"})
        except BarkError as exc:
            return {"ok": False, "message": str(exc), "sent": sent, "total": len(parts)}
        sent += 1
    return {"ok": True, "sent": sent, "total": len(parts)}


def main():
    def expired(signum, frame):
        raise BarkError("Worker timed out; delivery is unconfirmed. Check your device before retrying.")
    # Independent of the GUI/CLI supervisor, including if it is destroyed.
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(165)
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise BarkError("Input is too large.")
        result = dispatch(json.loads(raw))
    except BarkError as exc:
        result = {"ok": False, "message": str(exc)}
    except (ValueError, UnicodeError, TypeError, AttributeError, RecursionError):
        result = {"ok": False, "message": "Invalid input."}
    except OSError:
        result = {"ok": False, "message": "Cannot access private device storage. Check permissions."}
    finally:
        signal.alarm(0)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
