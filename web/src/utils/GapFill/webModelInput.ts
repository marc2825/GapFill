import { excludeTargetGapFromGuides } from './onnxGapMask.ts';
import type { PixelPatch } from './onnxPatchExtraction';

export function buildLegacyWebModelInput(
  linePatch: PixelPatch,
  guidesPatch: PixelPatch,
  gapMask: Float32Array,
  targetIsGuideGap: boolean,
): Float32Array {
  if (
    linePatch.width !== guidesPatch.width ||
    linePatch.height !== guidesPatch.height
  ) {
    throw new Error('Line Art and Guide patches must have matching dimensions.');
  }
  const pixelCount = linePatch.width * linePatch.height;
  if (
    linePatch.data.length !== pixelCount * 4 ||
    guidesPatch.data.length !== pixelCount * 4 ||
    gapMask.length !== pixelCount
  ) {
    throw new Error('Web model input patches have inconsistent sizes.');
  }

  const effectiveGuides = targetIsGuideGap
    ? excludeTargetGapFromGuides(guidesPatch, gapMask)
    : guidesPatch;
  const tensor = new Float32Array(pixelCount * 2);
  for (let index = 0; index < pixelCount; index++) {
    const rgbaIndex = index * 4;
    tensor[index] =
      linePatch.data[rgbaIndex + 3] > 0 ||
      effectiveGuides.data[rgbaIndex + 3] > 0
        ? 1
        : 0;
    tensor[pixelCount + index] = gapMask[index];
  }
  return tensor;
}
