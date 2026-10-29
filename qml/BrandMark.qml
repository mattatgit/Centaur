import QtQuick
import QtQuick.Controls
import Centaur.Native 1.0

Button {
    implicitWidth: 32; implicitHeight: 32
    hoverEnabled: true
    scale: hovered ? 1.1 : 1
    Behavior on scale { NumberAnimation { duration: 100 } }
    leftPadding: 0; rightPadding: 0; topPadding: 0; bottomPadding: 0
    background: Rectangle { radius: 10; color: "transparent"; border.width: parent.visualFocus ? 2 : 0; border.color: Theme.blue }
    contentItem: SvgIcon {
        source: "qrc:/brand/centaur.svg"
    }
    Accessible.name: "Centaur projects"
}
