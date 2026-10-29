import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Centaur.Native 1.0

Rectangle {
    id: sidebar
    property string page: "projects"
    property bool compact: false
    property real bottomCornerRadius: 0
    bottomLeftRadius: bottomCornerRadius
    signal navigate(string destination)
    color: Theme.ice
    implicitWidth: compact ? 72 : 216
    BrandMark { x: sidebar.compact ? 20 : 24; y: 24; onClicked: sidebar.navigate("projects") }
    Column {
        x: 8; y: 104; width: parent.width - 16
        Repeater {
            model: [ { key: "projects", label: "Projects", icon: "project-icon-default.svg" },
                     { key: "designSystems", label: "Design Systems", icon: "ds-icon-default.svg" },
                     { key: "settings", label: "Settings", icon: "settings-icon-default.svg" } ]
            delegate: Button {
                id: entry
                required property var modelData
                objectName: "nav-" + modelData.key
                readonly property bool selected: sidebar.page === modelData.key
                readonly property color foreground: selected ? Theme.ink : hovered || visualFocus ? Theme.hover : Theme.muted
                width: parent.width; height: 40
                hoverEnabled: true
                leftPadding: 8; rightPadding: 8
                background: Rectangle { radius: 8; color: entry.selected ? "#f3f3f3" : "transparent"
                    Rectangle { anchors.fill: parent; anchors.margins: -5; radius: 13; color: "transparent"; border.width: 2; border.color: Theme.blue; visible: entry.visualFocus }
                }
                contentItem: RowLayout {
                    spacing: 8
                    SvgIcon { source: "qrc:/assets/dialogue/" + entry.modelData.icon; color: entry.foreground; Layout.preferredWidth: 32; Layout.preferredHeight: 32 }
                    Text { visible: !sidebar.compact; text: entry.modelData.label; color: entry.foreground; readonly property real typeSize: 14; font.pixelSize: typeSize; font.family: Theme.familyForSize(-1, typeSize); font.weight: Font.DemiBold; Layout.fillWidth: true }
                }
                onClicked: sidebar.navigate(modelData.key)
                Accessible.name: modelData.label
                Accessible.checkable: true
                Accessible.checked: selected
                ToolTip.visible: sidebar.compact && hovered
                ToolTip.text: modelData.label
            }
        }
    }
    Button {
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: 88; leftPadding: sidebar.compact ? 16 : 24; rightPadding: 16
        hoverEnabled: true
        background: Rectangle { color: "transparent"; border.width: parent.visualFocus ? 2 : 0; border.color: Theme.blue; radius: 8 }
        contentItem: RowLayout {
            spacing: 12
            Rectangle { Layout.preferredWidth: 40; Layout.preferredHeight: 40; radius: 10; color: "#669e68"; Text { anchors.centerIn: parent; text: Backend.author.slice(0,1).toUpperCase(); color: "#102010"; readonly property real typeSize: 12; font.pixelSize: typeSize; font.family: Theme.familyForSize(-1, typeSize); font.weight: Font.Bold } }
            ColumnLayout { visible: !sidebar.compact; spacing: 2; Layout.fillWidth: true
                Text { text: Backend.author; color: Theme.ink; readonly property real typeSize: 14; font.pixelSize: typeSize; font.family: Theme.familyForSize(-1, typeSize); font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                Text { text: "This device"; color: Theme.muted; readonly property real typeSize: 12; font.pixelSize: typeSize; font.family: Theme.familyForSize(-1, typeSize); }
            }
        }
        onClicked: sidebar.navigate("settings")
        Accessible.name: "Your settings"
    }
}
