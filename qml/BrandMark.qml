import QtQuick
import QtQuick.Controls

Button {
    implicitWidth: 32; implicitHeight: 32
    hoverEnabled: true
    scale: hovered ? 1.1 : 1
    Behavior on scale { NumberAnimation { duration: 100 } }
    background: Rectangle { radius: 10; color: Theme.ink; border.width: parent.visualFocus ? 2 : 0; border.color: Theme.blue }
    contentItem: Item {
        Grid { anchors.centerIn: parent; columns: 2; spacing: 3
            Repeater { model: 4; Rectangle { width: 4; height: 4; radius: 2; color: "white" } }
        }
    }
    Accessible.name: "Centaur projects"
}
