import unittest

import numpy as np
from gapfill_krita.engine.pixels import bgra_bytes_to_rgba


class PixelFormatTests(unittest.TestCase):
    def test_converts_krita_integer_rgba_channel_order(self):
        rgba = bgra_bytes_to_rgba(bytes((30, 20, 10, 40, 70, 60, 50, 80)), 2, 1)
        np.testing.assert_array_equal(
            rgba,
            np.array([[[10, 20, 30, 40], [50, 60, 70, 80]]], dtype=np.uint8),
        )

    def test_rejects_short_pixel_buffer(self):
        with self.assertRaises(RuntimeError):
            bgra_bytes_to_rgba(b"\x00\x00\x00", 1, 1)


if __name__ == "__main__":
    unittest.main()
