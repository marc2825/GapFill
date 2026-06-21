import unittest

import numpy as np
from gapfill_krita.engine.patches import build_model_patches, centered_patch_bounds, extract_patch
from gapfill_krita.engine.types import GapKind, GapRegion, LayerImages


class PatchTests(unittest.TestCase):
    def test_edge_patch_uses_zero_padding_matching_training(self):
        image = np.full((10, 10, 4), 255, dtype=np.uint8)
        bounds = centered_patch_bounds(10, 10, (1, 1), 32)
        patch = extract_patch(image, bounds, 32)
        self.assertEqual((bounds.destination_x, bounds.destination_y), (15, 15))
        self.assertTrue(np.all(patch.rgba[:15] == 0))
        self.assertTrue(np.all(patch.rgba[:, :15] == 0))
        self.assertTrue(np.all(patch.rgba[15:25, 15:25] == 255))

    def test_target_guide_is_removed_from_boundary_channel(self):
        coloring = np.zeros((40, 40, 4), dtype=np.uint8)
        line = np.zeros_like(coloring)
        guides = np.zeros_like(coloring)
        guides[20, 20, 3] = 255
        gap = GapRegion("gap-0", np.array([20 * 40 + 20]), (20, 20), GapKind.GUIDE)
        _, _, guide_patch, gap_mask = build_model_patches(LayerImages(coloring, line, guides), gap)
        self.assertEqual(float(gap_mask.sum()), 1.0)
        self.assertEqual(int(guide_patch.rgba[..., 3].sum()), 0)


if __name__ == "__main__":
    unittest.main()
