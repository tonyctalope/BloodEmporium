/* Persistent Wayland pointer: real input events, including motion for Proton games. */
#include <stdint.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <wayland-client.h>
#include "virtual-pointer-client.h"

static struct zwlr_virtual_pointer_manager_v1 *manager;

static void global(void *data, struct wl_registry *registry, uint32_t name,
                   const char *interface, uint32_t version) {
    (void)data;
    if (!strcmp(interface, zwlr_virtual_pointer_manager_v1_interface.name))
        manager = wl_registry_bind(registry, name, &zwlr_virtual_pointer_manager_v1_interface,
                                   version < 2 ? version : 2);
}

static void removed(void *data, struct wl_registry *registry, uint32_t name) {
    (void)data; (void)registry; (void)name;
}

static uint32_t milliseconds(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (uint32_t)((uint64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000);
}

int main(void) {
    /* A killed worker closes stdout too; still reach EOF cleanup for held buttons. */
    signal(SIGPIPE, SIG_IGN);
    setvbuf(stdout, NULL, _IOLBF, 0);
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) { fputs("Cannot connect to Wayland\n", stderr); return 1; }
    struct wl_registry *registry = wl_display_get_registry(display);
    const struct wl_registry_listener listener = {global, removed};
    wl_registry_add_listener(registry, &listener, NULL);
    if (wl_display_roundtrip(display) < 0 || !manager) {
        fputs("Compositor does not support virtual pointers\n", stderr);
        wl_display_disconnect(display);
        return 1;
    }
    struct zwlr_virtual_pointer_v1 *pointer =
        zwlr_virtual_pointer_manager_v1_create_virtual_pointer(manager, NULL);
    if (wl_display_roundtrip(display) < 0) return 1;
    puts("READY");
    char line[256];
    unsigned x, y, width, height, button, state;
    double dx, dy;
    unsigned held[3] = {0, 0, 0};
    while (fgets(line, sizeof(line), stdin)) {
        if (sscanf(line, "absolute %u %u %u %u", &x, &y, &width, &height) == 4 && width && height) {
            zwlr_virtual_pointer_v1_motion_absolute(pointer, milliseconds(), x, y, width, height);
        } else if (sscanf(line, "relative %lf %lf", &dx, &dy) == 2) {
            zwlr_virtual_pointer_v1_motion(pointer, milliseconds(), wl_fixed_from_double(dx), wl_fixed_from_double(dy));
        } else if (sscanf(line, "button %u %u", &button, &state) == 2 && button >= 272 && button <= 274 && state <= 1) {
            zwlr_virtual_pointer_v1_button(pointer, milliseconds(), button, state);
            held[button - 272] = state;
        } else if (!strcmp(line, "quit\n")) {
            break;
        } else {
            puts("ERROR invalid command");
            continue;
        }
        zwlr_virtual_pointer_v1_frame(pointer);
        if (wl_display_roundtrip(display) < 0) break;
        puts("OK");
    }
    for (unsigned i = 0; i < 3; i++)
        if (held[i]) zwlr_virtual_pointer_v1_button(pointer, milliseconds(), 272 + i, 0);
    zwlr_virtual_pointer_v1_frame(pointer);
    wl_display_roundtrip(display);
    zwlr_virtual_pointer_v1_destroy(pointer);
    zwlr_virtual_pointer_manager_v1_destroy(manager);
    wl_registry_destroy(registry);
    wl_display_flush(display);
    wl_display_disconnect(display);
    return 0;
}
