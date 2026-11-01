"""Tests for the pure helpers; they need no Home Assistant installation."""

import importlib.util
import sys
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "util", Path(__file__).parents[1] / "custom_components" / "unifi_doorbell_display" / "util.py"
)
util = importlib.util.module_from_spec(_spec)
sys.modules["util"] = util
_spec.loader.exec_module(util)


class ParseMessage(unittest.TestCase):
    def test_absent_is_default(self):
        self.assertTrue(util.parse_message(None).is_default)
        self.assertTrue(util.parse_message({}).is_default)

    def test_image_with_reset(self):
        msg = util.parse_message({"type": "IMAGE", "text": "abc.png", "resetAt": 1793555626806})
        self.assertEqual((msg.kind, msg.text, msg.reset_at_ms), ("image", "abc.png", 1793555626806))

    def test_unknown_type_is_default(self):
        self.assertTrue(util.parse_message({"type": "SOMETHING_NEW"}).is_default)


class BuildMessage(unittest.TestCase):
    def test_permanent_image(self):
        self.assertEqual(
            util.build_message("image", "abc.png", None, 1000),
            {"type": "IMAGE", "text": "abc.png", "resetAt": None},
        )

    def test_duration_sets_reset_at_in_ms(self):
        self.assertEqual(util.build_message("custom_text", "Hi", 20, 1000)["resetAt"], 21000)

    def test_builtin_texts(self):
        self.assertEqual(util.build_message("do_not_disturb")["text"], "DO NOT DISTURB")

    def test_default_cannot_be_sent(self):
        with self.assertRaises(ValueError):
            util.build_message("default")


class Names(unittest.TestCase):
    def test_friendly_name(self):
        self.assertEqual(util.friendly_name("cat_halloween_small.gif.png", "x"), "cat halloween small")
        self.assertEqual(util.friendly_name("My-Doorbell.PNG", "x"), "My Doorbell")
        self.assertEqual(util.friendly_name(None, "abc12345"), "abc12345")

    def test_is_sprite(self):
        self.assertTrue(util.is_sprite({"id": "x.png"}))
        self.assertFalse(util.is_sprite({"id": "x.png.gif"}))

    def test_find_preview(self):
        files = ["cat_halloween_small.gif", "other.png"]
        self.assertEqual(util.find_preview(files, "cat_halloween_small.gif.png"), "cat_halloween_small.gif")
        self.assertEqual(util.find_preview(["Cat_Hello_Small.AVIF"], "cat_hello_small.gif.png"), "Cat_Hello_Small.AVIF")
        self.assertIsNone(util.find_preview(files, "nope.gif.png"))

    def test_content_type(self):
        self.assertEqual(util.content_type("a.GIF"), "image/gif")
        self.assertEqual(util.content_type("a.avif"), "image/avif")


if __name__ == "__main__":
    unittest.main()
