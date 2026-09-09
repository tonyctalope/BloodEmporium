"""Hyprland global shortcut with a Qt-thread callback and local IPC."""
import json
import os
import shlex
import sys
from pathlib import Path

from PyQt5.QtCore import QObject, QTimer
from PyQt5.QtNetwork import QLocalServer, QLocalSocket

from backend.control import socket_path
from backend.desktop import hyprctl

MODIFIERS = {"ctrl": ("CTRL", 4), "alt": ("ALT", 8), "shift": ("SHIFT", 1), "cmd": ("SUPER", 64)}


def binding_spec(keys):
    mods, mask, normal = [], 0, []
    for key in keys:
        if key in MODIFIERS:
            name, bit = MODIFIERS[key]
            mods.append(name)
            mask |= bit
        else:
            normal.append({"enter": "Return", "esc": "Escape", "space": "space"}.get(key, key))
    if len(normal) != 1:
        raise ValueError("Use modifiers and exactly one non-modifier key for the Hyprland shortcut.")
    return " + ".join(mods + normal), mask, normal[0]


class CommandServer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.callback = None
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        probe = QLocalSocket()
        probe.connectToServer(socket_path())
        if probe.waitForConnected(200):
            probe.abort()
            raise RuntimeError("Blood Emporium is already running.")
        QLocalServer.removeServer(socket_path())
        if not self.server.listen(socket_path()):
            raise RuntimeError(self.server.errorString())
        self.server.newConnection.connect(self.accept)

    def accept(self):
        while self.server.hasPendingConnections():
            client = self.server.nextPendingConnection()
            client.readyRead.connect(lambda c=client: self.receive(c))
            client.disconnected.connect(client.deleteLater)
            if client.bytesAvailable():
                self.receive(client)

    def receive(self, client):
        if not client.canReadLine():
            return
        command = bytes(client.readLine()).strip()
        if command == b"toggle" and self.callback:
            self.callback()
        client.disconnectFromServer()


class HyprlandHotkey:
    def __init__(self, keys, on_error=None):
        self.spec, self.mask, self.key = binding_spec(keys)
        client = Path(__file__).resolve().parents[1] / "backend/control.py"
        self.command = shlex.join([sys.executable, str(client), "toggle"])
        self.description = f"Blood Emporium: run / stop ({os.getpid()})"
        self.on_error = on_error
        self.timer = QTimer()
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.poll)
        self.registered = False

    def ensure_bound(self):
        bindings = json.loads(hyprctl("-j", "binds"))
        matches = [b for b in bindings if b.get("modmask") == self.mask
                   and b.get("key", "").lower() == self.key.lower()]
        if matches:
            if any(b.get("description") != self.description for b in matches):
                raise RuntimeError(f"Hyprland shortcut {self.spec} is already assigned. Choose another shortcut.")
            self.registered = True
            return
        hyprctl("eval", f"hl.bind({json.dumps(self.spec)}, hl.dsp.exec_cmd({json.dumps(self.command)}), "
                f'{{description={json.dumps(self.description)}}})')
        self.registered = True

    def poll(self):
        try:
            self.ensure_bound()
        except Exception as error:
            self.timer.stop()
            if self.on_error:
                self.on_error(str(error))

    def start(self):
        self.ensure_bound()
        # Re-register after a compositor config reload.
        self.timer.start()

    def stop(self):
        self.timer.stop()
        if self.registered:
            bindings = json.loads(hyprctl("-j", "binds"))
            if any(b.get("description") == self.description for b in bindings):
                hyprctl("eval", f"hl.unbind({json.dumps(self.spec)})")
            self.registered = False
