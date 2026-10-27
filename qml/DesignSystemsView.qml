import QtQuick
import QtQuick.Layouts

Rectangle {
    color: "white"; radius: 16
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(360, parent.width - 48)
        spacing: 16
        Image { objectName: "designSystemEmptyArt"; source: "qrc:/assets/dialogue/design-system-empty-suitcase.png"; Layout.preferredWidth: 176; Layout.preferredHeight: 176; Layout.alignment: Qt.AlignHCenter; fillMode: Image.PreserveAspectFit }
        Text { text: "No design systems added yet"; color: Theme.muted; font.pixelSize: 14; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true; wrapMode: Text.Wrap }
        Text { text: "Design-system import is not available yet."; color: Theme.muted; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
}
