import os
import sys

from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QIcon, QCursor
from PyQt5.QtWidgets import QLabel, QLineEdit, QCheckBox, QComboBox, QListView, QPushButton, QWidget, QVBoxLayout, \
    QToolButton, QProxyStyle, QStyle, QScrollArea, QScrollBar, QPlainTextEdit
from backend.desktop import IS_WAYLAND
if not IS_WAYLAND:
    from pynput import keyboard

from frontend.stylesheets import StyleSheets

sys.path.append(os.path.dirname(os.path.realpath("backend/state.py")))

from backend.config import Config
from backend.util.text_util import TextUtil

class Font(QFont):
    def __init__(self, font_size):
        super().__init__()
        self.setFamily("Segoe UI")
        self.setPointSize(font_size)

class TextLabel(QLabel):
    def __init__(self, parent, object_name, text, font=Font(10), style_sheet=StyleSheets.white_text):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setText(text)
        self.setFont(font)
        self.setStyleSheet(style_sheet)
        self.setAlignment(Qt.AlignVCenter)

# TODO could remove this and replace with what authorButton and updateButton are using (should make a class for it)
class HyperlinkTextLabel(QLabel):
    def __init__(self, parent, object_name, text, link, font):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFont(font)
        self.setText(f"<a style=\"color: white; text-decoration:none;\" href=\"{link}\">{text}</a>")
        self.setAlignment(Qt.AlignVCenter)
        self.setTextFormat(Qt.RichText)
        self.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.setOpenExternalLinks(True)

class HotkeyListenerControl:
    """
    Single point of control for the global run/terminate hotkey listener.

    Widgets suspend the listener while they have keyboard focus, so that typing cannot trigger a run.
    Suspends are reference counted: an unbalanced resume used to start a second listener without stopping
    the first, and every extra listener calls run_terminate() again on the same key press. Two listeners
    therefore run and immediately terminate, which looks like the hotkey doing nothing at all.
    """
    on_suspend = staticmethod(lambda: None)
    on_resume = staticmethod(lambda: None)
    __depth = 0

    @classmethod
    def suspend(cls):
        cls.__depth += 1
        if cls.__depth == 1:
            cls.on_suspend()

    @classmethod
    def resume(cls):
        if cls.__depth == 0:
            return # unpaired resume: the listener is already running
        cls.__depth -= 1
        if cls.__depth == 0:
            cls.on_resume()

class HotkeySuspendingInput:
    """
    Mixin pairing each suspend with exactly one resume, per widget. Read only inputs still receive focus
    events, and setReadOnly can be toggled while the widget is focused, so the pairing cannot be inferred
    from isReadOnly() at focus-out time alone.
    """
    def suspend_hotkey_listener(self):
        if not getattr(self, "_hotkey_suspended", False):
            self._hotkey_suspended = True
            HotkeyListenerControl.suspend()

    def resume_hotkey_listener(self):
        if getattr(self, "_hotkey_suspended", False):
            self._hotkey_suspended = False
            HotkeyListenerControl.resume()

class TextInputBox(QLineEdit, HotkeySuspendingInput):
    def __init__(self, parent, object_name, size, placeholder_text, text=None, font=Font(10),
                 style_sheet=StyleSheets.text_box):
        QLineEdit.__init__(self, parent)
        self.setObjectName(object_name)
        self.setFixedSize(size)
        self.setPlaceholderText(placeholder_text)
        if text is not None:
            self.setText(text)
        self.setFont(font)
        self.setStyleSheet(style_sheet)

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:
        super().focusInEvent(event)
        if not self.isReadOnly():
            QTimer.singleShot(0, self.selectAll)
            self.suspend_hotkey_listener()

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        super().focusOutEvent(event)
        self.resume_hotkey_listener()

    def setReadOnly(self, a0: bool) -> None:
        super().setReadOnly(a0)
        self.setStyleSheet(StyleSheets.text_box if not a0 else StyleSheets.text_box_read_only)

class MultiLineTextInputBox(QPlainTextEdit, HotkeySuspendingInput):
    def __init__(self, parent, object_name, width, height, full_height, placeholder_text, text=None, font=Font(10),
                 style_sheet=StyleSheets.multiline_text_box):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFixedWidth(width)
        self.small_height = height
        self.full_height = full_height
        self.setMinimumHeight(height)
        self.setPlaceholderText(placeholder_text)
        if text is not None:
            self.setPlainText(text)
        self.setFont(font)
        self.setStyleSheet(style_sheet)

    def setReadOnly(self, a0: bool) -> None:
        super().setReadOnly(a0)
        self.setStyleSheet(StyleSheets.multiline_text_box_read_only if a0 else StyleSheets.multiline_text_box)
        # self.viewport().setCursor(Qt.ForbiddenCursor if a0 else Qt.IBeamCursor)

    def wheelEvent(self, e: QtGui.QWheelEvent) -> None:
        current = self.verticalScrollBar().value()
        minimum = self.verticalScrollBar().minimum()
        maximum = self.verticalScrollBar().maximum()

        if e.angleDelta().y() < 0 and current == maximum:
            self.verticalScrollBar().setValue(maximum)
        elif e.angleDelta().y() > 0 and current == minimum:
            self.verticalScrollBar().setValue(minimum)
        else:
            return QPlainTextEdit.wheelEvent(self, e)
        e.accept()

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:
        super().focusInEvent(event)
        if not self.isReadOnly():
            self.animate()
            self.suspend_hotkey_listener()

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        super().focusOutEvent(event)
        if not self.isReadOnly():
            self.animate()
        # resumed unconditionally: setReadOnly(True) can be called while this widget is focused (see the
        # preferences page switching to a bundled profile), which would otherwise never resume the listener
        self.resume_hotkey_listener()

    def animate(self):
        self.animation = QPropertyAnimation(self, b"minimumHeight")
        self.animation.setDuration(500)
        self.animation.setStartValue(self.minimumHeight())
        self.animation.setEndValue(self.full_height if self.hasFocus() else self.small_height)
        self.animation.setEasingCurve(QEasingCurve.InOutQuint)
        self.animation.start()

class CheckBox(QCheckBox):
    def __init__(self, parent, object_name, style_sheet=StyleSheets.check_box):
        super().__init__(parent)
        if object_name is not None:
            self.setObjectName(object_name)
        self.setAutoFillBackground(False)
        self.setStyleSheet(style_sheet)

    def setEnabled(self, a0: bool) -> None:
        super().setEnabled(a0)
        self.setStyleSheet(StyleSheets.check_box if a0 else StyleSheets.check_box_read_only)

class Selector(QComboBox):
    def __init__(self, parent, object_name, size, items, active_item=None):
        super().__init__(parent)
        self.view = QListView()
        self.view.setFont(Font(8))

        self.setObjectName(object_name)
        self.setFont(Font(10))
        # # size is either QSize or integer for height (with auto sizing width)
        # if isinstance(size, int):
        #     self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        #     self.setFixedHeight(size)
        # else:
        #     self.setFixedSize(size)
        self.setFixedSize(size)
        self.addItems(items)
        if active_item is not None:
            self.setCurrentIndex(self.findText(active_item))
        self.setView(self.view)
        self.setStyleSheet(StyleSheets.selector)

    def wheelEvent(self, e: QtGui.QWheelEvent) -> None:
        e.ignore()

class Button(QPushButton):
    def __init__(self, parent, object_name, text, size: QSize):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFixedSize(size)
        self.setFont(Font(10))
        self.setText(text)
        self.setStyleSheet(StyleSheets.button)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)

class CheckBoxWithFunction(CheckBox):
    def __init__(self, parent, object_name, on_click, style_sheet=StyleSheets.check_box):
        super().__init__(parent, object_name, style_sheet)
        self.clicked.connect(on_click)

class CollapsibleBox(QWidget):
    def __init__(self, parent, object_name, text):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(15)

        self.toggleButton = QToolButton(self)
        self.toggleButton.setObjectName(object_name)
        self.toggleButton.setCheckable(True)
        self.toggleButton.setChecked(False)
        self.toggleButton.setFont(Font(12))
        self.toggleButton.setStyleSheet(StyleSheets.collapsible_box_inactive)
        self.toggleButton.setText(text)
        self.toggleButton.setIcon(QIcon(Icons.right_arrow))
        self.toggleButton.setIconSize(QSize(20, 20))
        self.toggleButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggleButton.pressed.connect(self.on_pressed)
        self.toggleButton.setStyle(NoShiftStyle())
        self.toggleButton.setCursor(Qt.PointingHandCursor)

        self.layout.addWidget(self.toggleButton, alignment=Qt.AlignTop)

    def on_pressed(self):
        pass

# https://forum.qt.io/topic/15068/prevent-flat-qtoolbutton-from-moving-when-clicked/8
class NoShiftStyle(QProxyStyle):
    def pixelMetric(self, metric, option, widget):
        if metric == QStyle.PM_ButtonShiftHorizontal or metric == QStyle.PM_ButtonShiftVertical:
            ret = 0
        else:
            ret = QProxyStyle.pixelMetric(self, metric, option, widget)
        return ret

class Icons:
    __base = "assets/images/icons"

    icon = "assets/images/inspo1.png"
    app_splash = "assets/images/app_splash.png"
    splash = "assets/images/splash.png"

    # https://thenounproject.com/browse/collection-icon/website-library-79202/
    minimize = __base + "/icon_minimize.png"
    restore = __base + "/icon_restore.png"
    maximize = __base + "/icon_maximize.png"
    close = __base + "/icon_close.png"
    menu = __base + "/icon_menu.png"
    home = __base + "/icon_home.png"
    preferences = __base + "/icon_preferences.png"
    settings = __base + "/icon_settings.png"
    bloodweb = __base + "/icon_graph.png"
    help = __base + "/icon_help.png"
    down_arrow = __base + "/icon_down_arrow.png"
    right_arrow = __base + "/icon_right_arrow.png"
    up_arrow = __base + "/icon_up_arrow.png"
    discord = __base + "/icon_discord.png"
    twitter = __base + "/icon_twitter.png"

# TODO space shouldnt deselect
class HotkeyInput(QPushButton, HotkeySuspendingInput):
    def __init__(self, parent, object_name, size):
        super().__init__(parent)
        self.pressed_keys = []
        self.pressed_keys_cache = []
        self.active = False
        self.listener = None
        self.setObjectName(object_name)
        self.setFixedSize(size)
        self.setStyleSheet(StyleSheets.button)
        self.set_keys(Config().hotkey())
        self.setFont(Font(10))
        self.clicked.connect(self.on_click)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def on_click(self):
        if self.active:
            self.set_keys(self.pressed_keys_cache) # cancelled: restore what was showing before recording
            self.stop_recording()
        else:
            self.pressed_keys_cache = list(self.pressed_keys)
            self.pressed_keys = []
            self.setStyleSheet(StyleSheets.button_recording)
            self.setText("Recording keystrokes...")
            self.active = True
            self.suspend_hotkey_listener()
            self.start_recording_listener()

    def stop_recording(self):
        """Idempotent: a combination emits one key release per key, but only the first ends the recording."""
        if not self.active:
            return
        self.active = False
        self.stop_recording_listener()
        self.setStyleSheet(StyleSheets.button)
        self.resume_hotkey_listener()

    def start_recording_listener(self):
        self.stop_recording_listener() # never leave a previous listener running
        if IS_WAYLAND:
            self.setFocus()
            return # Qt records keys locally; Hyprland handles the global shortcut.
        self.listener = keyboard.Listener(on_press=self.on_key_down, on_release=self.on_key_up)
        self.listener.start()

    def stop_recording_listener(self):
        if self.listener is None:
            return
        self.listener.stop()
        self.listener = None

    def on_key_down(self, key):
        if not self.active or self.listener is None:
            return
        key = TextUtil.pynput_to_key_string(self.listener, key)
        if key is None:
            return
        self.pressed_keys = list(dict.fromkeys(self.pressed_keys + [key]))
        self.setText(" + ".join([TextUtil.title_case(k) for k in self.pressed_keys]))

    def on_key_up(self, key):
        # releasing any key ends the recording; the remaining releases of the combination land here with the
        # listener already torn down, which used to raise AttributeError inside the listener thread
        if not self.active or self.listener is None:
            return
        if TextUtil.pynput_to_key_string(self.listener, key) is None:
            return

        self.setText(" + ".join([TextUtil.title_case(k) for k in self.pressed_keys]))
        self.stop_recording()

    def keyPressEvent(self, event):
        if IS_WAYLAND and self.active:
            if event.isAutoRepeat():
                return
            names = {Qt.Key_Control: "ctrl", Qt.Key_Alt: "alt", Qt.Key_Shift: "shift",
                     Qt.Key_Meta: "cmd", Qt.Key_Escape: "esc", Qt.Key_Return: "enter",
                     Qt.Key_Space: "space"}
            key = names.get(event.key())
            if key is None:
                from PyQt5.QtGui import QKeySequence
                key = QKeySequence(event.key()).toString().lower()
            if key and key not in self.pressed_keys:
                self.pressed_keys.append(key)
            self.setText(" + ".join(self.pressed_keys))
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if IS_WAYLAND and self.active:
            if not event.isAutoRepeat():
                self.stop_recording()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def set_keys(self, pressed_keys):
        self.pressed_keys = list(pressed_keys)
        self.setText(" + ".join([TextUtil.title_case(k) for k in self.pressed_keys]))

class ScrollBar(QScrollBar):
    def __init__(self, parent, base_object_name):
        super().__init__(parent)
        self.setObjectName(f"{base_object_name}ScrollBar")
        self.setOrientation(Qt.Vertical)
        self.setStyleSheet(StyleSheets.scroll_bar)

class ScrollArea(QScrollArea):
    def __init__(self, parent, base_object_name, scroll_bar):
        super().__init__(parent)
        self.setObjectName(f"{base_object_name}ScrollArea")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBar(scroll_bar)
        self.setWidgetResizable(True)
        self.setStyleSheet(f"""
            QScrollArea#{base_object_name}ScrollArea {{
                background: transparent;
                border: 0px;
            }}""")

class ScrollAreaContent(QWidget):
    def __init__(self, parent, base_object_name):
        super().__init__(parent)
        self.setObjectName(f"{base_object_name}ScrollAreaContent")
        self.setStyleSheet(f"""
            QWidget#{base_object_name}ScrollAreaContent {{
                background: transparent;
            }}""")