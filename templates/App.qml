import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: app
    width: 520; height: 640
    color: "#fafbf7"
    property int completed: 0
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 32; spacing: 20
        RowLayout {
            Layout.fillWidth: true
            Text { text: "Our everyday"; color: "#293326"; font.pointSize: 22; font.family: "Inter Tight"; font.weight: Font.DemiBold }
            Item { Layout.fillWidth: true }
            ToolButton {
                text: "•••"
                onClicked: options.open()
                Menu { id: options; popupType: Popup.Window; MenuItem { text: "About this app"; onTriggered: about.open() } }
            }
        }
        Text { text: "A little space for the things we share."; color: "#84907c"; font.pointSize: 12; font.family: "Inter"; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 98; radius: 16; color: "#e9efdd"
            Column {
                anchors.fill: parent; anchors.margins: 20; spacing: 8
                Text { text: "Make room for a good day."; color: "#35432c"; font.pointSize: 15; font.family: "Inter Tight"; font.weight: Font.DemiBold }
                Text { text: app.completed + " things ticked off together"; color: "#6d7d5f"; font.pointSize: 11; font.family: "Inter" }
            }
        }
        Text { text: "TODAY, TOGETHER"; color: "#84907c"; font.pointSize: 9; font.family: "Inter"; font.letterSpacing: 1.5; Layout.topMargin: 8 }
        ListView {
            id: tasks
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 8
            model: ListModel {
                id: taskModel
                ListElement { title: "Plan something for the weekend"; done: false }
                ListElement { title: "Pick a recipe to cook together"; done: false }
                ListElement { title: "Get outside for a little while"; done: false }
            }
            delegate: Rectangle {
                required property string title
                required property bool done
                required property int index
                width: tasks.width; height: 54; radius: 10; color: "white"
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 12
                    CheckBox { checked: done; onToggled: { taskModel.setProperty(index, "done", checked); app.completed += checked ? 1 : -1 } }
                    Text { text: title; font.pointSize: 11.5; font.family: "Inter"; font.strikeout: done; color: done ? "#9aa28f" : "#35432c"; Layout.fillWidth: true; elide: Text.ElideRight }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            TextField { id: newTask; objectName: "newTask"; Layout.fillWidth: true; placeholderText: "Add a little thing…"; font.pointSize: 12; font.family: "Inter"; onAccepted: addTask.clicked() }
            Button { id: addTask; text: "Add"; enabled: newTask.text.trim().length > 0; onClicked: { taskModel.append({ title: newTask.text.trim(), done: false }); newTask.clear() } }
        }
    }
    Dialog {
        id: about; title: "Made together"; anchors.centerIn: parent; modal: true; standardButtons: Dialog.Ok
        Label { text: "A real native app, running inside Centaur."; font.pointSize: 12; font.family: "Inter" }
    }
}
