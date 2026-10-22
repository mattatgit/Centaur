import QtQuick
import QtQuick.Window
import QtWayland.Compositor
import QtWayland.Compositor.XdgShell

Item {
    id: host
    objectName: "waylandHost"
    clip: true
    property bool disposing: false
    ListModel { id: clients }
    WaylandCompositor {
        id: compositor
        socketName: Backend.socketName
        onCreatedChanged: if (created) Qt.callLater(function() { Backend.startPreview() })
        XdgShell {
            onToplevelCreated: function(toplevel, xdgSurface) {
                toplevel.sendUnmaximized(Qt.size(host.width, host.height))
                clients.append({ shell: xdgSurface, clientToplevel: toplevel })
                host.updateSurfaceCount()
            }
        }
        WaylandOutput {
            window: host.Window.window
            sizeFollowsWindow: true
        }
    }
    Repeater {
        model: clients
        delegate: ShellSurfaceItem {
            required property var shell
            required property var clientToplevel
            required property int index
            objectName: "embeddedClient"
            shellSurface: shell
            autoCreatePopupItems: true
            onSurfaceDestroyed: if (!host.disposing) { clients.remove(index); host.updateSurfaceCount() }
            onWidthChanged: if (width > 0) host.configureClients()
            Component.onCompleted: takeFocus()
            Connections {
                target: shell ? shell.surface : null
                function onHasContentChanged() { host.updateSurfaceCount() }
            }
        }
    }
    function configureClients() {
        if (disposing) return
        for (let i = 0; i < clients.count; ++i)
            if (clients.get(i).clientToplevel) clients.get(i).clientToplevel.sendUnmaximized(Qt.size(host.width, host.height))
    }
    function updateSurfaceCount() {
        if (disposing) return
        let count = 0
        for (let i = 0; i < clients.count; ++i) {
            const shell = clients.get(i).shell
            const surface = shell ? shell.surface : null
            if (surface && surface.hasContent) ++count
        }
        Backend.surfaceCount = count
    }
    onWidthChanged: configureClients()
    onHeightChanged: configureClients()
    Component.onCompleted: if (compositor.created) Backend.startPreview()
    Connections {
        target: Backend
        function onPreviewStopping() {
            host.disposing = true
            clients.clear()
            Backend.surfaceCount = 0
            host.disposing = false
        }
    }
    Component.onDestruction: disposing = true
}
