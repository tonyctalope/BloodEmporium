"""Interactive desktop smoke test; only clicks its own temporary test window.

Run with ./run-linux.sh --desktop-selfcheck. Never starts Bloodweb automation.
"""
import json
from multiprocessing import Pipe

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication, QPushButton
from PyQt5.QtTest import QTest

from backend.control import send_command
from backend.desktop import HyprlandDesktop, hyprctl
from frontend.linux_hotkey import CommandServer


def main(app_module):
    app = QApplication([])
    server = CommandServer(app)
    main_pipe, state_pipe = Pipe()
    emitter = app_module.Emitter(main_pipe)
    window = app_module.MainWindow(state_pipe, emitter, False)
    window.show()
    clicks = []
    commands = []
    server.callback = lambda: commands.append("toggle")
    button = QPushButton("Blood Emporium — Linux input test")
    button.setWindowTitle("Blood Emporium input test")
    button.resize(600, 250)
    button.pressed.connect(lambda: clicks.append("down"))
    button.released.connect(lambda: clicks.append("up"))
    original_cursor = json.loads(hyprctl("-j", "cursorpos"))

    def wait(ms=250):
        QTest.qWait(ms)

    try:
        wait(500)
        assert window.preferencesPage is not None
        assert window.settingsPage.hotkey_listener is not None
        window.settingsPage.hotkey_listener.ensure_bound()
        window.settingsPage.hotkey_listener.ensure_bound() # repeat must not report our own bind as a conflict
        send_command()
        wait()
        assert commands == ["toggle"], commands
        print("GUI, global shortcut registration and local command delivery: OK")

        widget = window.settingsPage.hotkeyInput
        cached = list(widget.pressed_keys)
        widget.on_click()
        QTest.keyPress(widget, Qt.Key_Control)
        QTest.keyPress(widget, Qt.Key_Alt)
        QTest.keyPress(widget, Qt.Key_8)
        QTest.keyRelease(widget, Qt.Key_8)
        QTest.keyRelease(widget, Qt.Key_Alt)
        QTest.keyRelease(widget, Qt.Key_Control)
        assert widget.pressed_keys == ["ctrl", "alt", "8"], widget.pressed_keys
        widget.set_keys(cached)
        print("Shortcut recording: OK")

        button.show()
        wait(800)
        hyprctl("eval", 'hl.dispatch(hl.dsp.focus({window="title:^Blood Emporium input test$"}))')
        wait()
        desktop = HyprlandDesktop()
        capture = desktop.screenshot()
        point = button.mapToGlobal(QPoint(button.width() // 2, button.height() // 2))
        monitor = desktop.monitor
        x = (point.x() - monitor["x"]) * monitor["scale"]
        y = (point.y() - monitor["y"]) * monitor["scale"]
        desktop.moveTo(x, y)
        wait()
        active = json.loads(hyprctl("-j", "activewindow"))
        assert active["title"] == button.windowTitle(), "Test window lost focus; refusing to click"
        desktop.mouseDown()
        wait()
        assert clicks == ["down"], clicks
        desktop.mouseUp()
        wait()
        assert clicks == ["down", "up"], clicks
        print(f"Wayland capture {capture.size}, pointer positioning, held click and release: OK")
    finally:
        desktop = HyprlandDesktop()
        desktop.mouseUp(_pause=False)
        hyprctl("eval", f'hl.dispatch(hl.dsp.cursor.move({{x={original_cursor["x"]}, y={original_cursor["y"]}}}))')
        window.settingsPage.stop_hotkey_listener()
        window.state.terminate()
        button.close()
        window.close()
        server.server.close()
        main_pipe.close()
        state_pipe.close()
