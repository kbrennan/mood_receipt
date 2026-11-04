import io
import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import LABEL_H, LABEL_W, png_to_tspl


def png(image):
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


class PngToTspl(unittest.TestCase):
    def test_bitmap_has_white_as_one_and_black_as_zero(self):
        image = Image.new("RGB", (LABEL_W, LABEL_H), "white")
        image.paste("black", (0, 0, 8, 1))  # First eight dots of the first row.
        job = png_to_tspl(png(image))
        start = job.index(b"BITMAP 6,9,100,1200,0,") + len(b"BITMAP 6,9,100,1200,0,")
        bitmap = job[start:start + 100 * 1200]
        self.assertEqual(bitmap[0], 0x00)
        self.assertEqual(bitmap[1], 0xFF)
        self.assertEqual(job[start + len(bitmap):], b"\r\nPRINT 1\r\n")

    def test_rejects_wrong_size(self):
        with self.assertRaises(ValueError):
            png_to_tspl(png(Image.new("L", (384, 800), 255)))

    def test_rejects_non_image(self):
        with self.assertRaises(ValueError):
            png_to_tspl(b"not a png")


if __name__ == "__main__":
    unittest.main()
