import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    color: "white"; radius: 16
    signal createRequested()
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
                            TapHandler { onTapped: Backend.openProject(modelData.id) }
                            ColumnLayout {
                                anchors.fill: parent; anchors.margins: 24; spacing: 12
                                Rectangle {
                                    width: 54; height: 54; radius: 14; color: Theme.ink
                                    Text { anchors.centerIn: parent; text: modelData.name.substring(0, 1).toUpperCase(); color: Theme.lime; font.pointSize: 23; font.weight: Font.DemiBold }
                                }
                                Text { text: modelData.name; color: Theme.ink; font.pointSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                                Text { text: modelData.description || "A new idea, ready to take shape."; color: Theme.muted; font.pointSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                                Item { Layout.fillHeight: true }
                                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                                Text { text: "Native app"; color: Theme.muted; font.pointSize: 10 }
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
