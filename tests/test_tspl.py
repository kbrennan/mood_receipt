import io
import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import LABEL_H, LABEL_W, ROW_BYTES, SHEET_H, png_to_tspl


def png(image):
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


class PngToTspl(unittest.TestCase):
    def test_bitmap_has_white_as_one_and_black_as_zero(self):
        image = Image.new("RGB", (LABEL_W, LABEL_H), "white")
        # Top-left of the image: rotated 180 and centered, it lands on byte 99 of row 1208.
        image.paste("black", (6, 0, 14, 1))
        job = png_to_tspl(png(image))
        marker = b"BITMAP 0,0,102,1218,0,"
        start = job.index(marker) + len(marker)
        bitmap = job[start:start + ROW_BYTES * SHEET_H]
        row = bitmap[1208 * ROW_BYTES:1209 * ROW_BYTES]
        self.assertEqual(row[99], 0x00)
        self.assertEqual(row[98], 0xFF)
        self.assertEqual(row[100], 0xFF)
        self.assertEqual(bitmap[0], 0xFF)  # The padding is white.
        self.assertEqual(job[start + len(bitmap):], b"\r\nPRINT 1\r\n")

    def test_rejects_wrong_size(self):
        with self.assertRaises(ValueError):
            png_to_tspl(png(Image.new("L", (384, 800), 255)))

    def test_rejects_non_image(self):
        with self.assertRaises(ValueError):
            png_to_tspl(b"not a png")


if __name__ == "__main__":
    unittest.main()
