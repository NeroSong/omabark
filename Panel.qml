import QtQuick
import QtQuick.Controls as Controls
import qs.Commons
import qs.Ui as Ui

Ui.Panel {
    id: root
    moduleName: "nerosong.omabark"
    manageIpc: false
    property var anchorItem: null
    property var hostWidget: null
    function open() { barkBackend.refresh(); controller.show(); Qt.callLater(view.focusEditor) }
    function paste() {
        if (barkBackend.busy) return
        controller.show()
        barkBackend.run({action: "clipboard"})
    }
    function close() { view.clearSecrets(); controller.hide() }
    function switchPanel(direction) {
        return bar && typeof bar.switchPanelFrom === "function"
            ? bar.switchPanelFrom(hostWidget || root, direction) : false
    }
    Backend { id: barkBackend }
    Connections {
        target: barkBackend
        function onBusyChanged() {
            if (!barkBackend.busy && root.opened) Qt.callLater(view.focusEditor)
        }
        function onPasted(text) { view.replaceDraft(text) }
    }
    Ui.KeyboardPanel {
        id: popup
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        focusTarget: view
        contentWidth: fittedContentWidth(Style.space(340))
        contentHeight: fittedContentHeight(view.implicitHeight)
        Controls.ScrollView {
            anchors.fill: parent
            clip: true
            contentWidth: availableWidth
            OmaBarkView {
                id: view
                width: parent.width
                backend: barkBackend
                onCloseRequested: root.close()
            }
        }
    }
}
