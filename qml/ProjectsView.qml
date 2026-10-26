import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    signal createRequested()
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 48
        spacing: 28
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 8
                Text { text: "A place to make things."; color: Theme.ink; font.pointSize: 28; font.weight: Font.DemiBold }
                Text { text: "Start with an idea. Shape it together."; color: Theme.muted; font.pointSize: 12.5 }
            }
            Item { Layout.fillWidth: true }
            FlatButton { text: "+  New project"; tone: "dark"; onClicked: root.createRequested() }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
        RowLayout {
            Text { text: "Your projects"; font.pointSize: 12; font.weight: Font.DemiBold; color: Theme.ink }
            Text { text: Backend.projects.length; color: Theme.muted; font.pointSize: 10.5 }
            Item { Layout.fillWidth: true }
            Text { text: "Saved on this computer"; color: Theme.muted; font.pointSize: 10.5 }
        }
        ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true
            Flow {
                width: parent.width
                spacing: 20
                Repeater {
                    model: Backend.projects
                    delegate: Rectangle {
                        required property var modelData
                        width: 310; height: 256; radius: 16; color: "white"
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
                Rectangle {
                    visible: Backend.projects.length === 0
                    width: 420; height: 265; radius: 18; color: "white"; border.color: Theme.line
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 28; spacing: 16
                        Text { text: "What shall we make?"; font.pointSize: 18; font.weight: Font.DemiBold; color: Theme.ink }
                        Text { text: "A family planner, a little game, a shared collection. Every project becomes its own native app."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: 12; color: Theme.muted }
                        Item { Layout.fillHeight: true }
                        FlatButton { text: "Create your first project"; tone: "lime"; onClicked: root.createRequested() }
                    }
                }
            }
        }
    }
}
