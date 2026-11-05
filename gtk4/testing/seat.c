/* Disposable CI input seat. Uses one fixed US keymap for the entire test. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <wayland-client.h>
#include <xkbcommon/xkbcommon.h>
#include "virtual-pointer-client-protocol.h"
#include "virtual-keyboard-client-protocol.h"

static struct wl_seat *seat;
static struct zwlr_virtual_pointer_manager_v1 *pointer_manager;
static struct zwp_virtual_keyboard_manager_v1 *keyboard_manager;
static void capabilities(void *data, struct wl_seat *object, uint32_t caps) {}
static void seat_name(void *data, struct wl_seat *object, const char *name) {}
static const struct wl_seat_listener seat_listener = {capabilities, seat_name};
static void global(void *data, struct wl_registry *registry, uint32_t name,
                   const char *interface, uint32_t version) {
    if (!strcmp(interface, "wl_seat") && !seat) {
        seat = wl_registry_bind(registry, name, &wl_seat_interface, 2);
        wl_seat_add_listener(seat, &seat_listener, NULL);
    } else if (!strcmp(interface, "zwlr_virtual_pointer_manager_v1")) {
        pointer_manager = wl_registry_bind(registry, name, &zwlr_virtual_pointer_manager_v1_interface, 1);
    } else if (!strcmp(interface, "zwp_virtual_keyboard_manager_v1")) {
        keyboard_manager = wl_registry_bind(registry, name, &zwp_virtual_keyboard_manager_v1_interface, 1);
    }
}
static void removed(void *data, struct wl_registry *registry, uint32_t name) {}
static const struct wl_registry_listener registry_listener = {global, removed};
static uint32_t timestamp(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (uint32_t)(now.tv_sec * 1000 + now.tv_nsec / 1000000);
}
static uint32_t modifier(struct xkb_keymap *map, const char *name) {
    xkb_mod_index_t index = xkb_keymap_mod_get_index(map, name);
    return index == XKB_MOD_INVALID ? 0 : 1u << index;
}
static int key(struct wl_display *display, struct zwp_virtual_keyboard_v1 *keyboard,
               struct xkb_keymap *map, xkb_keysym_t symbol, uint32_t mods) {
    for (xkb_keycode_t code = xkb_keymap_min_keycode(map); code <= xkb_keymap_max_keycode(map); ++code) {
        for (xkb_level_index_t level = 0; level < 2; ++level) {
            const xkb_keysym_t *symbols;
            int count = xkb_keymap_key_get_syms_by_level(map, code, 0, level, &symbols);
            if (count != 1 || symbols[0] != symbol) continue;
            uint32_t mask = mods | (level ? modifier(map, XKB_MOD_NAME_SHIFT) : 0);
            zwp_virtual_keyboard_v1_modifiers(keyboard, mask, 0, 0, 0);
            wl_display_roundtrip(display);
            zwp_virtual_keyboard_v1_key(keyboard, timestamp(), code - 8, WL_KEYBOARD_KEY_STATE_PRESSED);
            wl_display_roundtrip(display);
            usleep(12000);
            zwp_virtual_keyboard_v1_key(keyboard, timestamp(), code - 8, WL_KEYBOARD_KEY_STATE_RELEASED);
            zwp_virtual_keyboard_v1_modifiers(keyboard, 0, 0, 0, 0);
            wl_display_roundtrip(display);
            return 0;
        }
    }
    return -1;
}
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) return 1;
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    if (wl_display_roundtrip(display) < 0 || !seat || !pointer_manager || !keyboard_manager) return 1;
    struct zwlr_virtual_pointer_v1 *pointer = zwlr_virtual_pointer_manager_v1_create_virtual_pointer(pointer_manager, seat);
    struct zwp_virtual_keyboard_v1 *keyboard = zwp_virtual_keyboard_manager_v1_create_virtual_keyboard(keyboard_manager, seat);
    struct xkb_context *context = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
    struct xkb_rule_names names = {.layout = "us"};
    struct xkb_keymap *map = xkb_keymap_new_from_names(context, &names, XKB_KEYMAP_COMPILE_NO_FLAGS);
    if (!map) return 1;
    char *text = xkb_keymap_get_as_string(map, XKB_KEYMAP_FORMAT_TEXT_V1);
    size_t size = strlen(text) + 1;
    int fd = memfd_create("centaur-test-keymap", 0);
    if (fd < 0 || ftruncate(fd, size) < 0 || write(fd, text, size) != (ssize_t)size) return 1;
    zwp_virtual_keyboard_v1_keymap(keyboard, WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1, fd, size);
    if (wl_display_roundtrip(display) < 0) return 1;
    close(fd);
    free(text);
    int server = socket(AF_UNIX, SOCK_STREAM, 0);
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    if (strlen(argv[1]) >= sizeof(address.sun_path)) return 1;
    strcpy(address.sun_path, argv[1]);
    if (bind(server, (struct sockaddr *)&address, sizeof(address)) < 0 || listen(server, 4) < 0) return 1;
    puts("Persistent test keyboard and pointer attached");
    fflush(stdout);
    for (;;) {
        int client = accept(server, NULL, NULL);
        if (client < 0) break;
        char request[4096];
        size_t length = 0;
        ssize_t count;
        while (length < sizeof(request) - 1 && (count = read(client, request + length, sizeof(request) - 1 - length)) > 0)
            length += count;
        request[length] = 0;
        int failed = 0;
        if (!strncmp(request, "text ", 5)) {
            for (unsigned char *c = (unsigned char *)request + 5; *c && !failed; ++c)
                failed = key(display, keyboard, map, xkb_utf32_to_keysym(*c), 0);
        } else if (!strncmp(request, "key ", 4)) {
            char *name = request + 4;
            uint32_t mods = 0;
            while (!strncmp(name, "ctrl+", 5)) { mods |= modifier(map, XKB_MOD_NAME_CTRL); name += 5; }
            failed = key(display, keyboard, map, xkb_keysym_from_name(name, XKB_KEYSYM_NO_FLAGS), mods);
        } else if (!strcmp(request, "scroll up") || !strcmp(request, "scroll down")) {
            int direction = !strcmp(request, "scroll up") ? -1 : 1;
            zwlr_virtual_pointer_v1_axis_source(pointer, WL_POINTER_AXIS_SOURCE_WHEEL);
            zwlr_virtual_pointer_v1_axis_discrete(pointer, timestamp(), WL_POINTER_AXIS_VERTICAL_SCROLL,
                                                 wl_fixed_from_double(direction * 15.0), direction);
            zwlr_virtual_pointer_v1_frame(pointer);
            failed = wl_display_roundtrip(display) < 0;
        } else failed = 1;
        if (write(client, failed ? "error" : "ok", failed ? 5 : 2) < 0) return 1;
        close(client);
    }
    return 0;
}
