import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: chat
    color: "white"; radius: 16
    signal sendRequested(string text)
    property var proposal: Backend.project.proposal || ({})
    property bool hasProposal: !!proposal.id
    property bool accepted: hasProposal && proposal.accepted.indexOf(Backend.author) !== -1
    property bool contributor: hasProposal && proposal.authors.indexOf(Backend.author) !== -1
    function focusComposer() { composer.forceActiveFocus() }
    function send() {
        const text = composer.text.trim()
        if (!text) return
        composer.clear()
        sendRequested(text)
    }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 20; spacing: 16
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 4
                Text { text: "Together"; font.pointSize: 14; font.weight: Font.DemiBold; color: Theme.ink }
                Text { text: "The conversation shapes the app."; color: Theme.muted; font.pointSize: 10.5 }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                width: 32; height: 32; radius: 10; color: Theme.lime
                Text { anchors.centerIn: parent; text: "c"; color: Theme.ink; font.pointSize: 17; font.weight: Font.DemiBold }
                ToolTip.visible: agentHover.hovered
                ToolTip.text: Backend.agentAvailable ? "Agent executable available" : "Install and sign in to omp to connect the agent"
                HoverHandler { id: agentHover }
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
        ListView {
            id: messages
            objectName: "chatMessages"
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true; spacing: 24
            model: Backend.project.messages || []
            ScrollBar.vertical: ScrollBar {}
            onCountChanged: Qt.callLater(function() { messages.positionViewAtEnd() })
            delegate: Item {
                required property var modelData
                width: messages.width
                height: messageColumn.implicitHeight
                ColumnLayout {
                    id: messageColumn
                    width: parent.width; spacing: 8
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        Rectangle {
                            width: 26; height: 26; radius: 8
                            color: modelData.kind === "human" ? "#e7ede3" : Theme.lime
                            Text { anchors.centerIn: parent; text: modelData.author.substring(0, 1).toUpperCase(); color: Theme.ink; font.pointSize: 9; font.weight: Font.DemiBold }
                        }
                        Text { text: modelData.kind === "human" ? modelData.author : "@" + modelData.author; color: Theme.ink; font.pointSize: 10.5; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                        Text { text: Qt.formatTime(new Date(modelData.time), "hh:mm"); color: Theme.muted; font.pointSize: 9 }
                    }
                    TextEdit {
                        text: modelData.text
                        Layout.fillWidth: true
                        Layout.preferredHeight: contentHeight
                        readOnly: true; selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        textFormat: TextEdit.PlainText
                        font.pointSize: 12.5
                        color: modelData.kind === "system" ? Theme.muted : Theme.ink
                        selectionColor: "#d9e4ff"
                    }
                    Text { visible: modelData.revision < Backend.project.revision; text: "Discussed on V" + modelData.revision; font.pointSize: 9; color: Theme.muted }
                }
            }
            ColumnLayout {
                visible: messages.count === 0
                width: parent.width
                anchors.verticalCenter: parent.verticalCenter
                spacing: 14
                Text { text: "Start with a conversation."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: 18; font.weight: Font.DemiBold; color: Theme.ink }
                Text { text: "Talk to each other here. When you’re ready for help, mention @" + Backend.project.agentName + "."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: 12.5; color: Theme.muted }
                Text { text: "Sketch on the canvas or point with Comment. Your marks accompany the next request to the agent."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: 12.5; color: Theme.muted }
                Text { visible: !Backend.agentAvailable; text: "The agent needs omp installed and signed in. Project creation, chat and drawing work without it."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: 10.5; color: Theme.muted }
            }
        }
        Rectangle {
            visible: Backend.agentBusy
            Layout.fillWidth: true; implicitHeight: busyRow.implicitHeight + 20
            color: Theme.ice; radius: 10
            RowLayout {
                id: busyRow
                anchors.fill: parent; anchors.margins: 10
                Text { text: "@" + Backend.project.agentName + " is working…"; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: 10.5; color: Theme.muted }
                FlatButton { text: "Stop"; tone: "plain"; onClicked: Backend.cancelAgent() }
            }
        }
        Rectangle {
            visible: chat.hasProposal
            Layout.fillWidth: true
            implicitHeight: proposalColumn.implicitHeight + 28
            color: "#f3f7e8"; radius: 12
            ColumnLayout {
                id: proposalColumn
                anchors.fill: parent; anchors.margins: 14; spacing: 10
                Text { text: "A direction to agree on"; font.pointSize: 11; font.weight: Font.DemiBold; color: Theme.ink }
                Text { text: chat.hasProposal ? chat.proposal.authors.map(function(name) { return (chat.proposal.accepted.indexOf(name) !== -1 ? "✓ " : "○ ") + name }).join("   ") : ""; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: 10.5; color: Theme.muted }
                FlatButton { text: chat.accepted ? "Waiting for everyone" : "Agree & build"; tone: "dark"; enabled: chat.contributor && !chat.accepted && !Backend.agentBusy; Layout.fillWidth: true; onClicked: Backend.acceptProposal() }
                Text { text: "More discussion updates the proposal before anything changes."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pointSize: 9.5 }
            }
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Math.min(180, Math.max(100, composer.contentHeight + 60))
            color: Theme.ice; radius: 12
            border.width: 1; border.color: composer.activeFocus ? "#bdc7b6" : Theme.line
            ScrollView {
                anchors.fill: parent; anchors.margins: 12; anchors.bottomMargin: 43
                TextArea {
                    id: composer
                    objectName: "chatComposer"
                    placeholderText: "Message, or ask @" + Backend.project.agentName
                    font.pointSize: 12.5
                    color: Theme.ink
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    background: null
                    padding: 0
                    Keys.onReturnPressed: function(event) { if (!(event.modifiers & Qt.ShiftModifier)) { chat.send(); event.accepted = true } else event.accepted = false }
                    Keys.onEnterPressed: function(event) { if (!(event.modifiers & Qt.ShiftModifier)) { chat.send(); event.accepted = true } else event.accepted = false }
                }
            }
            RowLayout {
                anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                anchors.margins: 8
                FlatButton { text: "@" + Backend.project.agentName; tone: "plain"; implicitHeight: 30; font.pointSize: 9.5; onClicked: { composer.insert(composer.cursorPosition, "@" + Backend.project.agentName + " "); composer.forceActiveFocus() } }
                Item { Layout.fillWidth: true }
                FlatButton { text: "↑"; implicitWidth: 30; implicitHeight: 30; tone: "dark"; enabled: composer.text.trim().length > 0; onClicked: chat.send(); Accessible.name: "Send message" }
            }
        }
        Text { text: "Chatting as " + Backend.author + " · Shift + Enter for a new line"; font.pointSize: 9; color: Theme.muted; Layout.alignment: Qt.AlignHCenter }
    }
}
