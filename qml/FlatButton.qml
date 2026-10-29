import QtQuick
import QtQuick.Controls
import Centaur.Native 1.0

Button {
    id: control
    property string tone: "soft"
    property url iconSource: ""
    property url hoverIconSource: iconSource
    property url selectedIconSource: iconSource
    property bool scaleOnHover: true
    property int iconSize: 12
    property int iconHeight: iconSize
    property color foreground: checked || tone === "dark" ? "white" : tone === "mode" ? (hovered || visualFocus ? Theme.hover : Theme.muted) : Theme.ink
    readonly property bool hasIcon: iconSource.toString().length > 0
    implicitHeight: 32
    implicitWidth: Math.max(32, label.implicitWidth + (hasIcon ? iconSize + (text.length ? 8 : 0) : 0) + leftPadding + rightPadding)
    leftPadding: text.length === 0 ? 6 : tone === "dark" ? 16 : 8
    rightPadding: leftPadding
    hoverEnabled: true
    readonly property real typeSize: 12; font.pixelSize: typeSize; font.family: Theme.familyForSize(-1, typeSize)
    font.weight: Font.DemiBold
    opacity: enabled ? 1 : 0.45
    scale: enabled && hovered && scaleOnHover && tone !== "mode" ? 1.05 : 1
    Behavior on scale { NumberAnimation { duration: 100; easing.type: Easing.OutQuad } }
    contentItem: Item {
        implicitHeight: Math.max(label.implicitHeight, control.iconHeight)
        Row {
            anchors.centerIn: parent
            spacing: 8
            height: Math.max(label.implicitHeight, control.iconHeight)
            SvgIcon {
                visible: control.hasIcon
                source: control.checked ? control.selectedIconSource : control.hovered || control.visualFocus ? control.hoverIconSource : control.iconSource
                color: control.foreground
                width: control.iconSize; height: control.iconHeight
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                id: label
                visible: control.text.length > 0
                text: control.text; font: control.font; color: control.foreground
                width: Math.max(0, Math.min(implicitWidth, control.availableWidth - (control.hasIcon ? control.iconSize + 8 : 0)))
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
            }
        }
    }
    background: Rectangle {
        radius: 8
        color: control.checked ? (control.tone === "mode" ? "#323232" : Theme.blue)
            : control.tone === "dark" ? Theme.ink : control.tone === "lime" ? Theme.lime
            : control.tone === "plain" || control.tone === "mode" ? "transparent" : Theme.dust
        Rectangle { anchors.fill: parent; anchors.margins: -5; radius: 13; color: "transparent"; border.width: 2; border.color: Theme.blue; visible: control.visualFocus }
        Behavior on color { ColorAnimation { duration: 100 } }
    }
    ToolTip.visible: hovered && ToolTip.text.length > 0
    Accessible.name: text
}
