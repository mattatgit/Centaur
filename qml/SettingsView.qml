import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs as NativeDialogs

Rectangle {
    id: settings
    color: "white"; radius: 16
    signal returnToApp()
    Dialog { id: archiveDialog; title: "Archive this project?"; modal: true; anchors.centerIn: parent; width: Math.min(420, settings.width - 32); standardButtons: Dialog.Yes | Dialog.Cancel
        Label { width: parent.width; text: "Your app and conversation stay saved in the project folder."; wrapMode: Text.Wrap }
        onAccepted: Backend.archiveProject(Backend.projectId)
    }
    NativeDialogs.ColorDialog { id: gridColorDialog; title: "Grid colour"; selectedColor: Backend.gridColor; onAccepted: Backend.gridColor = selectedColor }
    ScrollView {
        id: settingsScroll
        anchors.fill: parent
        anchors.margins: settings.width < 600 ? 24 : 40
        contentWidth: availableWidth
        ColumnLayout {
            width: Math.min(640, settingsScroll.availableWidth); spacing: 24
            ColumnLayout {
                Layout.fillWidth: true; spacing: 14
                Text { text: "Your space"; font.pixelSize: 16; font.weight: Font.DemiBold; color: Theme.ink }
                Text { text: "Your name"; font.pixelSize: 14; color: Theme.ink }
                TextField { id: authorField; objectName: "settingsAuthor"; text: Backend.author; Layout.fillWidth: true; maximumLength: 50; onEditingFinished: if (text.trim()) Backend.author = text }
                Text { text: "People in this conversation see this name."; font.pixelSize: 12; color: Theme.muted }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.dust }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 14
                Text { text: "Agent"; font.pixelSize: 16; font.weight: Font.DemiBold; color: Theme.ink }
                Text { text: Backend.agentAvailable ? "OMP is available" : "OMP is not connected"; font.pixelSize: 14; color: Theme.ink }
                Text { text: Backend.agentExecutable || "Launch Centaur with your OMP executable configured."; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; font.pixelSize: 12; color: Theme.muted }
                Text { text: Backend.agentModel || "The model is reported after an agent request."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.muted }
                Text { text: "Sign in and select a model in OMP. Credentials stay with the agent on this device."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.muted }
                Text { visible: !!Backend.projectId; text: "Address this project's agent as"; font.pixelSize: 14; color: Theme.ink }
                TextField { visible: !!Backend.projectId; text: Backend.project.agentName || "centaur"; Layout.fillWidth: true; maximumLength: 30; onEditingFinished: if (text.trim()) Backend.renameAgent(text) }
                RowLayout { visible: !!Backend.projectId; Layout.fillWidth: true
                    FlatButton { text: "Open repo"; onClicked: Backend.revealProject() }
                    FlatButton { text: "Restart app"; iconSource: "qrc:/assets/dialogue/reload.svg"; enabled: Backend.embeddingSupported; onClicked: Backend.restartPreview() }
                    FlatButton { text: "Archive"; onClicked: archiveDialog.open() }
                }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.dust }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 14
                Text { text: "Grid"; font.pixelSize: 16; font.weight: Font.DemiBold; color: Theme.ink }
                RowLayout { Layout.fillWidth: true
                    Text { text: "Show grid"; color: Theme.ink; font.pixelSize: 14; Layout.fillWidth: true }
                    Switch { checked: Backend.gridEnabled; onToggled: Backend.gridEnabled = checked; Accessible.name: "Show grid" }
                }
                RowLayout { Layout.fillWidth: true
                    Text { text: "Grid colour"; color: Theme.ink; font.pixelSize: 14; Layout.fillWidth: true }
                    Button { implicitWidth: 112; implicitHeight: 32; onClicked: gridColorDialog.open(); Accessible.name: "Grid colour"
                        background: Rectangle { radius: 8; color: Theme.ice }
                        contentItem: RowLayout { spacing: 8
                            Rectangle { width: 16; height: 16; color: Backend.gridColor; border.width: 1; border.color: Theme.line }
                            Text { text: Backend.gridColor.toString().toUpperCase(); font.pixelSize: 11; color: Theme.ink }
                        }
                    }
                }
                RowLayout { Layout.fillWidth: true
                    Text { text: "Grid point size"; color: Theme.ink; font.pixelSize: 14; Layout.fillWidth: true }
                    SpinBox { objectName: "gridSizeSetting"; from: 2; to: 64; value: Backend.gridSize; editable: true; onValueModified: Backend.gridSize = value; Accessible.name: "Grid point size" }
                    Text { text: "pt"; font.pixelSize: 12; color: Theme.muted }
                }
                RowLayout { Layout.fillWidth: true
                    Text { text: "Grid opacity"; color: Theme.ink; font.pixelSize: 14; Layout.fillWidth: true }
                    ComboBox { objectName: "gridOpacitySetting"; model: ["0%","10%","20%","30%","40%","50%","60%","70%","80%","90%","100%"]
                        currentIndex: Math.round(Backend.gridOpacity / 10); onActivated: Backend.gridOpacity = currentIndex * 10; Accessible.name: "Grid opacity" }
                }
                Text { text: "Saved on this device. The grid is aligned with the native app."; font.pixelSize: 12; color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.dust }
            ColumnLayout { Layout.fillWidth: true; spacing: 14
                Text { text: "Collaboration and storage"; font.pixelSize: 16; font.weight: Font.DemiBold; color: Theme.ink }
                Text { text: "Multiple windows can share a session under the same OS user and data folder. Joining from another computer is not available yet."; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Text { text: Backend.dataRoot; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                FlatButton { text: "Open data folder"; onClicked: Backend.revealData() }
                FlatButton { visible: !!Backend.projectId; text: "Back to app"; onClicked: settings.returnToApp() }
                Text { text: "Centaur v" + Qt.application.version; color: Theme.muted; font.pixelSize: 12 }
            }
        }
    }
}
