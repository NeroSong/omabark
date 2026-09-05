import QtQuick
import Quickshell
import Quickshell.Io
import "./plugin" as Bark
ShellRoot {
    property int stage: 0
    property string clipboardText: ""
    Bark.BarWidget { id: widget }
    Bark.Backend { id: backend }
    Process {
        id: ipc
        command: ["/usr/bin/qs", "ipc", "-n", "-p",
                  decodeURIComponent(Qt.resolvedUrl(".").toString().replace(/^file:\/\//, "")),
                  "call", "--", "nerosong.omabark", "paste"]
        onExited: function(code) {
            if (code !== 0) { console.error("IPC_FAILED"); Qt.quit() }
            else console.log("IPC_PASSED")
        }
    }
    Connections {
        target: backend
        function onPasted(text) { clipboardText = text }
        function onBusyChanged() {
            if (backend.busy) return
            if (backend.failed) { console.error("TEST_FAILED", backend.status); Qt.quit(); return }
            if (stage === 0) {
                stage = 1
                Qt.callLater(function() { backend.run({action:"save",title:"Saved title",key:"test_key",server:"https://example.invalid"}) })
            } else if (stage === 1) {
                if (backend.notificationTitle !== "Saved title") { console.error("TITLE_FAILED"); Qt.quit(); return }
                stage = 2
                Qt.callLater(function() { backend.refresh() })
            } else if (stage === 2) {
                if (backend.devices.length !== 1) { console.error("TEST_FAILED devices"); Qt.quit(); return }
                stage = 25
                Qt.callLater(function() { backend.run({action:"clipboard"}) })
            } else if (stage === 25) {
                if (clipboardText !== "Clipboard fixture") { console.error("CLIPBOARD_FAILED"); Qt.quit(); return }
                stage = 3
                Qt.callLater(function() { backend.run({action:"send",body:"Smoke test"}) })
            } else if (stage === 3) {
                if (backend.shortStatus !== "Accepted") { console.error("STATUS_FAILED"); Qt.quit(); return }
                stage = 4
                Qt.callLater(function() { backend.run({action:"remove",id:backend.selected}) })
            } else {
                console.log("BACKEND_SMOKE_PASSED")
                lifecycle.start()
            }
        }
    }
    Timer {
        id: lifecycle
        property int step: 0
        interval: 350; repeat: true
        onTriggered: {
            if (step === 0) widget.open()
            else if (step === 2) ipc.running = true
            else if (step === 1 || step === 3) {
                if (!widget.opened) { console.error("LIFECYCLE_FAILED open"); Qt.quit(); return }
                widget.close()
            } else {
                if (widget.opened) console.error("LIFECYCLE_FAILED close")
                else console.log("LIFECYCLE_PASSED")
                Qt.quit()
            }
            step++
        }
    }
    Timer { interval: 300; running: true; onTriggered: backend.refresh() }
    Timer { interval: 7000; running: true; onTriggered: { console.error("TEST_TIMED_OUT"); Qt.quit() } }
}
