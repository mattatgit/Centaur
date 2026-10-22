import QtQuick
import QtQuick.Controls

Button {
    id: control
    property string tone: "soft"
    implicitHeight: 38
    implicitWidth: Math.max(38, label.implicitWidth + 28)
    leftPadding: 14
    rightPadding: 14
    hoverEnabled: true
    font.pointSize: 10.5
    font.weight: Font.DemiBold
    opacity: enabled ? 1 : 0.4
    contentItem: Text {
        id: label
        text: control.text
        font: control.font
        color: control.checked || control.tone === "dark" ? "white" : Theme.ink
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: 10
        color: control.checked || control.tone === "dark" ? Theme.ink
            : control.tone === "lime" ? Theme.lime
            : control.tone === "plain" ? (control.hovered ? "#efefed" : "transparent")
            : control.hovered ? "#e9ebe6" : Theme.ice
        border.width: control.activeFocus ? 2 : 0
        border.color: Theme.blue
    }
    ToolTip.visible: hovered && ToolTip.text.length > 0
    Accessible.name: text
}
