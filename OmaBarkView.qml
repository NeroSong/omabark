import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Commons
import qs.Commons as Commons
import qs.Ui as Ui

ColumnLayout {
    id: root
    required property var backend
    readonly property color secondaryTextColor: Qt.tint(Commons.Color.popups.background,
        Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.75))
    property bool configuring: false
    property bool advanced: false
    readonly property bool setup: configuring || backend.devices.length === 0
    readonly property int messageBytes: unescape(encodeURIComponent(message.text)).length
    readonly property bool canSend: !setup && !backend.busy && backend.selected !== ""
        && message.text.trim().length > 0 && messageBytes <= 32000

    signal closeRequested()
    spacing: Style.space(14)

    function focusEditor() { if (setup) notificationTitleField.forceActiveFocus(); else message.forceActiveFocus() }
    function replaceDraft(text) {
        configuring = false
        clearSecrets()
        message.text = text
    }
    function send() {
        if (canSend) backend.run({action: "send", id: backend.selected, body: message.text})
    }
    readonly property string chosenServer: advanced ? server.text.replace(/\/+$/, "") : "https://api.day.app"
    readonly property bool reuseExisting: backend.devices.length > 0 && chosenServer === backend.server
        && (advanced ? deviceKey.text.trim() === "" : deviceUrl.text.trim() === "")
    function openSettings() {
        notificationTitleField.text = backend.notificationTitle === "From Omarchy" ? "" : backend.notificationTitle
        advanced = backend.server !== "https://api.day.app"
        server.text = backend.server
        clearSecrets()
        configuring = true
        backend.status = ""
    }
    function goBack() {
        clearSecrets()
        if (backend.devices.length) configuring = false
        else closeRequested()
    }
    function clearSecrets() { deviceUrl.text = ""; deviceKey.text = "" }
    Keys.onEscapePressed: {
        if (setup) goBack()
        else closeRequested()
    }
    Keys.onPressed: function(event) {
        if ((event.modifiers & Qt.ControlModifier) && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
            root.send(); event.accepted = true
        }
    }
    Connections {
        target: root.backend
        function onSent() { message.text = "" }
        function onSaved() { root.configuring = false; root.clearSecrets(); root.focusEditor() }
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.maximumWidth: Infinity
        ColumnLayout {
            Layout.fillWidth: true
            Layout.maximumWidth: Infinity
            spacing: Style.space(3)
            Text {
                text: "OmaBark"
                color: Commons.Color.foreground
                font.family: Style.font.family
                font.pixelSize: Style.font.title
                font.bold: true
            }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Send text to your Apple device.")
                color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.65)
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
            }
        }
        Ui.Button {
            text: root.setup ? qsTr("Back") : ""
            iconText: root.setup ? "" : "\uf013"
            tooltipText: root.setup ? "" : qsTr("Settings")
            Accessible.name: root.setup ? qsTr("Back") : qsTr("Settings")
            Layout.alignment: Qt.AlignTop
            focusable: true
            enabled: !root.backend.busy
            onClicked: root.setup ? root.goBack() : root.openSettings()
        }
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Commons.Color.foreground; opacity: 0.12 }

    ColumnLayout {
        visible: !root.setup
        Layout.fillWidth: true
        spacing: Style.space(12)
        Controls.ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: Style.space(110)
            clip: true
            Controls.TextArea {
                id: message
                objectName: "message"
                placeholderText: qsTr("Type a message…")
                wrapMode: TextEdit.Wrap
                textFormat: TextEdit.PlainText
                selectByMouse: true
                color: Commons.Color.foreground
                placeholderTextColor: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.65)
                selectionColor: Style.selectionFillFor(Commons.Color.foreground, Commons.Color.accent)
                selectedTextColor: Commons.Color.foreground
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                padding: Style.space(12)
                enabled: !root.backend.busy
                Accessible.name: qsTr("Message")
                background: Rectangle {
                    color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.035)
                    radius: Style.cornerRadius
                    border.width: 1
                    border.color: message.activeFocus ? Commons.Color.accent : Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.18)
                }
                Keys.onPressed: function(event) {
                    if ((event.modifiers & Qt.ControlModifier) && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
                        root.send(); event.accepted = true
                    }
                }
            }
        }
        Ui.Button {
            id: sendButton
            Layout.fillWidth: true
            implicitHeight: sendLabel.implicitHeight + verticalPadding * 2 + Style.space(2)
            Accessible.name: qsTr("Send [Ctrl+Enter]")
            selected: true
            bordered: true
            focusable: true
            enabled: root.canSend
            opacity: enabled ? 1 : 0.5
            onClicked: root.send()
            Row {
                id: sendLabel
                anchors.centerIn: parent
                spacing: Style.space(6)
                Text {
                    text: root.backend.busy ? qsTr("Sending…") : qsTr("Send")
                    color: Style.selectedStateColor(Commons.Color.foreground, Commons.Color.accent)
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: "[Ctrl+Enter]"
                    color: root.secondaryTextColor
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
        Text {
            Layout.fillWidth: true
            visible: root.messageBytes > 1800
            text: root.messageBytes > 32000 ? qsTr("Over 32 KB limit") : qsTr("Long text sends in numbered parts")
            color: root.messageBytes > 32000 ? Commons.Color.urgent : Commons.Color.foreground
            wrapMode: Text.WordWrap
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
        }
    }

    ColumnLayout {
        visible: root.setup
        Layout.fillWidth: true
        spacing: Style.space(12)
        Ui.TextField {
            id: notificationTitleField
            Layout.fillWidth: true
            placeholderText: qsTr("Title · From Omarchy")
            maximumLength: 120
            enabled: !root.backend.busy
            Accessible.name: qsTr("Notification title; defaults to From Omarchy")
        }
        Ui.Dropdown {
            Layout.fillWidth: true
            showLabel: false
            options: [
                {value: "default", label: qsTr("Default Server · api.day.app")},
                {value: "custom", label: qsTr("Custom server")}
            ]
            value: root.advanced ? "custom" : "default"
            enabled: !root.backend.busy
            onChanged: function(value) {
                root.advanced = value === "custom"
                root.clearSecrets()
            }
        }
        Text {
            Layout.fillWidth: true
            text: root.advanced ? qsTr("Enter your server URL and device key.")
                : qsTr("Copy your test URL from Bark.")
            wrapMode: Text.NoWrap
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: Math.max(8, Style.font.caption - 2)
            elide: Text.ElideRight
            color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.65)
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
        }
        Ui.TextField {
            id: deviceUrl
            visible: !root.advanced
            Layout.fillWidth: true
            placeholderText: root.reuseExisting ? qsTr("Saved URL · leave blank to keep") : "https://api.day.app/your-key/…"
            password: true
            maximumLength: 2048
            enabled: !root.backend.busy
            Accessible.name: qsTr("Bark test URL")
        }
        Ui.TextField {
            id: server
            visible: root.advanced
            Layout.fillWidth: true
            text: "https://api.day.app"
            placeholderText: qsTr("HTTPS server URL")
            maximumLength: 2048
            enabled: !root.backend.busy
            Accessible.name: qsTr("HTTPS server URL")
        }
        Ui.TextField {
            id: deviceKey
            visible: root.advanced
            Layout.fillWidth: true
            placeholderText: root.reuseExisting ? qsTr("Saved key · leave blank to keep") : qsTr("Device key")
            password: true
            maximumLength: 256
            enabled: !root.backend.busy
            Accessible.name: qsTr("Device key")
        }
        Text {
            Layout.fillWidth: true
            text: qsTr("A test notification will be sent before saving. Keys stay in private local storage.")
            wrapMode: Text.WordWrap
            color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.65)
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
        }
        Text {
            Layout.fillWidth: true
            visible: unescape(encodeURIComponent(notificationTitleField.text)).length > 120
            text: qsTr("Title exceeds 120 bytes")
            color: Commons.Color.urgent
            wrapMode: Text.WordWrap
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
        }
        Ui.Button {
            Layout.fillWidth: true
            text: root.backend.busy ? qsTr("Testing…") : qsTr("Test and Save")
            selected: true
            bordered: true
            focusable: true
            enabled: !root.backend.busy && unescape(encodeURIComponent(notificationTitleField.text)).length <= 120
                && (root.reuseExisting || (root.advanced ? deviceKey.text.trim() !== "" : deviceUrl.text.trim() !== ""))
            opacity: enabled ? 1 : 0.5
            onClicked: root.backend.run({action: "save", title: notificationTitleField.text,
                serverMode: root.advanced ? "custom" : "default", reuseExisting: root.reuseExisting,
                url: root.advanced ? "" : deviceUrl.text,
                server: root.chosenServer, key: deviceKey.text})
        }
    }

    Text {
        Layout.fillWidth: true
        visible: root.backend.status !== ""
        text: root.setup ? root.backend.status : root.backend.shortStatus
        horizontalAlignment: root.setup ? Text.AlignLeft : Text.AlignHCenter
        textFormat: Text.PlainText
        color: root.backend.failed ? Commons.Color.urgent : Commons.Color.accent
        wrapMode: Text.WordWrap
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        Accessible.role: Accessible.StaticText
        Accessible.name: root.backend.status
        HoverHandler { id: statusHover }
        Controls.ToolTip.visible: !root.setup && root.backend.failed && statusHover.hovered
        Controls.ToolTip.text: root.backend.status
        Controls.ToolTip.delay: 300
    }
}
