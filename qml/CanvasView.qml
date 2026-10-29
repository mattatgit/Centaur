import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Centaur.Native 1.0

Rectangle {
    id: canvas
    color: "white"; radius: 16; clip: true
    property bool buildMode: false
    property string tool: "draw"
    property int revision: Backend.project.revision || 1
    onRevisionChanged: tool = "draw"
    signal commentDrawn()
    property var currentMarks: (Backend.project.annotations || []).filter(function(mark) { return mark.revision === Backend.project.revision })
    function capture(callback) {
        const path = Backend.capturePath()
        const capturedRevision = Backend.project.revision
        board.grabToImage(function(result) { callback(result.saveToFile(path) ? path : "", capturedRevision) })
    }
    Item {
        id: board
        objectName: "canvasBoard"
        width: 1000; height: 800
        transformOrigin: Item.TopLeft
        scale: Math.max(0.1, Math.min((canvas.width - 32) / width, (canvas.height - 100) / height))
        x: (canvas.width - width * scale) / 2
        y: (canvas.height - 100 - height * scale) / 2
        Rectangle { anchors.fill: parent; color: "white" }
        Rectangle {
            id: appFrame
            objectName: "nativeAppFrame"
            x: 240; y: 60; width: 520; height: 640
            color: "white"; border.color: "#d4d8cf"; border.width: 1
            Loader { anchors.fill: parent; anchors.margins: 1; source: Backend.embeddingSupported ? "WaylandPreview.qml" : "PreviewUnavailable.qml" }
        }
        DesignGrid {
            objectName: "designGrid"
            anchors.fill: parent; visible: Backend.gridEnabled
            step: Backend.gridSize; color: Backend.gridColor; opacity: Backend.gridOpacity / 100
            origin: Qt.point(appFrame.x, appFrame.y)
        }
        Text { x: 240; y: 718; width: 520; horizontalAlignment: Text.AlignHCenter; text: Backend.previewStatus; color: Theme.muted; readonly property real typeSize: 10; font.pointSize: typeSize; font.family: Theme.familyForSize(typeSize, -1); wrapMode: Text.Wrap }
        InkLayer {
            objectName: "inkLayer"
            anchors.fill: parent
            visible: canvas.buildMode
            tool: canvas.buildMode && Backend.canContribute && canvas.tool ? canvas.tool : "interact"
            annotations: canvas.currentMarks
            onStrokeFinished: function(stroke) {
                stroke.frame = { x: appFrame.x / board.width, y: appFrame.y / board.height, width: appFrame.width / board.width, height: appFrame.height / board.height }
                Backend.addAnnotation(stroke)
                if (canvas.tool === "comment") canvas.commentDrawn()
            }
        }
    }
    FlatButton {
        objectName: "gridToggle"
        x: 8; y: 8; width: 24; height: 24
        iconSource: "qrc:/assets/dialogue/grid.svg"
        checkable: true; checked: Backend.gridEnabled
        onClicked: Backend.gridEnabled = !Backend.gridEnabled
        foreground: checked ? "white" : Theme.muted
        background: Rectangle { radius: 8; color: parent.checked ? "#20a8f0" : Theme.ice; border.width: parent.visualFocus ? 2 : 0; border.color: Theme.blue }
        ToolTip.text: checked ? "Hide grid" : "Show grid"
        Accessible.name: checked ? "Hide grid" : "Show grid"
    }
    Rectangle {
        visible: canvas.buildMode
        anchors.bottom: parent.bottom; anchors.bottomMargin: 16; anchors.horizontalCenter: parent.horizontalCenter
        width: 296; height: 48; radius: 16; color: "white"; border.width: 1; border.color: "#14000000"
        Row { anchors.centerIn: parent; spacing: 8
            FlatButton { width: 80; text: "✎ Draw"; tone: "plain"; checkable: true; autoExclusive: true; checked: canvas.tool === "draw"; onClicked: canvas.tool = "draw"; Accessible.name: "Draw" }
            FlatButton { width: 104; text: "Comment"; tone: "plain"; iconSource: "qrc:/assets/dialogue/arrow.svg"; iconSize: 16; checkable: true; autoExclusive: true; checked: canvas.tool === "comment"; onClicked: canvas.tool = "comment" }
            FlatButton { width: 80; text: "↶ Undo"; tone: "plain"; enabled: Backend.canContribute && canvas.currentMarks.some(function(mark) { return mark.author === Backend.author }); onClicked: Backend.undoAnnotation(); Accessible.name: "Undo" }
        }
    }
    Shortcut { sequence: "Escape"; onActivated: canvas.tool = "" }
}
