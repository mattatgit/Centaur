/* Disposable CI seat fixture. Keeps one virtual pointer attached to headless Sway. */
#include <stdio.h>
#include <string.h>
#include <wayland-client.h>
#include "virtual-pointer-client-protocol.h"

static struct wl_seat *seat;
static struct zwlr_virtual_pointer_manager_v1 *manager;
static void capabilities(void *data, struct wl_seat *object, uint32_t caps) {}
static void seat_name(void *data, struct wl_seat *object, const char *name) {}
static const struct wl_seat_listener seat_listener = {capabilities, seat_name};
static void global(void *data, struct wl_registry *registry, uint32_t name,
                   const char *interface, uint32_t version) {
    if (!strcmp(interface, "wl_seat") && !seat) {
        seat = wl_registry_bind(registry, name, &wl_seat_interface, 2);
        wl_seat_add_listener(seat, &seat_listener, NULL);
    } else if (!strcmp(interface, "zwlr_virtual_pointer_manager_v1")) {
        manager = wl_registry_bind(registry, name, &zwlr_virtual_pointer_manager_v1_interface, 1);
    }
}
static void removed(void *data, struct wl_registry *registry, uint32_t name) {}
static const struct wl_registry_listener registry_listener = {global, removed};
int main(void) {
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) { fputs("Cannot connect to disposable display\n", stderr); return 1; }
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    if (wl_display_roundtrip(display) < 0 || !seat || !manager) {
        fputs("Disposable compositor has no seat/virtual pointer protocol\n", stderr);
        return 1;
    }
    zwlr_virtual_pointer_manager_v1_create_virtual_pointer(manager, seat);
    if (wl_display_roundtrip(display) < 0) return 1;
    puts("Persistent test pointer attached");
    fflush(stdout);
    while (wl_display_dispatch(display) != -1) {}
    wl_display_disconnect(display);
    return 0;
}
