"""Desktop capture and input. Hyprland uses logical output coordinates."""
import io
import atexit
import json
import os
import select
import subprocess
import time
from pathlib import Path

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


def pointer_position(monitors, x, y):
    """Normalize layout coordinates to the virtual-pointer absolute frame."""
    outputs = [m for m in monitors if not m.get("disabled")]
    left, top = min(m["x"] for m in outputs), min(m["y"] for m in outputs)
    right = max(m["x"] + m["height" if m.get("transform", 0) % 2 else "width"] / m["scale"] for m in outputs)
    bottom = max(m["y"] + m["width" if m.get("transform", 0) % 2 else "height"] / m["scale"] for m in outputs)
    return round(x - left), round(y - top), round(right - left), round(bottom - top)


class VirtualPointer:
    def __init__(self):
        executable = Path(__file__).resolve().parents[1] / ".local/bin/wayland-pointer"
        if not executable.is_file():
            raise RuntimeError("Wayland pointer helper is missing. Run ./setup-linux.sh.")
        self.process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        atexit.register(self.close)
        try:
            self._ack("READY")
        except Exception:
            self.close()
            raise

    def _ack(self, expected="OK"):
        if not select.select([self.process.stdout], [], [], 5)[0]:
            raise RuntimeError("Wayland pointer did not respond.")
        if self.process.stdout.readline().strip() != expected:
            raise RuntimeError("Wayland pointer disconnected or rejected an input event.")

    def send(self, command):
        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
            self._ack()
        except (OSError, RuntimeError):
            self.close()
            raise

    def close(self):
        # EOF releases held buttons in the helper, also when the worker is terminated.
        if self.process.stdin and not self.process.stdin.closed:
            try:
                self.process.stdin.close()
            except OSError:
                pass # A disconnected compositor may have already closed the pipe.
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
        self.process.stdout.close()
        self.process.stderr.close()


class HyprlandDesktop:
    PAUSE = 0.05
    FAILSAFE = False

    def __init__(self):
        self.monitor = None
        self.image_size = None
        self.pointer = None

    def _send(self, command):
        if self.pointer is None:
            self.pointer = VirtualPointer()
        self.pointer.send(command)

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
        monitors = json.loads(hyprctl("-j", "monitors"))
        current = select_monitor(monitors, self.monitor["name"])
        if any(current[k] != self.monitor[k] for k in ("x", "y", "width", "height", "scale", "transform")):
            raise RuntimeError("Monitor layout changed during the run; restart Blood Emporium.")
        x, y = logical_position(self.monitor, self.image_size, x, y)
        self._send("absolute " + " ".join(map(str, pointer_position(monitors, x, y))))
        if _pause:
            time.sleep(self.PAUSE)

    def _button(self, button, state, pause):
        code = {"left": 272, "right": 273, "middle": 274}[button]
        if state == "up" and self.pointer is None:
            return # This process never held a button (e.g. the GUI stopping its worker).
        self._send(f"button {code} {1 if state == 'down' else 0}")
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
