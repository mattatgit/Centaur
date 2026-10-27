import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Centaur.Native 1.0

Rectangle {
    id: root
    color: "white"; radius: 16
    signal createRequested()
    property string selectedProjectId: ""
    property bool selectedProjectRemote: false
    property string selectedProjectName: ""
    function showProjectMenu(button, project) {
        selectedProjectId = project.id
        selectedProjectName = project.name
        selectedProjectRemote = !!project.remote
        const position = button.mapToItem(root, button.width, button.height + 8)
        projectMenu.x = Math.max(8, Math.min(root.width - projectMenu.width - 8, position.x - projectMenu.width))
        projectMenu.y = position.y
        projectMenu.open()
    }
    function saveProjectName() {
        if (!renameName.text.trim()) return
        renameDialog.close()
        Backend.renameProject(selectedProjectId, renameName.text)
    }
    Menu {
        id: projectMenu
        objectName: "projectCardMenu"
        width: 176; padding: 4
        background: Rectangle { color: "white"; radius: 12; border.color: Theme.dust }
        delegate: MenuItem {
            id: menuEntry
            objectName: "projectMenuEntry-" + text
            implicitHeight: 36
            leftPadding: 12; rightPadding: 12
            contentItem: Text { text: menuEntry.text; font.pixelSize: 12; color: menuEntry.enabled ? Theme.ink : Theme.muted; verticalAlignment: Text.AlignVCenter }
            background: Rectangle { radius: 8; color: menuEntry.highlighted || menuEntry.down ? Theme.dust : "transparent" }
        }
        Action { text: "Rename"; enabled: !root.selectedProjectRemote; onTriggered: { renameName.text = root.selectedProjectName; renameDialog.open() } }
        Action { text: root.selectedProjectRemote ? "Leave project" : "Delete"; onTriggered: deleteDialog.open() }
    }
    Dialog {
        id: renameDialog
        objectName: "renameProjectDialog"
        title: "Rename project"
        parent: Overlay.overlay
        modal: true; anchors.centerIn: parent
        width: Math.min(400, root.width - 24); padding: 24
        background: Rectangle { radius: 16; color: "white"; border.color: Theme.dust }
        header: Label { text: renameDialog.title; color: Theme.ink; font.pixelSize: 16; font.weight: Font.DemiBold; leftPadding: 24; rightPadding: 24; topPadding: 24; wrapMode: Text.Wrap }
        ColumnLayout {
            width: parent.width; spacing: 20
            TextField { id: renameName; objectName: "renameProjectName"; Layout.fillWidth: true; maximumLength: 100; selectByMouse: true; onAccepted: root.saveProjectName(); Accessible.name: "Project name" }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                FlatButton { text: "Cancel"; tone: "plain"; onClicked: renameDialog.close() }
                FlatButton { text: "Save"; tone: "dark"; enabled: renameName.text.trim().length > 0; onClicked: root.saveProjectName() }
            }
        }
        onOpened: { renameName.forceActiveFocus(); renameName.selectAll() }
    }
    Dialog {
        id: deleteDialog
        objectName: "deleteProjectDialog"
        title: root.selectedProjectRemote ? "Leave project?" : "Delete project?"
        parent: Overlay.overlay
        modal: true; anchors.centerIn: parent
        width: Math.min(420, root.width - 24); padding: 24
        background: Rectangle { radius: 16; color: "white"; border.color: Theme.dust }
        header: Label { text: deleteDialog.title; color: Theme.ink; font.pixelSize: 16; font.weight: Font.DemiBold; leftPadding: 24; rightPadding: 24; topPadding: 24; wrapMode: Text.Wrap }
        ColumnLayout {
            width: parent.width; spacing: 20
            Text { text: root.selectedProjectRemote ? "Leave “" + root.selectedProjectName + "” on this device? The owner’s project stays available to the other people." : "“" + root.selectedProjectName + "” and its app and conversation will be removed from Centaur."; textFormat: Text.PlainText; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 14; color: Theme.ink }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                FlatButton { id: cancelDelete; objectName: "cancelProjectDeletion"; text: "Cancel"; tone: "plain"; onClicked: deleteDialog.close() }
                FlatButton { objectName: "confirmProjectDeletion"; text: root.selectedProjectRemote ? "Leave project" : "Delete project"; tone: "dark"; onClicked: { deleteDialog.close(); root.selectedProjectRemote ? Backend.leaveProject(root.selectedProjectId) : Backend.deleteProject(root.selectedProjectId) } }
            }
        }
        onOpened: cancelDelete.forceActiveFocus()
    }
        ScrollView {
            id: projectsScroll
            objectName: "projectsScroll"
            anchors.fill: parent
            anchors.margins: root.width < 720 ? 24 : 40
            clip: true
            contentWidth: availableWidth
            contentHeight: projectContent.implicitHeight
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            Column {
                id: projectContent
                width: projectsScroll.availableWidth
                Grid {
                    id: projectGrid
                    objectName: "projectGrid"
                    width: parent.width
                    visible: Backend.projects.length > 0
                    spacing: 32
                    columns: Math.max(1, Math.min(5, Math.floor((width + spacing) / (260 + spacing))))
                    Repeater {
                        model: Backend.projects
                        delegate: Rectangle {
                            required property var modelData
                            objectName: "projectCard"
                            width: Math.max(0, (projectGrid.width - (projectGrid.columns - 1) * projectGrid.spacing) / projectGrid.columns)
                            height: 256; radius: 16; color: Theme.ice
                            border.width: hover.hovered ? 1 : 0; border.color: "#d3d7ce"
                            HoverHandler { id: hover }
                            Button {
                                anchors.fill: parent
                                background: Item {}
                                contentItem: Item {}
                                onClicked: Backend.openProject(modelData.id)
                                Accessible.name: "Open " + modelData.name
                                Rectangle { anchors.fill: parent; radius: 16; color: "transparent"; border.width: parent.visualFocus ? 2 : 0; border.color: Theme.blue }
                            }
                            ColumnLayout {
                                anchors.fill: parent; anchors.margins: 24; spacing: 12
                                Rectangle {
                                    width: 54; height: 54; radius: 14; color: Theme.ink
                                    Text { anchors.centerIn: parent; text: modelData.name.substring(0, 1).toUpperCase(); color: Theme.lime; font.pointSize: 23; font.weight: Font.DemiBold }
                                }
                                Text { textFormat: Text.PlainText; text: modelData.name; color: Theme.ink; font.pointSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                                Text { textFormat: Text.PlainText; text: modelData.description || "A new idea, ready to take shape."; color: Theme.muted; font.pointSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                                Item { Layout.fillHeight: true }
                                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                                Text { text: modelData.remote ? (modelData.connected ? "Shared project" : "Shared · host unavailable") : "Native app"; color: Theme.muted; font.pointSize: 10 }
                            }
                            Button {
                                id: menuButton
                                objectName: "projectMenuButton"
                                anchors.right: parent.right; anchors.rightMargin: 16
                                y: 20; width: 32; height: 32
                                padding: 0
                                hoverEnabled: true
                                contentItem: SvgIcon { source: "qrc:/assets/dialogue/tile-menu.svg"; color: Theme.muted }
                                background: Rectangle {
                                    radius: 8
                                    color: menuButton.hovered || menuButton.down || (projectMenu.opened && root.selectedProjectId === modelData.id) ? Theme.dust : "transparent"
                                    border.width: menuButton.visualFocus ? 2 : 0; border.color: Theme.blue
                                }
                                onClicked: root.showProjectMenu(menuButton, modelData)
                                Accessible.name: "Options for " + modelData.name
                                ToolTip.visible: hovered; ToolTip.text: "Project options"
                            }
                        }
                    }
                }
                Rectangle {
                    objectName: "projectEmptyState"
                    visible: Backend.projects.length === 0
                    width: Math.min(420, parent.width); height: 265; radius: 18; color: Theme.ice; border.color: Theme.line
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 28; spacing: 16
                        Text { text: "What shall we make?"; font.pointSize: 18; font.weight: Font.DemiBold; color: Theme.ink; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        Text { text: "A family planner, a little game, a shared collection. Every project becomes its own native app."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: 12; color: Theme.muted }
                        Item { Layout.fillHeight: true }
                        FlatButton { text: "Create your first project"; tone: "lime"; onClicked: root.createRequested() }
                    }
                }
            }
        }
}
