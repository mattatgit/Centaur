import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Centaur.Native 1.0

ApplicationWindow {
    id: window
    objectName: "centaurWindow"
    visible: true
    width: 1440; height: 940
    minimumWidth: workspaceVisible ? 1000 : 360
    minimumHeight: 680
    title: Backend.projectId ? Backend.project.name + " · Centaur" : "Centaur"
    color: "transparent"
    property bool nativeFrameSquare: false
    readonly property real bottomCornerRadius: visibility === Window.Windowed && !nativeFrameSquare ? 12 : 0
    background: Rectangle {
        color: Theme.ice
        bottomLeftRadius: window.bottomCornerRadius
        bottomRightRadius: window.bottomCornerRadius
    }
    font.family: "Inter"; font.pointSize: 11
    property string page: "projects"
    property bool buildMode: false
    readonly property bool workspaceVisible: !!Backend.projectId && page === "projects"
    property string notification: ""
    property string lastProjectId: ""
    function navigate(destination) {
        if (destination === "projects") Backend.closeProject()
        page = destination
    }
    Connections {
        target: Backend
        function onChanged() {
            if (Backend.projectId !== window.lastProjectId) {
                if (Backend.projectId) window.page = "projects"
                window.lastProjectId = Backend.projectId
            }
        }
        function onError(message) { window.notification = message; noticeTimer.restart() }
    }
    RowLayout {
        anchors.fill: parent; spacing: 0
        SideNavigation {
            visible: !window.workspaceVisible
            compact: window.width < 760
            bottomCornerRadius: window.bottomCornerRadius
            page: window.page
            Layout.preferredWidth: implicitWidth
            Layout.fillHeight: true
            onNavigate: function(destination) { window.navigate(destination) }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            Item {
                Layout.fillWidth: true; Layout.preferredHeight: 80
                RowLayout {
                    anchors.left: parent.left; anchors.leftMargin: window.workspaceVisible ? 24 : 3
                    anchors.verticalCenter: parent.verticalCenter
                    width: window.workspaceVisible ? Math.max(160, (parent.width - 280) / 2 - 48) : Math.max(0, parent.width - headerActions.width - 32)
                    spacing: 5
                    BrandMark { visible: window.workspaceVisible; Layout.rightMargin: 3; onClicked: window.navigate("projects") }
                    FlatButton {
                        visible: window.workspaceVisible; text: "Projects"; tone: "plain"; scaleOnHover: false
                        foreground: hovered || visualFocus ? Theme.ink : Theme.muted
                        onClicked: window.navigate("projects")
                    }
                    SvgIcon { visible: window.workspaceVisible; source: "qrc:/assets/dialogue/breadcrumb-arrow.svg"; color: Theme.muted; Layout.preferredWidth: 18; Layout.preferredHeight: 20 }
                    Text {
                        text: window.workspaceVisible ? Backend.project.name : window.page === "designSystems" ? "Design Systems" : window.page === "settings" ? "Settings" : "Projects"
                        color: Theme.ink; readonly property real typeSize: window.workspaceVisible ? 12 : 16; font.pixelSize: typeSize; font.family: Theme.familyForSize(-1, typeSize); font.weight: Font.DemiBold
                        elide: Text.ElideRight; Layout.fillWidth: true
                    }
                }
                Rectangle {
                    visible: window.workspaceVisible
                    anchors.horizontalCenter: parent.horizontalCenter; anchors.verticalCenter: parent.verticalCenter
                    width: 240; height: 48; radius: 16; color: "white"
                    Row { anchors.centerIn: parent
                        FlatButton { objectName: "interactMode"; width: 112; text: "Interact"; tone: "mode"; scaleOnHover: false; iconHeight: 13
                            iconSource: "qrc:/assets/dialogue/interact-grey.svg"; hoverIconSource: "qrc:/assets/dialogue/interact-hover.svg"; selectedIconSource: "qrc:/assets/dialogue/interact-white.svg"
                            checkable: true; autoExclusive: true; checked: !window.buildMode; onClicked: window.buildMode = false }
                        FlatButton { objectName: "buildMode"; width: 112; text: "Build"; tone: "mode"; scaleOnHover: false
                            iconSource: "qrc:/assets/dialogue/comment-grey.svg"; hoverIconSource: "qrc:/assets/dialogue/comment-hover.svg"; selectedIconSource: "qrc:/assets/dialogue/comment-white.svg"
                            checkable: true; autoExclusive: true; checked: window.buildMode; onClicked: window.buildMode = true }
                    }
                }
                Row {
                    id: headerActions
                    anchors.right: parent.right; anchors.rightMargin: 24; anchors.verticalCenter: parent.verticalCenter
                    spacing: 8
                    FlatButton {
                        visible: window.workspaceVisible || window.page === "projects"
                        text: window.workspaceVisible ? (Backend.remoteProject ? "Shared" : "Invite") : "Join project"
                        enabled: !window.workspaceVisible || !Backend.remoteProject
                        tone: "plain"
                        onClicked: window.workspaceVisible ? collaboration.openInvite() : collaboration.openJoin()
                        ToolTip.text: Backend.connectionStatus
                    }
                    FlatButton {
                        visible: window.workspaceVisible || window.page !== "settings"
                        text: window.workspaceVisible ? "Deploy" : window.page === "designSystems" ? "Import" : window.width < 600 ? "+ New" : "+  New project"
                        tone: window.workspaceVisible ? "soft" : "dark"
                        iconSource: window.workspaceVisible ? "qrc:/assets/dialogue/share.svg" : ""
                        enabled: window.page !== "designSystems" && !Backend.remoteProject
                        onClicked: window.workspaceVisible ? deployDialog.open() : createDialog.open()
                        ToolTip.text: window.page === "designSystems" ? "Design-system import is not available yet" : ""
                    }
                }
            }
            StackLayout {
                id: pages
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.rightMargin: 8; Layout.bottomMargin: 8
                currentIndex: window.page === "designSystems" ? 2 : window.page === "settings" ? 3 : Backend.projectId ? 1 : 0
                Loader { active: pages.currentIndex === 0; sourceComponent: projectsComponent }
                Loader { active: !!Backend.projectId; sourceComponent: workspaceComponent }
                Loader { active: pages.currentIndex === 2; sourceComponent: designSystemsComponent }
                Loader { active: pages.currentIndex === 3; sourceComponent: settingsComponent }
            }
        }
    }
    Component { id: projectsComponent; ProjectsView { onCreateRequested: createDialog.open() } }
    Component { id: workspaceComponent; WorkspaceView { buildMode: window.buildMode; onSettingsRequested: window.page = "settings" } }
    Component { id: designSystemsComponent; DesignSystemsView {} }
    Component { id: settingsComponent; SettingsView { onReturnToApp: window.page = "projects" } }

    CollaborationDialogs { id: collaboration; anchors.fill: parent }
    Dialog {
        id: deployDialog
        title: "Deploy"
        modal: true; anchors.centerIn: parent; width: Math.min(420, window.width - 32)
        standardButtons: Dialog.Ok
        Label { width: parent.width; text: "Deployment is not available yet. This is where you'll install and share your finished app."; wrapMode: Text.Wrap }
    }
    Dialog {
        id: createDialog
        title: "Make something together"
        modal: true; anchors.centerIn: parent
        width: Math.min(460, window.width - 32); padding: 28
        standardButtons: Dialog.NoButton
        background: Rectangle { color: "white"; radius: 20; border.color: Theme.line }
        ColumnLayout {
            width: parent.width; spacing: 16
            Text { text: "One project, one native app."; color: Theme.muted; readonly property real typeSize: 11; font.pointSize: typeSize; font.family: Theme.familyForSize(typeSize, -1); }
            TextField { id: projectName; objectName: "projectName"; placeholderText: "Project name"; Layout.fillWidth: true; maximumLength: 100; readonly property real typeSize: 12; font.pointSize: typeSize; font.family: Theme.familyForSize(typeSize, -1); onAccepted: if (text.trim()) createButton.clicked() }
            TextArea { id: projectDescription; placeholderText: "What would you like to make?"; Layout.fillWidth: true; Layout.preferredHeight: 100; wrapMode: TextEdit.Wrap; readonly property real typeSize: 12; font.pointSize: typeSize; font.family: Theme.familyForSize(typeSize, -1); background: Rectangle { color: Theme.ice; radius: 10 } }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                FlatButton { text: "Cancel"; tone: "plain"; onClicked: createDialog.close() }
                FlatButton { id: createButton; text: "Create project"; tone: "dark"; enabled: projectName.text.trim().length > 0
                    onClicked: { Backend.createProject(projectName.text, projectDescription.text); createDialog.close(); projectName.clear(); projectDescription.clear() } }
            }
        }
        onOpened: projectName.forceActiveFocus()
    }
    Rectangle {
        z: 100; visible: window.notification.length > 0
        anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 24
        width: Math.min(parent.width - 80, notice.implicitWidth + 48); height: notice.implicitHeight + 30
        radius: 12; color: Theme.ink
        Text { id: notice; anchors.fill: parent; anchors.margins: 15; text: window.notification; wrapMode: Text.Wrap; color: "white"; readonly property real typeSize: 11; font.pointSize: typeSize; font.family: Theme.familyForSize(typeSize, -1); }
        TapHandler { onTapped: window.notification = "" }
        Timer { id: noticeTimer; interval: 8000; onTriggered: window.notification = "" }
    }
    // Let the compositor handle the drag, including native snapping and limits.
    MouseArea {
        objectName: "windowResizeCorner"
        anchors.right: parent.right; anchors.bottom: parent.bottom
        width: 20; height: 20; z: 1000
        enabled: window.visibility === Window.Windowed
        hoverEnabled: true
        cursorShape: Qt.SizeFDiagCursor
        acceptedButtons: Qt.LeftButton
        onPressed: function(mouse) { window.startSystemResize(Qt.RightEdge | Qt.BottomEdge) }
    }

}
