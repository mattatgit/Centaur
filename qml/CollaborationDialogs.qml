import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: collaboration
    objectName: "collaborationDialogs"
    function openInvite() { inviteAddress.text = Backend.localAddress; localOnly.checked = false; inviteDialog.open() }
    function openJoin() { joinName.text = Backend.author; joinDialog.open() }
    Connections { target: Backend; function onJoined() { joinDialog.close(); invitationInput.clear() } }
    Dialog {
        id: inviteDialog
        objectName: "invitePeopleDialog"
        parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(500, parent.width - 32); padding: 24; modal: true
        background: Rectangle { color: "white"; radius: 16; border.color: Theme.dust }
        header: Label { text: "Invite people"; font.pixelSize: 16; font.weight: Font.DemiBold; color: Theme.ink; padding: 24; bottomPadding: 0 }
        ColumnLayout {
            width: parent.width; spacing: 16
            Text { text: "Invite people nearby or on another network. Keep this computer awake; sharing continues when you close its Centaur window."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 14; color: Theme.ink }
            CheckBox { id: localOnly; text: "Local network only"; enabled: !Backend.inviting; Accessible.name: "Local network only" }
            Text { visible: localOnly.checked; text: "This computer’s reachable address"; font.pixelSize: 12; color: Theme.muted }
            TextField { visible: localOnly.checked; id: inviteAddress; objectName: "inviteAddress"; Layout.fillWidth: true; placeholderText: "192.168.1.10"; Accessible.name: "Host address" }
            FlatButton { text: Backend.inviting ? "Preparing invitation…" : "Create invitation"; tone: "dark"; enabled: !Backend.inviting && (!localOnly.checked || inviteAddress.text.trim().length > 0) && Backend.canContribute; onClicked: Backend.invitePeople(localOnly.checked ? inviteAddress.text : "iroh") }
            Text { visible: Backend.invitationCode.length > 0; text: "Send this code to one person. It can be used once and expires in 20 minutes."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.muted }
            ScrollView {
                visible: Backend.invitationCode.length > 0
                Layout.fillWidth: true; Layout.preferredHeight: 100
                TextArea { text: Backend.invitationCode; readOnly: true; selectByMouse: true; wrapMode: TextEdit.WrapAnywhere; font.pixelSize: 12; Accessible.name: "Invitation code" }
            }
            FlatButton { visible: Backend.invitationCode.length > 0; text: "Copy invitation"; onClicked: Backend.copyInvitation() }
            Text { visible: !!Backend.project.sharing && Backend.project.sharing.members.length > 0; text: "Members: " + ((Backend.project.sharing || {}).members || []).join(", "); Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.muted }
            RowLayout {
                Layout.fillWidth: true
                FlatButton { visible: !!Backend.project.sharing && Backend.project.sharing.enabled; text: "Stop sharing"; onClicked: { Backend.stopSharing(); inviteDialog.close() } }
                Item { Layout.fillWidth: true }
                FlatButton { text: "Done"; tone: "plain"; onClicked: inviteDialog.close() }
            }
        }
    }
    Dialog {
        id: joinDialog
        objectName: "joinProjectDialog"
        parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(480, parent.width - 32); padding: 24; modal: true
        background: Rectangle { color: "white"; radius: 16; border.color: Theme.dust }
        header: Label { text: "Join a project"; font.pixelSize: 16; font.weight: Font.DemiBold; color: Theme.ink; padding: 24; bottomPadding: 0 }
        onRejected: Backend.cancelJoin()
        ColumnLayout {
            width: parent.width; spacing: 16
            TextField { id: joinName; objectName: "joinName"; Layout.fillWidth: true; placeholderText: "Your name"; maximumLength: 50; enabled: !Backend.joining; Accessible.name: "Your name" }
            ScrollView { Layout.fillWidth: true; Layout.preferredHeight: 100
                TextArea { id: invitationInput; objectName: "joinInvitation"; placeholderText: "Paste the invitation code"; wrapMode: TextEdit.WrapAnywhere; selectByMouse: true; enabled: !Backend.joining; font.pixelSize: 12; Accessible.name: "Invitation code" }
            }
            Text { text: "Only join people you trust. The shared native app runs on this device. You don’t need to set up OMP to participate."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.muted }
            Text { text: Backend.joinStatus; visible: text.length > 0; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.muted }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                FlatButton { text: "Cancel"; tone: "plain"; onClicked: { Backend.cancelJoin(); joinDialog.close() } }
                FlatButton { text: Backend.joining ? "Connecting…" : "Join project"; tone: "dark"; enabled: !Backend.joining && joinName.text.trim().length > 0 && invitationInput.text.trim().length > 0; onClicked: Backend.joinProject(invitationInput.text, joinName.text) }
            }
        }
    }
}
