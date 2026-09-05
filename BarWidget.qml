import QtQuick
import Quickshell.Io
import qs.Commons
import qs.Ui as Ui

Ui.BarWidget {
    id: root
    moduleName: "nerosong.omabark"
    readonly property bool opened: panelLoader.item ? panelLoader.item.opened : false
    readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing : false
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    function open() { if (panelLoader.item) panelLoader.item.open() }
    function paste() {
        var chosen = bar && typeof bar.findPanelWidget === "function"
            ? bar.findPanelWidget(moduleName) : null
        if (chosen && chosen !== root && typeof chosen.paste === "function") {
            chosen.paste()
            return
        }
        if (panelLoader.item) panelLoader.item.paste()
    }
    IpcHandler {
        target: root.moduleName
        function paste(): void { root.paste() }
    }
    function close() { if (panelLoader.item) panelLoader.item.close() }
    function toggle() { if (panelLoader.item) panelLoader.item.toggle() }
    function closeForPopoutSwitch() { if (panelLoader.item) panelLoader.item.closeForPopoutSwitch() }
    function injectPanel() {
        if (!panelLoader.item) return
        panelLoader.item.bar = root.bar
        panelLoader.item.settings = root.settings
        panelLoader.item.anchorItem = button
        panelLoader.item.hostWidget = root
    }
    onBarChanged: injectPanel()
    onSettingsChanged: injectPanel()

    Loader {
        id: panelLoader
        source: Qt.resolvedUrl("Panel.qml")
        visible: false
        onLoaded: { root.injectPanel(); Qt.callLater(root.injectPanel) }
    }
    Ui.BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        iconComponent: Component {
            BarkIcon {
                anchors.fill: parent
                anchors.margins: Style.space(2)
                foreground: button.foreground
            }
        }
        slotSize: Style.bar.statusSlot
        tooltipText: qsTr("OmaBark")
        onPressed: function(buttonCode) { if (buttonCode === Qt.LeftButton) root.toggle() }
    }
}
