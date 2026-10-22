import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Centaur.Native 1.0

Rectangle {
    id: canvas
    color: Theme.canvas
    radius: 16
    clip: true
    property string tool: "interact"
    property int revision: Backend.project.revision || 1
    onRevisionChanged: tool = "interact"
    signal commentDrawn()
    property var currentMarks: (Backend.project.annotations || []).filter(function(mark) { return mark.revision === Backend.project.revision })

    function capture(callback) {
        const path = Backend.capturePath()
        const capturedRevision = Backend.project.revision
        board.grabToImage(function(result) { callback(result.saveToFile(path) ? path : "", capturedRevision) })
    }

    RowLayout {
        anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
        anchors.margins: 18
        spacing: 10
        Text { text: "Canvas"; color: Theme.ink; font.pointSize: 10.5; font.weight: Font.DemiBold }
        Item { Layout.fillWidth: true }
        FlatButton { text: "Open repo"; tone: "plain"; onClicked: Backend.revealProject(); ToolTip.text: "Open the project folder" }
        FlatButton { text: "Restart app"; tone: "plain"; enabled: Backend.embeddingSupported; onClicked: Backend.restartPreview() }
        FlatButton { text: "Archive"; tone: "plain"; onClicked: archiveDialog.open() }
    }

    Item {
        id: board
        objectName: "canvasBoard"
        width: 1000; height: 800
        transformOrigin: Item.TopLeft
        scale: Math.max(0.1, Math.min((canvas.width - 32) / width, (canvas.height - 155) / height))
        x: (canvas.width - width * scale) / 2
        y: 60 + (canvas.height - 155 - height * scale) / 2
        Rectangle { anchors.fill: parent; color: Theme.canvas }
        Row {
            x: 240; y: 23; spacing: 10
            Text { text: Backend.project.name || ""; color: Theme.ink; font.pointSize: 11; font.weight: Font.DemiBold }
            Rectangle {
                width: revisionLabel.implicitWidth + 12; height: 22; radius: 5; color: "#e1e5db"
                Text { id: revisionLabel; anchors.centerIn: parent; text: "V" + (Backend.project.revision || 1); color: "#5a6652"; font.pointSize: 9 }
            }
        }
        Rectangle {
            id: appFrame
            objectName: "nativeAppFrame"
            x: 240; y: 60; width: 520; height: 640
            color: "white"; border.color: "#d4d8cf"; border.width: 1
            Loader {
                id: preview
                anchors.fill: parent; anchors.margins: 1
                source: Backend.embeddingSupported ? "WaylandPreview.qml" : "PreviewUnavailable.qml"
            }
        }
        Text {
            x: 240; y: 718; width: 520; horizontalAlignment: Text.AlignHCenter
            text: Backend.previewStatus; color: Theme.muted; font.pointSize: 10
            wrapMode: Text.Wrap
        }
        InkLayer {
            id: ink
            objectName: "inkLayer"
            anchors.fill: parent
            tool: canvas.tool
            annotations: canvas.currentMarks
            onStrokeFinished: function(stroke) {
                stroke.frame = { x: appFrame.x / board.width, y: appFrame.y / board.height, width: appFrame.width / board.width, height: appFrame.height / board.height }
                Backend.addAnnotation(stroke)
                if (canvas.tool === "comment") canvas.commentDrawn()
            }
        }
    }

    ColumnLayout {
        anchors.bottom: parent.bottom; anchors.bottomMargin: 20
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 10
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: canvas.tool === "draw" ? "Sketch an idea, then describe it in the chat."
                : canvas.tool === "comment" ? "Drag an arrow to what you mean, then add a message."
                : "Try the app, or draw an idea together."
            color: Theme.muted; font.pointSize: 10
        }
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: tools.implicitWidth + 12; height: 50; radius: 14; color: "white"
            RowLayout {
                id: tools
                anchors.centerIn: parent; spacing: 5
                FlatButton { text: "↖  Use app"; checkable: true; checked: canvas.tool === "interact"; onClicked: canvas.tool = "interact" }
                FlatButton { text: "✎  Draw"; checkable: true; checked: canvas.tool === "draw"; onClicked: canvas.tool = "draw" }
                FlatButton { text: "↗  Comment"; checkable: true; checked: canvas.tool === "comment"; onClicked: canvas.tool = "comment" }
                Rectangle { width: 1; height: 22; color: Theme.line; Layout.leftMargin: 5; Layout.rightMargin: 5 }
                FlatButton { text: "↶"; tone: "plain"; enabled: canvas.currentMarks.some(function(m) { return m.author === Backend.author }); onClicked: Backend.undoAnnotation(); ToolTip.text: "Undo your last mark" }
            }
        }
    }
    Shortcut { sequence: "Escape"; onActivated: canvas.tool = "interact" }
    Dialog {
        id: archiveDialog
        width: 420
        modal: true; anchors.centerIn: parent; title: "Archive this project?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        Label { text: "Your app and conversation stay saved in the project folder."; wrapMode: Text.Wrap; width: 320 }
        onAccepted: Backend.archiveProject(Backend.projectId)
    }
}
