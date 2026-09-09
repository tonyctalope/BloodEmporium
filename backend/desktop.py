"""Desktop capture and input. Hyprland uses logical output coordinates."""
import io
import json
import os
import subprocess
import time

IS_WAYLAND = bool(os.environ.get("WAYLAND_DISPLAY"))


def hyprctl(*args):
    result = subprocess.run(["hyprctl", *args], check=True, capture_output=True,
                            text=True, timeout=5)
    output = result.stdout.strip()
    if output.lower().startswith(("error", "invalid")):
        raise RuntimeError(output)
    return output


def select_monitor(monitors, requested=None):
    enabled = [m for m in monitors if not m.get("disabled") and m.get("dpmsStatus", True)]
    if requested:
        matches = [m for m in enabled if m["name"] == requested]
        if not matches:
            raise RuntimeError(f"Monitor {requested!r} is not active.")
        return matches[0]
    if not enabled:
        raise RuntimeError("No active monitor found.")
    return next((m for m in enabled if m.get("focused")), enabled[0])


def logical_position(monitor, image_size, x, y):
    width, height = monitor["width"], monitor["height"]
    if monitor.get("transform", 0) % 2:
        width, height = height, width
    if not (0 <= x < image_size[0] and 0 <= y < image_size[1]):
        raise ValueError("Click is outside the captured monitor.")
    return (round(monitor["x"] + x * width / monitor["scale"] / image_size[0]),
            round(monitor["y"] + y * height / monitor["scale"] / image_size[1]))


class HyprlandDesktop:
    PAUSE = 0.05
    FAILSAFE = False

    def __init__(self):
        self.monitor = None
        self.image_size = None

    def begin_run(self, output=None):
        self.monitor = select_monitor(json.loads(hyprctl("-j", "monitors")), output)
        self.screenshot()

    def screenshot(self):
        from PIL import Image
        if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            raise RuntimeError("Wayland support currently requires Hyprland.")
        monitors = json.loads(hyprctl("-j", "monitors"))
        requested = self.monitor["name"] if self.monitor else os.environ.get("BLOODEMPORIUM_MONITOR")
        self.monitor = select_monitor(monitors, requested)
        capture = subprocess.run(["grim", "-o", self.monitor["name"], "-t", "ppm", "-"],
                                 check=True, capture_output=True, timeout=10)
        image = Image.open(io.BytesIO(capture.stdout)).convert("RGB")
        self.image_size = image.size
        return image

    def moveTo(self, x, y, _pause=True):
        if self.monitor is None or self.image_size is None:
            raise RuntimeError("Capture a monitor before moving the pointer.")
        current = select_monitor(json.loads(hyprctl("-j", "monitors")), self.monitor["name"])
        if any(current[k] != self.monitor[k] for k in ("x", "y", "width", "height", "scale", "transform")):
            raise RuntimeError("Monitor layout changed during the run; restart Blood Emporium.")
        x, y = logical_position(self.monitor, self.image_size, x, y)
        hyprctl("eval", f"hl.dispatch(hl.dsp.cursor.move({{x={x}, y={y}}}))")
        if _pause:
            time.sleep(self.PAUSE)

    def _button(self, button, state, pause):
        code = {"left": 272, "right": 273, "middle": 274}[button]
        hyprctl("eval", 'hl.dispatch(hl.dsp.send_key_state({mods="", '
                f'key="mouse:{code}", state="{state}"' + '}))')
        if pause:
            time.sleep(self.PAUSE)

    def mouseDown(self, button="left", _pause=True):
        self._button(button, "down", _pause)

    def mouseUp(self, button="left", _pause=True):
        self._button(button, "up", _pause)


if IS_WAYLAND:
    desktop = HyprlandDesktop()
else:
    import pyautogui as desktop
