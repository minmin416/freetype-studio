"""Render the project's own tiny BDF font; no proprietary fonts required."""

import base64
import io
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

import server


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = server.add_font(Path(__file__).parent / "fixtures" / "tiny.bdf")[0]
        cls.size = cls.font["sizes"][0]

    def render(self, **settings):
        return server.render(
            {
                "font": self.font["id"],
                "size": self.size,
                "text": "AB",
                "padding": 0,
                **settings,
            }
        )

    def image(self, result):
        return Image.open(io.BytesIO(base64.b64decode(result["png"])))

    def test_embedded_pixels_are_loaded(self):
        result = self.render(text="A")
        image = self.image(result)
        self.assertTrue(result["bitmap"])
        self.assertEqual(image.size, (6, 8))
        self.assertEqual(
            [image.getpixel((x, 0))[3] for x in range(5)], [0, 255, 255, 255, 0]
        )
        self.assertEqual([image.getpixel((x, 3))[3] for x in range(5)], [255] * 5)

    def test_missing_strike_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "비트맵"):
            self.render(size=160)

    def test_missing_character_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "C"):
            self.render(text="C")

    def test_svg_and_png_pixels_match_after_width_changes(self):
        ns = {"s": "http://www.w3.org/2000/svg"}
        for stretch in (25, 75, 100, 150, 300):
            with self.subTest(stretch=stretch):
                result = self.render(stretch=stretch, padding=2)
                image = self.image(result)
                svg = ET.fromstring(result["svg"])
                self.assertEqual(
                    (int(svg.get("width")), int(svg.get("height"))), image.size
                )
                raster = Image.new("L", image.size)
                for rect in svg.findall("s:g/s:rect", ns):
                    x, y = int(rect.get("x")), int(rect.get("y"))
                    for column in range(x, x + int(rect.get("width"))):
                        raster.putpixel((column, y), 255)
                self.assertEqual(raster.tobytes(), image.getchannel("A").tobytes())

    def test_integer_scale_preserves_pixels(self):
        original = self.image(self.render())
        scaled = self.image(self.render(scale=4))
        self.assertEqual(
            scaled.tobytes(),
            original.resize(
                (original.width * 4, original.height * 4), Image.Resampling.NEAREST
            ).tobytes(),
        )

    def test_tracking_changes_width(self):
        self.assertEqual(self.render(tracking=3)["width"], self.render()["width"] + 3)

    def test_white_background_is_opaque(self):
        self.assertEqual(
            set(self.image(self.render(background="white")).getchannel("A").getdata()),
            {255},
        )

    def test_invalid_settings_are_rejected(self):
        for settings in (
            {"stretch": 0},
            {"stretch": 301},
            {"scale": 0},
            {"color": "invalid"},
        ):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.render(**settings)


if __name__ == "__main__":
    unittest.main()
