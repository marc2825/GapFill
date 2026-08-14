import unittest

import numpy as np
from gapfill_krita.engine.detection import detect_gap_regions
from gapfill_krita.engine.types import DetectionGeometry, GapKind, LayerImages


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

    def test_guide_is_a_boundary_not_a_paintable_component(self):
        coloring = empty_rgba()
        line = empty_rgba()
        guides = empty_rgba()
        guides[2, 2:7, 3] = 255
        guides[6, 2:7, 3] = 255
        guides[2:7, 2, 3] = 255
        guides[2:7, 6, 3] = 255
        guides[4, 4, 3] = 255

        gaps = detect_gap_regions(LayerImages(coloring, line, guides), 20)

        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].kind, GapKind.TRANSPARENT)
        self.assertNotIn(4 * 9 + 4, gaps[0].indices)

    def test_isolated_guide_in_open_space_is_not_a_gap(self):
        coloring = empty_rgba(5, 5)
        line = empty_rgba(5, 5)
        guides = empty_rgba(5, 5)
        guides[2, 2, 3] = 255

        self.assertEqual(detect_gap_regions(LayerImages(coloring, line, guides), 1), [])

    def test_selection_is_applied_after_full_component_geometry(self):
        coloring_gap = np.zeros((5, 5), dtype=np.bool_)
        coloring_gap[2, 1:4] = True
        selection = np.zeros((5, 5), dtype=np.bool_)
        selection[2, 2] = True
        geometry = DetectionGeometry(
            coloring_gap,
            np.zeros_like(coloring_gap),
            np.zeros_like(coloring_gap),
            selection,
        )

        gaps = detect_gap_regions(geometry, 3)

        self.assertEqual(gaps[0].indices.tolist(), [11, 12, 13])
        self.assertEqual(gaps[0].target_indices.tolist(), [12])

    def test_large_open_component_cancels_during_streaming_traversal(self):
        shape = (4096, 4096)
        geometry = DetectionGeometry(
            np.ones(shape, dtype=np.bool_),
            np.zeros(shape, dtype=np.bool_),
            np.zeros(shape, dtype=np.bool_),
        )
        self.assertEqual(detect_gap_regions(geometry, 10), [])
        polls = 0

        def cancel() -> bool:
            nonlocal polls
            polls += 1
            return polls == 8

        with self.assertRaises(InterruptedError):
            detect_gap_regions(geometry, 10, cancel_requested=cancel)

    def test_checkerboard_components_are_not_merged(self):
        y, x = np.indices((128, 128))
        coloring_gap = (x + y) % 2 == 0
        geometry = DetectionGeometry(
            coloring_gap,
            np.zeros_like(coloring_gap),
            np.zeros_like(coloring_gap),
        )

        gaps = detect_gap_regions(geometry, 1)

        expected = int(coloring_gap[1:-1, 1:-1].sum())
        self.assertEqual(len(gaps), expected)

    def test_threshold_excludes_larger_component(self):
        coloring = np.full((5, 5, 4), 255, dtype=np.uint8)
        coloring[1:4, 1:4, 3] = 0
        line = empty_rgba(5, 5)
        guides = empty_rgba(5, 5)
        self.assertEqual(detect_gap_regions(LayerImages(coloring, line, guides), 8), [])


if __name__ == "__main__":
    unittest.main()
