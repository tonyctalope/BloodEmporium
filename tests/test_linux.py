import math
import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("WAYLAND_DISPLAY", "test-wayland")

import cv2
import numpy as np
import torch

from backend.desktop import logical_position, pointer_position, select_monitor, HyprlandDesktop
from backend.rotated_nms import obb_nms
from frontend.linux_hotkey import HyprlandHotkey, binding_spec, keysym_name, lua_string


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.monitor = dict(name="DP-1", width=2560, height=1440, x=1920, y=-200,
                            scale=1.25, transform=0, focused=True)

    def test_offset_and_fractional_scale(self):
        self.assertEqual(logical_position(self.monitor, (2560, 1440), 1280, 720), (2944, 376))

    def test_rotated_output(self):
        self.monitor["transform"] = 1
        self.assertEqual(logical_position(self.monitor, (1440, 2560), 720, 1280), (2496, 824))

    def test_outside_capture_rejected(self):
        with self.assertRaises(ValueError):
            logical_position(self.monitor, (2560, 1440), -1, 10)

    def test_explicit_output_and_disconnected_output(self):
        other = dict(self.monitor, name="HDMI-A-1", focused=False)
        self.assertEqual(select_monitor([other, self.monitor])["name"], "DP-1")
        self.assertEqual(select_monitor([other, self.monitor], "HDMI-A-1")["name"], "HDMI-A-1")
        with self.assertRaises(RuntimeError):
            select_monitor([self.monitor], "missing")

    def test_no_move_before_capture(self):
        with self.assertRaises(RuntimeError):
            HyprlandDesktop().moveTo(10, 10)

    def test_virtual_pointer_frame_with_negative_origin(self):
        other = dict(self.monitor, name="HDMI-A-1", x=-1920, y=0, width=1920, height=1080, scale=1)
        self.assertEqual(pointer_position([other, self.monitor], 2944, 376), (4864, 576, 5888, 1280))

    @patch("backend.desktop.VirtualPointer")
    def test_mouse_press_and_release_are_distinct(self, pointer):
        desktop = HyprlandDesktop()
        desktop.mouseDown("right", _pause=False)
        desktop.mouseUp("right", _pause=False)
        self.assertEqual(pointer.return_value.send.call_args_list[0].args, ("button 273 1",))
        self.assertEqual(pointer.return_value.send.call_args_list[1].args, ("button 273 0",))
        pointer.assert_called_once() # one persistent device across press and release

    @patch("backend.desktop.hyprctl")
    @patch("backend.desktop.VirtualPointer")
    def test_move_emits_a_pointer_event_instead_of_warping_the_cursor(self, pointer, ctl):
        desktop = HyprlandDesktop()
        desktop.monitor = self.monitor
        desktop.image_size = (2560, 1440)
        ctl.return_value = json.dumps([self.monitor])
        desktop.moveTo(1280, 720, _pause=False)
        pointer.return_value.send.assert_called_once_with("absolute 1024 576 2048 1152")
        ctl.assert_called_once_with("-j", "monitors")


class NMSTests(unittest.TestCase):
    def test_duplicate_and_separate_boxes(self):
        boxes = torch.tensor([[10., 10, 8, 2, .4], [10., 10, 8, 2, .4], [50., 50, 8, 2, .4]])
        result, indices = obb_nms(boxes, torch.tensor([.8, .9, .7]), .45)
        self.assertEqual(indices.tolist(), [1, 2])
        torch.testing.assert_close(result, boxes[indices])

    def test_crossing_thin_edges_are_not_suppressed(self):
        boxes = np.array([[20., 20, 30, 2, math.pi/4], [20., 20, 30, 2, -math.pi/4]])
        _, indices = obb_nms(boxes, np.array([.9, .8]), .45)
        self.assertEqual(indices.tolist(), [0, 1])

    def test_contained_box_uses_actual_area_ratio(self):
        boxes = np.array([[0., 0, 100, 100, .3], [0., 0, 10, 10, .3]])
        _, indices = obb_nms(boxes, np.array([.9, .8]), .45)
        self.assertEqual(indices.tolist(), [0, 1])

    def test_empty_and_degenerate_boxes(self):
        _, indices = obb_nms(torch.empty((0, 5)), torch.empty(0), .45)
        self.assertEqual(indices.dtype, torch.int64)
        _, indices = obb_nms(np.array([[0., 0, 0, 2, 0]]), np.array([.8]), .45)
        self.assertEqual(indices.size, 0)


class HotkeyTests(unittest.TestCase):
    def test_french_characters_and_punctuation_use_xkb_names(self):
        for character, name in [("ç", "ccedilla"), ("é", "eacute"), ("è", "egrave"),
                                ("à", "agrave"), ("+", "plus"), ("&", "ampersand")]:
            with self.subTest(character=character):
                self.assertEqual(keysym_name(character), name)
        self.assertEqual(binding_spec(["ctrl", "alt", "ç"]), ("CTRL + ALT + ccedilla", 12, "ccedilla"))

    def test_lua_strings_keep_unicode_and_escape_quotes(self):
        self.assertEqual(lua_string('été "test"'), '"été \\"test\\""')

    def test_requires_one_regular_key(self):
        self.assertEqual(binding_spec(["ctrl", "alt", "9"]), ("CTRL + ALT + 9", 12, "9"))
        with self.assertRaises(ValueError):
            binding_spec(["ctrl", "a", "b"])

    @patch("frontend.linux_hotkey.hyprctl")
    def test_lua_dispatcher_id_is_not_mistaken_for_a_conflict(self, ctl):
        hotkey = HyprlandHotkey(["ctrl", "alt", "9"])
        ctl.return_value = json.dumps([dict(modmask=12, key="9", dispatcher="__lua", arg="200",
                                            description=hotkey.description)])
        hotkey.ensure_bound()
        self.assertTrue(hotkey.registered)
        self.assertEqual(ctl.call_count, 1) # no second binding added

    @patch("frontend.linux_hotkey.hyprctl")
    def test_existing_user_shortcut_is_preserved(self, ctl):
        ctl.return_value = json.dumps([dict(modmask=12, key="9", description="User shortcut")])
        with self.assertRaises(RuntimeError):
            HyprlandHotkey(["ctrl", "alt", "9"]).ensure_bound()
        self.assertEqual(ctl.call_count, 1) # query only; no unbind or overwrite


if __name__ == "__main__":
    unittest.main()
