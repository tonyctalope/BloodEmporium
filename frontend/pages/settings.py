import os
import sys

from PyQt5.QtCore import QSize, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QGridLayout
from backend.desktop import IS_WAYLAND
if not IS_WAYLAND:
    from pynput import keyboard

from frontend.generic import Font, TextLabel, TextInputBox, Button, HotkeyInput, ScrollAreaContent, ScrollBar, \
    ScrollArea, Selector, MultiLineTextInputBox, HotkeyListenerControl
from frontend.layouts import RowLayout
from frontend.stylesheets import StyleSheets

sys.path.append(os.path.dirname(os.path.realpath("backend/state.py")))

from backend.config import Config
from backend.util.text_util import TextUtil

class SettingsPage(QWidget):
    # the hotkey listener runs on a pynput thread; run_terminate touches widgets, so it has to be handed back
    # to the GUI thread rather than called directly from the listener callback
    hotkey_pressed = pyqtSignal()

    def set_path(self):
        icon_dir = QFileDialog.getExistingDirectory(self, "Select Icon Folder", self.pathText.text())
        if icon_dir != "":
            self.pathText.setText(icon_dir)

    def on_path_update(self):
        text = self.pathText.text()
        self.pathText.setStyleSheet(StyleSheets.settings_input(text))

    def show_settings_page_save_success_text(self, text):
        self.saveSuccessText.setText(text)
        self.saveSuccessText.setStyleSheet(StyleSheets.pink_text)
        self.saveSuccessText.setVisible(True)
        QTimer.singleShot(10000, self.hide_settings_page_save_success_text)

    def show_settings_page_save_fail_text(self, text):
        self.saveSuccessText.setText(text)
        self.saveSuccessText.setStyleSheet(StyleSheets.purple_text)
        self.saveSuccessText.setVisible(True)
        QTimer.singleShot(10000, self.hide_settings_page_save_success_text)

    def hide_settings_page_save_success_text(self):
        self.saveSuccessText.setVisible(False)

    def save_settings(self):
        path = self.pathText.text()
        if not Config.verify_path(path):
            self.show_settings_page_save_fail_text("Ensure path is an actual folder (can be empty if you are not using "
                                                   "custom icons). Changes not saved.")
            return

        hotkey = self.hotkeyInput.pressed_keys
        if IS_WAYLAND:
            from frontend.linux_hotkey import binding_spec
            try:
                binding_spec(hotkey)
            except ValueError as e:
                self.show_settings_page_save_fail_text(str(e))
                return
        if len(hotkey) == 0:
            self.show_settings_page_save_fail_text("Click the hotkey field and press the key combination you want "
                                                   "before saving. Changes not saved.")
            return

        try:
            node_click_slots = Config.parse_node_click_slots(self.nodeClickOffsetText.toPlainText())
        except ValueError as e:
            self.show_settings_page_save_fail_text(f"{e} Changes not saved.")
            return

        config = Config()
        config.set_path(path)
        if IS_WAYLAND:
            config.set_capture_monitor(self.monitorSelector.currentData() or "")
        config.set_hotkey(hotkey)
        config.set_interaction(self.interactionSelector.currentText())
        config.set_primary_mouse(self.primaryMouseSelector.currentText())
        config.set_node_click_slots(node_click_slots)
        self.config_cache = Config()
        if not self.refresh_hotkey_keys():
            return
        self.bloodweb_page.refresh_run_description()
        self.show_settings_page_save_success_text("Settings saved.")

    def revert_settings(self):
        self.pathText.setText(self.config_cache.path())
        if IS_WAYLAND:
            self.monitorSelector.setCurrentIndex(max(0, self.monitorSelector.findData(self.config_cache.capture_monitor())))
        self.hotkeyInput.set_keys(self.config_cache.hotkey())
        self.interactionSelector.setCurrentIndex(self.interactionSelector.findText(self.config_cache.interaction()))
        self.primaryMouseSelector.setCurrentIndex(self.primaryMouseSelector.findText(self.config_cache.primary_mouse()))
        self.nodeClickOffsetText.setPlainText(Config.format_node_click_slots(self.config_cache.node_click_slots()))
        if not self.refresh_hotkey_keys():
            return
        self.show_settings_page_save_success_text("Settings reverted to last saved state.")

    def refresh_hotkey_keys(self):
        """Cached so the listener thread does not re-read config.json on every single key press."""
        self.hotkey_keys = set(self.config_cache.hotkey())
        if IS_WAYLAND and hasattr(self, "saveSuccessText"):
            return self.start_hotkey_listener()
        return True

    def start_hotkey_listener(self):
        self.stop_hotkey_listener() # never leave a previous listener running: two listeners toggle run twice
        self.pressed_keys = [] # keys released while stopped were never seen, so start from a clean state
        self.hotkey_triggered = False
        try:
            if IS_WAYLAND:
                from frontend.linux_hotkey import HyprlandHotkey
                self.hotkey_listener = HyprlandHotkey(self.config_cache.hotkey(), self.show_settings_page_save_fail_text)
            else:
                self.hotkey_listener = keyboard.Listener(on_press=self.on_key_down, on_release=self.on_key_up)
            self.hotkey_listener.start()
            return True
        except Exception as error:
            self.hotkey_listener = None
            self.show_settings_page_save_fail_text(str(error))
            return False

    def stop_hotkey_listener(self):
        if self.hotkey_listener is None:
            return
        self.hotkey_listener.stop()
        self.hotkey_listener = None

    def on_key_down(self, key):
        listener = self.hotkey_listener
        if listener is None:
            return
        key = TextUtil.pynput_to_key_string(listener, key)
        # only keys belonging to the hotkey are tracked, so an unrelated key held down (or one whose release
        # was missed while the listener was stopped) can never stop the hotkey from matching
        if key is None or key not in self.hotkey_keys:
            return
        if key not in self.pressed_keys:
            self.pressed_keys.append(key)
        if len(self.pressed_keys) == len(self.hotkey_keys) and not self.hotkey_triggered:
            self.hotkey_triggered = True # edge triggered: key auto-repeat would otherwise toggle run repeatedly
            self.hotkey_pressed.emit()

    def on_key_up(self, key):
        listener = self.hotkey_listener
        if listener is None:
            return
        key = TextUtil.pynput_to_key_string(listener, key)
        if key is None or key not in self.hotkey_keys:
            return
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)
        self.hotkey_triggered = False

    def __init__(self, run_terminate, bloodweb_page):
        super().__init__()
        self.hotkey_listener = None
        self.pressed_keys = []
        self.hotkey_triggered = False
        self.config_cache = Config()
        self.refresh_hotkey_keys()
        self.setObjectName("settingsPage")
        self.hotkey_pressed.connect(run_terminate)
        self.bloodweb_page = bloodweb_page

        self.layout = QGridLayout(self)
        self.layout.setObjectName("settingsPageLayout")
        self.layout.setContentsMargins(25, 25, 25, 25)
        self.layout.setSpacing(0)

        self.scrollBar = ScrollBar(self, "settingsPage")
        self.scrollArea = ScrollArea(self, "settingsPage", self.scrollBar)
        self.scrollAreaContent = ScrollAreaContent(self.scrollArea, "settingsPage")
        self.scrollArea.setWidget(self.scrollAreaContent)
        self.scrollAreaContentLayout = QVBoxLayout(self.scrollAreaContent)
        self.scrollAreaContentLayout.setObjectName("settingsPageScrollAreaContentLayout")
        self.scrollAreaContentLayout.setContentsMargins(0, 0, 0, 0)
        self.scrollAreaContentLayout.setSpacing(15)

        self.pathLabel = TextLabel(self, "settingsPagePathLabel", "Installation Path", Font(12))
        self.pathLabelDefaultLabel = TextLabel(self, "settingsPagePathLabelDefaultLabel",
                                               "<p style=line-height:125%>"
                                               "You only need to modify this if you are using custom icons.<br>"
                                               "Default path on Steam is C:/Program Files (x86)/Steam/steamapps/common/"
                                               "Dead by Daylight/DeadByDaylight/Content/UI/Icons<br>"
                                               "Default path on Epic Games is C:/Program Files/Epic Games/"
                                               "DeadByDaylight/Content/UI/Icons</p>", Font(10))
        if sys.platform == "linux":
            self.pathLabelDefaultLabel.setText("Leave empty to use bundled icons. For custom icons, select the "
                                               "DeadByDaylight/Content/UI/Icons folder in your Steam library.")
        self.pathLabelDefaultLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.pathLabelDefaultLabel.setCursor(Qt.IBeamCursor)

        self.pathRow = QWidget(self)
        self.pathRow.setObjectName("settingsPagePathRow")
        self.pathRowLayout = RowLayout(self.pathRow, "settingsPagePathRowLayout")

        self.pathText = TextInputBox(self, "settingsPagePathText", QSize(550, 40),
                                     "Path to Dead by Daylight game icon files", str(self.config_cache.path()))
        self.on_path_update()
        self.pathText.textChanged.connect(self.on_path_update)
        self.pathButton = Button(self, "settingsPagePathButton", "Browse for icons folder", QSize(180, 35))
        self.pathButton.clicked.connect(self.set_path)

        self.hotkeyLabel = TextLabel(self, "settingsPageHotkeyLabel", "Hotkey", Font(12))
        self.hotkeyDescription = TextLabel(self, "settingsPageHotkeyDescription",
                                           "Shortcut to run or terminate the automatic bloodweb process.", Font(10))

        self.hotkeyInput = HotkeyInput(self, "settingsPageHotkeyInput", QSize(300, 40))

        self.nodeClickOffsetLabel = TextLabel(self, "settingsPageNodeClickOffsetLabel", "Node Click Offset", Font(12))
        self.nodeClickOffsetDescription = TextLabel(self, "settingsPageNodeClickOffsetDescription",
                                                    "<p style=line-height:125%>"
                                                    "Some bloodweb slots have a misaligned hitbox in game and ignore "
                                                    "a click on the centre of the icon sitting in them "
                                                    "(bugreport.deadbydaylight.com/projects/pr-5642738318/issues/1913)."
                                                    "<br>A slot is identified by where it sits, not by what is in it, "
                                                    "since that changes every bloodweb. One entry per line:<br>"
                                                    "<i>angle, ring, horizontal %, vertical %</i><br>"
                                                    "<b>angle</b>: degrees clockwise from straight up (0 is up, 90 is "
                                                    "right, -90 is left). <b>ring</b>: distance from the middle of the "
                                                    "bloodweb, where 1 is the innermost ring of six nodes and 2 is "
                                                    "twice that far out.<br>The percentages shift the click away from "
                                                    "the centre of the icon; negative is left / up, maximum 40. So "
                                                    "<i>15, 2.1, 0, -25</i> clicks a quarter of the icon's height "
                                                    "above centre, on the slot just right of straight up on the second "
                                                    "ring.<br>Every node's angle and ring is written to the log each "
                                                    "level, so the numbers for a slot can be read from there.</p>",
                                                    Font(10))
        self.nodeClickOffsetDescription.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.nodeClickOffsetText = MultiLineTextInputBox(self, "settingsPageNodeClickOffsetText", 550, 60, 120,
                                                         "angle, ring, horizontal %, vertical %",
                                                         Config.format_node_click_slots(
                                                             self.config_cache.node_click_slots()))

        self.accessibilityLabel = TextLabel(self, "settingsPageAccessibilityLabel", "Accessibility Options", Font(12))

        self.interactionRow = QWidget(self)
        self.interactionRow.setObjectName("settingsPageInteractionRow")
        self.interactionRowLayout = RowLayout(self.interactionRow, "settingsPageInteractionRowLayout")

        self.interactionDescription = TextLabel(self, "settingsPageInteractionDescription", "Bloodweb Interaction Mode",
                                                Font(10))
        self.interactionSelector = Selector(self, "settingsPageInteractionSelector", QSize(85, 35),
                                            ["press", "hold"], self.config_cache.interaction())

        self.primaryMouseRow = QWidget(self)
        self.primaryMouseRow.setObjectName("settingsPagePrimaryMouseRow")
        self.primaryMouseRowLayout = RowLayout(self.primaryMouseRow, "settingsPagePrimaryMouseRowLayout")

        self.primaryMouseDescription = TextLabel(self, "settingsPagePrimaryMouseDescription", "Primary Mouse Button",
                                                 Font(10))
        self.primaryMouseSelector = Selector(self, "settingsPagePrimaryMouseSelector", QSize(80, 35),
                                             ["left", "right"], self.config_cache.primary_mouse())

        self.saveRow = QWidget(self)
        self.saveRow.setObjectName("settingsPageSaveRow")
        self.saveRowLayout = RowLayout(self.saveRow, "settingsPageSaveRowLayout")

        self.saveButton = Button(self.saveRow, "settingsPageSaveButton", "Save", QSize(60, 35))
        self.saveButton.clicked.connect(self.save_settings)
        self.revertButton = Button(self.saveRow, "settingsPageRevertButton", "Revert", QSize(70, 35))
        self.revertButton.clicked.connect(self.revert_settings)

        self.saveSuccessText = TextLabel(self.saveRow, "settingsPageSaveSuccessText", "", Font(10))
        self.saveSuccessText.setVisible(False)

        self.pathRowLayout.addWidget(self.pathText)
        self.pathRowLayout.addWidget(self.pathButton)
        self.pathRowLayout.addStretch(1)

        self.interactionRowLayout.addWidget(self.interactionDescription)
        self.interactionRowLayout.addWidget(self.interactionSelector)
        self.interactionRowLayout.addStretch(1)

        self.primaryMouseRowLayout.addWidget(self.primaryMouseDescription)
        self.primaryMouseRowLayout.addWidget(self.primaryMouseSelector)
        self.primaryMouseRowLayout.addStretch(1)

        self.saveRowLayout.addWidget(self.saveButton)
        self.saveRowLayout.addWidget(self.revertButton)
        self.saveRowLayout.addWidget(self.saveSuccessText)
        self.saveRowLayout.addStretch(1)

        self.scrollAreaContentLayout.addWidget(self.pathLabel)
        self.scrollAreaContentLayout.addWidget(self.pathLabelDefaultLabel)
        self.scrollAreaContentLayout.addWidget(self.pathRow)
        if IS_WAYLAND:
            import json
            from backend.desktop import hyprctl
            from PyQt5.QtWidgets import QComboBox
            self.monitorSelector = QComboBox(self)
            self.monitorSelector.addItem("Focused screen when starting", "")
            outputs = [m["name"] for m in json.loads(hyprctl("-j", "monitors"))]
            saved = self.config_cache.capture_monitor()
            if saved and saved not in outputs:
                outputs.append(saved)
            for output in outputs:
                self.monitorSelector.addItem(output, output)
            self.monitorSelector.setCurrentIndex(max(0, self.monitorSelector.findData(saved)))
            self.scrollAreaContentLayout.addWidget(TextLabel(self, "monitorLabel", "Game screen", Font(12)))
            self.scrollAreaContentLayout.addWidget(self.monitorSelector)
        self.scrollAreaContentLayout.addWidget(self.hotkeyLabel)
        self.scrollAreaContentLayout.addWidget(self.hotkeyDescription)
        self.scrollAreaContentLayout.addWidget(self.hotkeyInput)
        self.scrollAreaContentLayout.addWidget(self.nodeClickOffsetLabel)
        self.scrollAreaContentLayout.addWidget(self.nodeClickOffsetDescription)
        self.scrollAreaContentLayout.addWidget(self.nodeClickOffsetText)
        self.scrollAreaContentLayout.addWidget(self.accessibilityLabel)
        self.scrollAreaContentLayout.addWidget(self.interactionRow)
        self.scrollAreaContentLayout.addWidget(self.primaryMouseRow)
        self.scrollAreaContentLayout.addWidget(self.saveRow)
        self.scrollAreaContentLayout.addStretch(1)

        self.layout.addWidget(self.scrollArea)
        self.layout.setRowStretch(0, 1)
        self.layout.setColumnStretch(0, 1)