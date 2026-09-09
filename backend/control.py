"""Small local-only command client, also used by the Hyprland shortcut."""
import os
import socket
import sys


def socket_path():
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
                        "bloodemporium.sock")


def send_command(command="toggle"):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(2)
        client.connect(socket_path())
        client.sendall(command.encode() + b"\n")


if __name__ == "__main__":
    send_command(sys.argv[1] if len(sys.argv) > 1 else "toggle")
