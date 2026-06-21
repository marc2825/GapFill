import unittest

import numpy as np
from gapfill_krita.engine.detection import detect_gap_regions
from gapfill_krita.engine.types import GapKind, LayerImages


def empty_rgba(width=9, height=9):
    return np.zeros((height, width, 4), dtype=np.uint8)


class DetectionTests(unittest.TestCase):
    def test_finds_only_enclosed_component(self):
        coloring = empty_rgba()
        line = empty_rgba()
        guides = empty_rgba()
        line[2, 2:7, 3] = 255
        line[6, 2:7, 3] = 255
        line[2:7, 2, 3] = 255
        line[2:7, 6, 3] = 255

        gaps = detect_gap_regions(LayerImages(coloring, line, guides), 100)

        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].pixel_count, 9)
        self.assertEqual(gaps[0].kind, GapKind.TRANSPARENT)
        self.assertEqual(gaps[0].center, (4, 4))

    def test_guide_pixels_are_an_independent_component(self):
        coloring = empty_rgba()
        line = empty_rgba()
        guides = empty_rgba()
        coloring[..., 3] = 255
        coloring[3:6, 3:6, 3] = 0
        guides[4, 4, 3] = 255

        gaps = detect_gap_regions(LayerImages(coloring, line, guides), 20)

        self.assertEqual(sorted(gap.kind for gap in gaps), [GapKind.GUIDE, GapKind.TRANSPARENT])
        guide_gap = next(gap for gap in gaps if gap.kind == GapKind.GUIDE)
        self.assertEqual(guide_gap.pixel_count, 1)

    def test_threshold_excludes_larger_component(self):
        coloring = np.full((5, 5, 4), 255, dtype=np.uint8)
        coloring[1:4, 1:4, 3] = 0
        line = empty_rgba(5, 5)
        guides = empty_rgba(5, 5)
        self.assertEqual(detect_gap_regions(LayerImages(coloring, line, guides), 8), [])


if __name__ == "__main__":
    unittest.main()
