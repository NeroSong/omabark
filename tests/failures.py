#!/usr/bin/python3
"""Fault-inject a disposable QML backend. Never contacts Bark or the clipboard."""
import os
from pathlib import Path
import subprocess
import tempfile

project = Path(__file__).resolve().parents[1]
cases = ("timeout", "watchdog", "invalid-json", "start-failure")
for case in cases:
    with tempfile.TemporaryDirectory(prefix="omabark-fault-") as temporary:
        root = Path(temporary)
        (root / "helpers").mkdir()
        source = (project / "Backend.qml").read_text().replace('"--kill-after=2"', '"--kill-after=0.2"')
        source = source.replace('"170"', '"0.4"' if case == "timeout" else '"30"')
        source = source.replace('175000', '300' if case == "watchdog" else '2500')
        if case == "start-failure":
            source = source.replace('/usr/bin/timeout', str(root / 'missing-executable'))
        (root / "Backend.qml").write_text(source)
        (root / "helpers/bark.py").write_text('''import pathlib, signal, sys, time
sys.stdin.read()
marker = pathlib.Path(__file__).with_suffix(".ran")
if marker.exists():
    print('{"ok":true,"sent":1,"total":1}')
else:
    marker.touch()
''' + ('    print("malformed response")\n' if case == "invalid-json" else
       '    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n    time.sleep(10)\n'))
        (root / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
 property int beats: 0
 property int stage: 0
 Backend { id: backend }
 Timer { interval: 10; running: true; repeat: true; onTriggered: beats++ }
 Timer { interval: 20; running: true; onTriggered: backend.run({action:"send",body:"fixture"}) }
 Connections {
  target: backend
  function onBusyChanged() {
   if (backend.busy) return
   if (stage === 0) {
    if (!backend.failed) { console.error("FAULT_FAILED expected failure"); Qt.quit(); return }
    if (REQUIRE_HEARTBEAT && beats < 10) { console.error("FAULT_FAILED heartbeat"); Qt.quit(); return }
    stage = 1
    if (START_FAILURE) { console.log("FAULT_PASSED"); Qt.quit(); return }
    Qt.callLater(function() { backend.run({action:"send",body:"retry fixture"}) })
   } else {
    if (backend.failed || backend.shortStatus !== "Accepted") console.error("FAULT_FAILED recovery")
    else console.log("FAULT_PASSED")
    Qt.quit()
   }
  }
 }
 Timer { interval: 5000; running: true; onTriggered: { console.error("FAULT_FAILED deadline"); Qt.quit() } }
}
'''.replace('REQUIRE_HEARTBEAT', str(case in ("timeout", "watchdog")).lower())
            .replace('START_FAILURE', str(case == "start-failure").lower()))
        result = subprocess.run(["quickshell", "-p", str(root), "--no-color"],
            env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_QPA_PLATFORMTHEME="basic"),
            capture_output=True, text=True, timeout=8)
        output = result.stdout + result.stderr
        if result.returncode or "FAULT_PASSED" not in output or "FAULT_FAILED" in output:
            raise SystemExit(f"{case}: {output}")
        print(f"{case}: passed (failure handled; " + ("startup released" if case == "start-failure" else "next request recovered") + ")")
