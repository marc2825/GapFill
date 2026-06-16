from __future__ import annotations

import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path

import cv2
import numpy as np

from src.utils.source_image_utils import load_visualization_source


class SourceImageUtilsTest(unittest.TestCase):
    def _write_image_pair(self, line_art_dir: Path, colored_dir: Path, filename: str, value: int) -> None:
        line_art = np.full((8, 8), 255, dtype=np.uint8)
        line_art[0, :] = 0
        line_art[:, 0] = 0
        colored = np.full((8, 8, 3), value, dtype=np.uint8)
        cv2.imwrite(str(line_art_dir / filename), line_art)
        cv2.imwrite(str(colored_dir / filename), colored)

    def test_visualization_source_cache_is_bounded_lru(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            line_art_dir = root / "line_art"
            colored_dir = root / "colored"
            line_art_dir.mkdir()
            colored_dir.mkdir()
            for index, filename in enumerate(("a.png", "b.png", "c.png")):
                self._write_image_pair(line_art_dir, colored_dir, filename, index + 1)

            cache = OrderedDict()
            load_visualization_source("a.png", str(line_art_dir), str(colored_dir), 128, cache, max_cache_size=2)
            load_visualization_source("b.png", str(line_art_dir), str(colored_dir), 128, cache, max_cache_size=2)
            load_visualization_source("a.png", str(line_art_dir), str(colored_dir), 128, cache, max_cache_size=2)
            load_visualization_source("c.png", str(line_art_dir), str(colored_dir), 128, cache, max_cache_size=2)

            self.assertEqual(list(cache.keys()), ["a.png", "c.png"])

    def test_visualization_source_can_disable_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            line_art_dir = root / "line_art"
            colored_dir = root / "colored"
            line_art_dir.mkdir()
            colored_dir.mkdir()
            self._write_image_pair(line_art_dir, colored_dir, "a.png", 1)

            cache = OrderedDict()
            source = load_visualization_source("a.png", str(line_art_dir), str(colored_dir), 128, cache, max_cache_size=0)

            self.assertIsNotNone(source)
            self.assertEqual(len(cache), 0)


if __name__ == "__main__":
    unittest.main()
