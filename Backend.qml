import QtQuick
import Quickshell.Io

Item {
    id: root
    property var devices: []
    property string selected: ""
    readonly property string notificationTitle: devices.length ? devices[0].title : "From Omarchy"
    readonly property string server: devices.length ? devices[0].server : "https://api.day.app"
    property bool busy: false
    property bool failed: false
    property string status: ""
    property string shortStatus: ""
    property string action: ""
    property string pending: ""
    signal sent()
    signal saved()
    signal pasted(string text)

    function run(data) {
        if (busy || worker.running) return
        busy = true
        failed = false
        status = data.action === "send" ? qsTr("Sending…")
            : data.action === "save" ? qsTr("Sending a test notification…") : ""
        shortStatus = data.action === "send" ? qsTr("Sending") : ""
        action = data.action
        pending = JSON.stringify(data)
        watchdog.restart()
        worker.running = true
    }
    function refresh() { run({action: "list"}) }
    Process {
        id: worker
        command: ["/usr/bin/timeout", "--kill-after=2", root.action === "clipboard" ? "5" : "170", "/usr/bin/python3", "-I",
                  decodeURIComponent(Qt.resolvedUrl("helpers/bark.py").toString().replace(/^file:\/\//, ""))]
        stdinEnabled: true
        onStarted: {
            write(root.pending)
            root.pending = ""
            stdinEnabled = false
        }
        stdout: StdioCollector { id: output }
        // Never show/log server response bodies or user-provided credentials.
        stderr: StdioCollector {}
        // FailedToStart emits runningChanged, but not exited in Quickshell.
        onRunningChanged: {
            if (!running && root.busy) Qt.callLater(function() {
                if (!worker.running && root.busy) {
                    watchdog.stop()
                    root.pending = ""
                    root.failed = true
                    root.status = qsTr("Cannot start the worker. Check the installation.")
                    root.shortStatus = qsTr("Failed")
                    root.busy = false
                }
            })
        }
        onExited: function(exitCode) {
            watchdog.stop()
            root.pending = ""
            stdinEnabled = true
            try {
                var result = JSON.parse(output.text)
                root.failed = !result.ok
                if (!result.ok) {
                    root.shortStatus = result.sent > 0 ? qsTr("Partial")
                        : String(result.message).indexOf("Cannot confirm delivery") >= 0 ? qsTr("Unconfirmed") : qsTr("Failed")
                    root.status = result.message || qsTr("Unable to complete the request.")
                    if (result.total !== undefined)
                        root.status += " " + qsTr("%1/%2 parts accepted. Check your device before retrying.").arg(result.sent).arg(result.total)
                    return
                }
                if (result.devices !== undefined) {
                    root.devices = result.devices
                    if (result.selected) root.selected = result.selected
                    if (!root.devices.some(function(d) { return d.id === root.selected }))
                        root.selected = root.devices.length ? root.devices[0].id : ""
                }
                if (root.action === "clipboard") {
                    root.status = ""
                    root.shortStatus = ""
                    root.pasted(result.text)
                } else if (root.action === "send") {
                    root.shortStatus = qsTr("Accepted")
                    root.status = qsTr("Accepted by Bark · %1 notification(s)").arg(result.sent)
                    root.sent()
                } else if (root.action === "save") {
                    root.shortStatus = qsTr("Saved")
                    root.status = qsTr("Test accepted by Bark. Device saved.")
                    root.saved()
                } else if (root.action === "remove") {
                    root.status = qsTr("Device removed")
                }
            } catch (e) {
                root.failed = true
                root.shortStatus = qsTr("Unconfirmed")
                root.status = qsTr("Worker stopped. Delivery is unconfirmed; check your device before retrying.")
            } finally {
                root.busy = false
            }
        }
    }
    Timer {
        id: watchdog
        interval: root.action === "clipboard" ? 8000 : 175000
        onTriggered: {
            worker.running = false
            root.pending = ""
            // Keep the operation locked until the process actually exits.
            // GNU timeout forwards TERM and escalates to KILL after 2 seconds.
            if (!worker.running) root.busy = false
            root.failed = true
            root.shortStatus = qsTr("Unconfirmed")
            root.status = qsTr("Request timed out. Check your device before retrying.")
        }
    }
}
