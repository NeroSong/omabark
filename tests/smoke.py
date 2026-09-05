#!/usr/bin/python3
"""Load real QML components in a disposable Wayland test harness. No push I/O."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

project = Path(__file__).resolve().parents[1]
shell = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")) / "shell"
if not os.environ.get("WAYLAND_DISPLAY"):
    raise SystemExit("Run this smoke test inside an active Wayland session.")
with tempfile.TemporaryDirectory(prefix="omabark-smoke-") as temporary:
    root = Path(temporary)
    for folder in ("Commons", "Ui"):
        (root / folder).symlink_to(shell / folder)
    plugin = root / "plugin"
    plugin.mkdir()
    for source in project.glob("*.qml"):
        shutil.copy2(source, plugin / source.name)
    shutil.copytree(project / "helpers", plugin / "helpers", ignore=shutil.ignore_patterns("__pycache__"))
    # Stub only this disposable worker's HTTP transport; never ship a test
    # bypass in the installed helper or send a real notification during QA.
    helper = plugin / "helpers/bark.py"
    helper.write_text(helper.read_text().replace('if __name__ == "__main__":',
        'def post(server, payload):\n    return None\n\ndef read_clipboard():\n    return "Clipboard fixture"\n\nif __name__ == "__main__":'))
    shutil.copy2(project / "tests/smoke.qml", root / "shell.qml")
    env = dict(os.environ, XDG_CONFIG_HOME=str(root / "config"),
               QT_QPA_PLATFORM="wayland", QT_QUICK_BACKEND="software", QT_QPA_PLATFORMTHEME="basic")
    result = subprocess.run(["quickshell", "-p", str(root), "--no-color"],
                            env=env, capture_output=True, text=True, timeout=12)
    output = result.stdout + result.stderr
    print(output, end="")
    if (result.returncode or "BACKEND_SMOKE_PASSED" not in output
            or "IPC_PASSED" not in output
            or "LIFECYCLE_PASSED" not in output or "FAILED" in output
            or "ERROR" in output or "unavailable" in output):
        raise SystemExit(1)
