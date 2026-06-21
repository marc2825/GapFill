interface RegionPoint {
  x: number;
  y: number;
}

export const TRANSPARENT_GAP_CANDIDATE = 1;
export const GUIDE_GAP_CANDIDATE = 2;

// Keep ordinary transparent gaps and transparent Coloring pixels through
// which the lower Guide layer is visible as separate component types.
export function buildGapCandidateMap(
  coloredPixels: Uint8ClampedArray,
  lineArtMask?: Uint8Array,
  guidesMask?: Uint8Array,
): Uint8Array {
  const pixelCount = Math.floor(coloredPixels.length / 4);
  const candidates = new Uint8Array(pixelCount);

  for (let pixelIndex = 0; pixelIndex < pixelCount; pixelIndex++) {
    if (
      coloredPixels[pixelIndex * 4 + 3] !== 0 ||
      lineArtMask?.[pixelIndex] !== 0
    ) {
      continue;
    }

    candidates[pixelIndex] = guidesMask?.[pixelIndex]
      ? GUIDE_GAP_CANDIDATE
      : TRANSPARENT_GAP_CANDIDATE;
  }

  return candidates;
}

export function findConnectedCandidateRegion(
  candidates: Uint8Array,
  width: number,
  height: number,
  startIndex: number,
  candidateType: number,
  maxRegionSize: number,
  visited: Uint8Array,
  stack: Uint32Array,
): RegionPoint[] | null {
  const region: RegionPoint[] = [];
  let stackLength = 0;
  let exceedsThreshold = false;

  visited[startIndex] = 1;
  stack[stackLength++] = startIndex;

  while (stackLength > 0) {
    const pixelIndex = stack[--stackLength];
    const x = pixelIndex % width;
    const y = Math.floor(pixelIndex / width);

    if (!exceedsThreshold) {
      if (region.length < maxRegionSize) {
        region.push({ x, y });
      } else {
        region.length = 0;
        exceedsThreshold = true;
      }
    }

    const visitMatchingNeighbor = (neighborIndex: number) => {
      if (
        visited[neighborIndex] === 0 &&
        candidates[neighborIndex] === candidateType
      ) {
        visited[neighborIndex] = 1;
        stack[stackLength++] = neighborIndex;
      }
    };

    if (x > 0) visitMatchingNeighbor(pixelIndex - 1);
    if (x + 1 < width) visitMatchingNeighbor(pixelIndex + 1);
    if (y > 0) visitMatchingNeighbor(pixelIndex - width);
    if (y + 1 < height) visitMatchingNeighbor(pixelIndex + width);
  }

  return exceedsThreshold ? null : region;
}

// Implementation of Paper Sec. 4.1.1:
// traverse a transparent connected component and retain only regions at or
// below the user-adjustable pixel-count threshold.
export function findConnectedRegion(
  pixels: Uint8ClampedArray,
  width: number,
  height: number,
  startIndex: number,
  maxRegionSize: number,
  visited: Uint8Array,
  stack: Uint32Array,
): RegionPoint[] | null {
  const region: RegionPoint[] = [];
  let stackLength = 0;
  let exceedsThreshold = false;

  visited[startIndex] = 1;
  stack[stackLength++] = startIndex;

  while (stackLength > 0) {
    const pixelIndex = stack[--stackLength];
    const x = pixelIndex % width;
    const y = Math.floor(pixelIndex / width);

    if (!exceedsThreshold) {
      if (region.length < maxRegionSize) {
        region.push({ x, y });
      } else {
        region.length = 0;
        exceedsThreshold = true;
      }
    }

    const visitTransparentNeighbor = (neighborIndex: number) => {
      if (
        visited[neighborIndex] === 0 &&
        pixels[neighborIndex * 4 + 3] === 0
      ) {
        visited[neighborIndex] = 1;
        stack[stackLength++] = neighborIndex;
      }
    };

    if (x > 0) visitTransparentNeighbor(pixelIndex - 1);
    if (x + 1 < width) visitTransparentNeighbor(pixelIndex + 1);
    if (y > 0) visitTransparentNeighbor(pixelIndex - width);
    if (y + 1 < height) visitTransparentNeighbor(pixelIndex + width);
  }

  return exceedsThreshold ? null : region;
}
