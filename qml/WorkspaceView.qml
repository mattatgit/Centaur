import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: workspace
    property bool buildMode: false
    signal settingsRequested()
    SplitView {
        anchors.fill: parent
        anchors.leftMargin: 12; anchors.rightMargin: 12; anchors.bottomMargin: 12
        orientation: Qt.Horizontal
        handle: Rectangle { implicitWidth: 10; color: Theme.ice }
        CanvasView {
            id: canvas
            SplitView.fillWidth: true
            SplitView.minimumWidth: 480
            buildMode: workspace.buildMode
            onCommentDrawn: chat.focusComposer()
        }
        ChatPanel {
            id: chat
            SplitView.preferredWidth: 430
            SplitView.minimumWidth: 370
            SplitView.maximumWidth: 620
            onSettingsRequested: workspace.settingsRequested()
            onSendRequested: function(text) {
                if (text.toLowerCase().indexOf("@" + Backend.project.agentName.toLowerCase()) !== -1)
                    canvas.capture(function(path, revision) { chat.finishSending(text, Backend.sendMessage(text, path, revision)) })
                else chat.finishSending(text, Backend.sendMessage(text))
            }
        }
    }
}
