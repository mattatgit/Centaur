import QtQuick
import QtQuick.Layouts

Rectangle {
    color: "white"; radius: 16
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(360, parent.width - 48)
        spacing: 16
        Image { objectName: "designSystemEmptyArt"; source: "qrc:/assets/dialogue/design-system-empty-suitcase.png"; Layout.preferredWidth: 176; Layout.preferredHeight: 176; Layout.alignment: Qt.AlignHCenter; fillMode: Image.PreserveAspectFit }
        Text { text: "No design systems added yet"; color: Theme.muted; readonly property real typeSize: 14; font.pixelSize: typeSize; font.family: Theme.familyForSize(-1, typeSize); horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true; wrapMode: Text.Wrap }
        Text { text: "Design-system import is not available yet."; color: Theme.muted; readonly property real typeSize: 12; font.pixelSize: typeSize; font.family: Theme.familyForSize(-1, typeSize); horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
}
