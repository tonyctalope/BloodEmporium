#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
mkdir -p .local/bin .cache/native
wayland-scanner client-header native/wlr-virtual-pointer-unstable-v1.xml .cache/native/virtual-pointer-client.h
wayland-scanner private-code native/wlr-virtual-pointer-unstable-v1.xml .cache/native/virtual-pointer-protocol.c
cc -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Werror -O2 \
    -I.cache/native native/wayland_pointer.c .cache/native/virtual-pointer-protocol.c \
    $(pkg-config --cflags --libs wayland-client) -o .local/bin/wayland-pointer
