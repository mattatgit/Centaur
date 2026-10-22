import QtQuick
import QtQuick.Layouts

Rectangle {
    color: "white"
    ColumnLayout {
        anchors.centerIn: parent; width: parent.width - 80; spacing: 18
        Text { text: "Your native app lives here."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.ink; font.pointSize: 22; font.weight: Font.DemiBold }
        Text { text: "Embedded app previews run on NixOS / Linux. This macOS build lets us work on the native interface, conversation and drawings."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pointSize: 12.5 }
        Text { text: "Your project already contains a real Qt Quick starter app."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pointSize: 12.5 }
    }
}
