import unittest

import numpy as np
from gapfill_krita.engine.postprocessing import segment_colored_regions, select_region_color


class PostprocessingTests(unittest.TestCase):
    def test_selects_modal_color_of_highest_mean_region(self):
        coloring = np.zeros((4, 4, 4), dtype=np.uint8)
        coloring[:, :2] = (255, 0, 0, 255)
        coloring[:, 2:] = (0, 0, 255, 255)
        line = np.zeros_like(coloring)
        guides = np.zeros_like(coloring)
        line[:, 2, 3] = 255
        labels, count = segment_colored_regions(coloring, line, guides)
        probabilities = np.zeros((4, 4), dtype=np.float32)
        probabilities[:, :2] = 0.9
        probabilities[:, 3] = 0.1
        self.assertEqual(select_region_color(coloring, labels, count, probabilities), (255, 0, 0))


if __name__ == "__main__":
    unittest.main()
