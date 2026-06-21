import type { PatchBounds, PixelPatch } from './onnxPatchExtraction';

interface Point {
  x: number;
  y: number;
}

function isTransparentValidPixel(patch: PixelPatch, pixelIndex: number): boolean {
  return patch.validPixels[pixelIndex] !== 0 && patch.data[pixelIndex * 4 + 3] === 0;
}

function markGapPixels(
  mask: Float32Array,
  patch: PixelPatch,
  patchBounds: PatchBounds,
  gapPixels: readonly Point[],
): void {
  const { width, height } = patch;

  gapPixels.forEach((point) => {
    const localX = point.x - patchBounds.virtualX;
    const localY = point.y - patchBounds.virtualY;
    if (localX < 0 || localX >= width || localY < 0 || localY >= height) return;

    const pixelIndex = localY * width + localX;
    if (isTransparentValidPixel(patch, pixelIndex)) {
      mask[pixelIndex] = 1.0;
    }
  });
}

function markConnectedGapAtCenter(
  mask: Float32Array,
  patch: PixelPatch,
  patchBounds: PatchBounds,
  gapCenter: Point,
): void {
  const { width, height } = patch;
  const startX = Math.round(gapCenter.x) - patchBounds.virtualX;
  const startY = Math.round(gapCenter.y) - patchBounds.virtualY;

  if (startX < 0 || startX >= width || startY < 0 || startY >= height) return;

  const startIndex = startY * width + startX;
  if (!isTransparentValidPixel(patch, startIndex)) return;

  const visited = new Uint8Array(width * height);
  const stack = new Uint32Array(width * height);
  let stackLength = 0;

  visited[startIndex] = 1;
  stack[stackLength++] = startIndex;

  while (stackLength > 0) {
    const pixelIndex = stack[--stackLength];
    const x = pixelIndex % width;
    const y = Math.floor(pixelIndex / width);
    mask[pixelIndex] = 1.0;

    const visitNeighbor = (neighborIndex: number) => {
      if (visited[neighborIndex] !== 0 || !isTransparentValidPixel(patch, neighborIndex)) return;
      visited[neighborIndex] = 1;
      stack[stackLength++] = neighborIndex;
    };

    if (x > 0) visitNeighbor(pixelIndex - 1);
    if (x + 1 < width) visitNeighbor(pixelIndex + 1);
    if (y > 0) visitNeighbor(pixelIndex - width);
    if (y + 1 < height) visitNeighbor(pixelIndex + width);
  }
}

export function buildGapMaskForPatch(
  coloredPatch: PixelPatch,
  patchBounds: PatchBounds,
  gapCenter: Point,
  gapPixels?: readonly Point[],
): Float32Array {
  const mask = new Float32Array(coloredPatch.width * coloredPatch.height);

  if (gapPixels) {
    markGapPixels(mask, coloredPatch, patchBounds, gapPixels);
  } else {
    markConnectedGapAtCenter(mask, coloredPatch, patchBounds, gapCenter);
  }

  return mask;
}

export function excludeTargetGapFromGuides(
  guidesPatch: PixelPatch,
  gapMask: Float32Array,
): PixelPatch {
  const pixelCount = guidesPatch.width * guidesPatch.height;
  if (gapMask.length !== pixelCount) {
    throw new Error('Guide patch and target gap mask must have matching sizes.');
  }

  const data = guidesPatch.data.slice();
  for (let pixelIndex = 0; pixelIndex < pixelCount; pixelIndex++) {
    if (gapMask[pixelIndex] > 0) {
      data[pixelIndex * 4 + 3] = 0;
    }
  }

  return { ...guidesPatch, data };
}
