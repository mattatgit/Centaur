import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    objectName: "centaurWindow"
    visible: true
    width: 1440
    height: 940
    minimumWidth: Backend.projectId ? 1000 : 360
    minimumHeight: 680
    title: Backend.projectId ? Backend.project.name + " · Centaur" : "Centaur"
    color: Theme.ice
    font.family: "Inter"
    font.pointSize: 11
    property string notification: ""

    header: Item {
        height: 80
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: window.width < 600 ? 16 : 28
            anchors.rightMargin: window.width < 600 ? 16 : 28
            spacing: window.width < 600 ? 10 : 16
            Rectangle {
                width: 38; height: 38; radius: 12; color: Theme.ink
                Grid {
                    anchors.centerIn: parent; columns: 2; spacing: 4
                    Repeater { model: 4; Rectangle { width: 5; height: 5; radius: 3; color: "white" } }
                }
                TapHandler { onTapped: Backend.closeProject() }
                Accessible.name: "Back to projects"
            }
            Text { text: "centaur"; font.pointSize: 17; font.weight: Font.DemiBold; color: Theme.ink }
            Rectangle { visible: !!Backend.projectId; width: 1; height: 22; color: Theme.line; Layout.leftMargin: 8; Layout.rightMargin: 8 }
            FlatButton { visible: !!Backend.projectId; text: "Projects"; tone: "plain"; onClicked: Backend.closeProject() }
            Text { visible: !!Backend.projectId; text: "/"; color: "#b8bdb5"; font.pointSize: 14 }
            Text { visible: !!Backend.projectId; text: Backend.project.name || ""; color: Theme.ink; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.maximumWidth: 300 }
            Item { Layout.fillWidth: true }
            Row {
                visible: window.width >= 600
                spacing: 8
                Rectangle { width: 6; height: 6; radius: 3; color: Theme.green; anchors.verticalCenter: parent.verticalCenter }
                Text { text: "Local session"; color: Theme.muted; font.pointSize: 10 }
            }
            FlatButton { text: Backend.author; tone: "plain"; Layout.maximumWidth: window.width < 600 ? 130 : 220; onClicked: { nameField.text = Backend.author; agentField.text = Backend.project.agentName || "centaur"; settings.open() } }
        }
    }

    Loader {
        anchors.fill: parent
        sourceComponent: Backend.projectId ? workspaceComponent : projectsComponent
    }
    Component {
        id: projectsComponent
        ProjectsView { onCreateRequested: createDialog.open() }
    }
    Component { id: workspaceComponent; WorkspaceView {} }

    Dialog {
        id: createDialog
        title: "Make something together"
        modal: true
        anchors.centerIn: parent
        width: Math.min(460, window.width - 32)
        padding: 28
        standardButtons: Dialog.NoButton
        background: Rectangle { color: "white"; radius: 20; border.color: Theme.line }
        ColumnLayout {
            width: parent.width
            spacing: 16
            Text { text: "One project, one native app."; color: Theme.muted; font.pointSize: 11 }
            TextField { id: projectName; objectName: "projectName"; placeholderText: "Project name"; Layout.fillWidth: true; maximumLength: 100; font.pointSize: 12; onAccepted: if (text.trim()) createButton.clicked() }
            TextArea { id: projectDescription; placeholderText: "What would you like to make?"; Layout.fillWidth: true; Layout.preferredHeight: 100; wrapMode: TextEdit.Wrap; font.pointSize: 12; background: Rectangle { color: Theme.ice; radius: 10 } }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                FlatButton { text: "Cancel"; tone: "plain"; onClicked: createDialog.close() }
                FlatButton {
                    id: createButton
                    text: "Create project"; tone: "dark"; enabled: projectName.text.trim().length > 0
                    onClicked: { Backend.createProject(projectName.text, projectDescription.text); createDialog.close(); projectName.clear(); projectDescription.clear() }
                }
            }
        }
        onOpened: projectName.forceActiveFocus()
    }

    Dialog {
        id: settings
        title: "Your space"
        modal: true; anchors.centerIn: parent; width: Math.min(460, window.width - 32); padding: 28
        standardButtons: Dialog.NoButton
        background: Rectangle { color: "white"; radius: 20; border.color: Theme.line }
        ColumnLayout {
            width: parent.width; spacing: 14
            Text { text: "Your name in this conversation"; color: Theme.muted }
            TextField { id: nameField; Layout.fillWidth: true; maximumLength: 50; font.pointSize: 12 }
            Text { visible: !!Backend.projectId; text: "Address the agent as"; color: Theme.muted }
            TextField { id: agentField; visible: !!Backend.projectId; Layout.fillWidth: true; maximumLength: 30; placeholderText: "centaur"; font.pointSize: 12 }
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: "Open another Centaur window with the same project folder to try a conversation with a second author. This first prototype shares sessions on one computer."; color: Theme.muted; font.pointSize: 10.5 }
            FlatButton {
                text: "Done"; tone: "dark"; Layout.alignment: Qt.AlignRight
                enabled: nameField.text.trim().length > 0
                onClicked: { Backend.author = nameField.text; if (Backend.projectId) Backend.renameAgent(agentField.text); settings.close() }
            }
        }
    }

    Rectangle {
        z: 100
        visible: window.notification.length > 0
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: 24
        width: Math.min(parent.width - 80, notice.implicitWidth + 48)
        height: notice.implicitHeight + 30
        radius: 12; color: Theme.ink
        Text { id: notice; anchors.fill: parent; anchors.margins: 15; text: window.notification; wrapMode: Text.Wrap; color: "white"; font.pointSize: 11 }
        TapHandler { onTapped: window.notification = "" }
        Timer { id: noticeTimer; interval: 8000; onTriggered: window.notification = "" }
    }
    Connections { target: Backend; function onError(message) { window.notification = message; noticeTimer.restart() } }
}
