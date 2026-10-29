import QtQuick
import QtQuick.Layouts

Rectangle {
    color: "white"
    ColumnLayout {
        anchors.centerIn: parent; width: parent.width - 80; spacing: 18
        Text { text: "Your native app lives here."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.ink; readonly property real typeSize: 22; font.pointSize: typeSize; font.family: Theme.familyForSize(typeSize, -1); font.weight: Font.DemiBold }
        Text { text: "Embedded app previews run on NixOS / Linux. This macOS build lets us work on the native interface, conversation and drawings."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; readonly property real typeSize: 12.5; font.pointSize: typeSize; font.family: Theme.familyForSize(typeSize, -1); }
        Text { text: "Your project already contains a real Qt Quick starter app."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; readonly property real typeSize: 12.5; font.pointSize: typeSize; font.family: Theme.familyForSize(typeSize, -1); }
    }
}
