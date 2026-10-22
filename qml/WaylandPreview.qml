import QtQuick
import QtQuick.Window
import QtWayland.Compositor
import QtWayland.Compositor.XdgShell

Item {
    id: host
    objectName: "waylandHost"
    clip: true
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
            onSurfaceDestroyed: { clients.remove(index); host.updateSurfaceCount() }
            onWidthChanged: if (width > 0) host.configureClients()
            Component.onCompleted: takeFocus()
            Connections {
                target: shell ? shell.surface : null
                function onHasContentChanged() { host.updateSurfaceCount() }
            }
        }
    }
    function configureClients() {
        for (let i = 0; i < clients.count; ++i)
            clients.get(i).clientToplevel.sendUnmaximized(Qt.size(host.width, host.height))
    }
    function updateSurfaceCount() {
        let count = 0
        for (let i = 0; i < clients.count; ++i) {
            const surface = clients.get(i).shell.surface
            if (surface && surface.hasContent) ++count
        }
        Backend.surfaceCount = count
    }
    onWidthChanged: configureClients()
    onHeightChanged: configureClients()
    Component.onCompleted: if (compositor.created) Backend.startPreview()
    Component.onDestruction: Backend.stopPreview()
}
