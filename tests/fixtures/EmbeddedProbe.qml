import QtQuick

Rectangle {
    width: 520; height: 640
    color: "#ccff00"
    Text { anchors.centerIn: parent; text: "Separate native client"; color: "#171717"; font.pixelSize: 24 }
    MouseArea { anchors.fill: parent; onClicked: console.log("CENTAUR_INPUT_OK") }
}
