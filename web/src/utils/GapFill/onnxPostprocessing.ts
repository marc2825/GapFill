import { resolveGapFillFallbackRgb } from './gapFillColors.ts';

interface PixelImage {
  data: Uint8ClampedArray;
  width: number;
  height: number;
  validPixels?: Uint8Array;
}

interface RegionSegmentation {
  labels: Int32Array;
  regionCount: number;
}

interface RgbColor {
  r: number;
  g: number;
  b: number;
}

export interface CanonicalRegionSelection {
  label: number;
  meanProbability: number;
  rgb: [number, number, number];
  pixelIndices: number[];
}

const DEFAULT_COLOR_TOLERANCE = 30;

const MODEL_PATCH_PIXELS = 32 * 32;

function pixelIsValid(image: PixelImage, pixelIndex: number): boolean {
  return !image.validPixels || image.validPixels[pixelIndex] !== 0;
}

// OpenCV-compatible fixed-point grayscale, followed by straight-alpha
// compositing over byte white.  The inclusive <=128 split is the exact ML
// training boundary rule; display/profile conversion remains a host concern.
export function canonicalBoundaryMask(image: PixelImage): Uint8Array {
  const pixelCount = image.width * image.height;
  if (image.data.length !== pixelCount * 4) {
    throw new Error('Canonical Line pixels do not match their dimensions.');
  }
  if (image.validPixels && image.validPixels.length !== pixelCount) {
    throw new Error('Canonical Line validity mask has the wrong length.');
  }

  const result = new Uint8Array(pixelCount);
  for (let pixelIndex = 0; pixelIndex < pixelCount; pixelIndex++) {
    if (!pixelIsValid(image, pixelIndex)) continue;
    const rgbaIndex = pixelIndex * 4;
    const red = image.data[rgbaIndex];
    const green = image.data[rgbaIndex + 1];
    const blue = image.data[rgbaIndex + 2];
    const alpha = image.data[rgbaIndex + 3];
    const luma =
      (red * 4899 + green * 9617 + blue * 1868 + 8192) >> 14;
    const composited = Math.floor(
      (luma * alpha + 255 * (255 - alpha) + 127) / 255,
    );
    result[pixelIndex] = composited <= 128 ? 1 : 0;
  }
  return result;
}

export function buildCanonicalModelInput(
  lineBoundary: Uint8Array,
  gapMask: Float32Array,
): Float32Array {
  if (
    lineBoundary.length !== MODEL_PATCH_PIXELS ||
    gapMask.length !== MODEL_PATCH_PIXELS
  ) {
    throw new Error('GapFill model input channels must each contain 32x32 values.');
  }
  const tensor = new Float32Array(MODEL_PATCH_PIXELS * 2);
  for (let index = 0; index < MODEL_PATCH_PIXELS; index++) {
    const boundary = lineBoundary[index];
    const target = gapMask[index];
    if ((boundary !== 0 && boundary !== 1) || (target !== 0 && target !== 1)) {
      throw new Error('GapFill model input channels must be binary.');
    }
    tensor[index] = boundary;
    tensor[MODEL_PATCH_PIXELS + index] = target;
  }
  return tensor;
}

export function segmentLineRegions(lineImage: PixelImage): RegionSegmentation {
  const { width, height } = lineImage;
  const pixelCount = width * height;
  const boundary = canonicalBoundaryMask(lineImage);
  const labels = new Int32Array(pixelCount);
  const queue = new Uint32Array(pixelCount);
  let regionCount = 0;

  for (let startIndex = 0; startIndex < pixelCount; startIndex++) {
    if (
      labels[startIndex] !== 0 ||
      boundary[startIndex] !== 0 ||
      !pixelIsValid(lineImage, startIndex)
    ) {
      continue;
    }
    const label = ++regionCount;
    let head = 0;
    let tail = 0;
    labels[startIndex] = label;
    queue[tail++] = startIndex;
    while (head < tail) {
      const pixelIndex = queue[head++];
      const x = pixelIndex % width;
      const y = Math.floor(pixelIndex / width);
      const visit = (neighbor: number) => {
        if (
          labels[neighbor] !== 0 ||
          boundary[neighbor] !== 0 ||
          !pixelIsValid(lineImage, neighbor)
        ) {
          return;
        }
        labels[neighbor] = label;
        queue[tail++] = neighbor;
      };
      if (x > 0) visit(pixelIndex - 1);
      if (x + 1 < width) visit(pixelIndex + 1);
      if (y > 0) visit(pixelIndex - width);
      if (y + 1 < height) visit(pixelIndex + width);
    }
  }
  return { labels, regionCount };
}

export function selectCanonicalRegion(
  coloredImage: PixelImage,
  labels: Int32Array,
  probabilityMap: Float32Array,
): CanonicalRegionSelection {
  const pixelCount = coloredImage.width * coloredImage.height;
  if (
    coloredImage.data.length !== pixelCount * 4 ||
    labels.length !== pixelCount ||
    probabilityMap.length !== pixelCount ||
    (coloredImage.validPixels && coloredImage.validPixels.length !== pixelCount)
  ) {
    throw new Error('Canonical postprocessing arrays must have matching dimensions.');
  }

  const labelOrder: number[] = [];
  const seen = new Set<number>();
  for (let pixelIndex = 0; pixelIndex < pixelCount; pixelIndex++) {
    const probability = probabilityMap[pixelIndex];
    if (!Number.isFinite(probability)) {
      throw new Error('Every model probability must be finite.');
    }
    if (probability < 0 || probability > 1) {
      throw new Error('Every model probability must be within [0, 1].');
    }
    const label = labels[pixelIndex];
    if (label < 0) throw new Error('Semantic labels must be nonnegative.');
    if (label > 0 && !seen.has(label)) {
      seen.add(label);
      labelOrder.push(label);
    }
  }

  let bestLabel = 0;
  let bestMean = -Infinity;
  for (const label of labelOrder) {
    let sum = 0;
    let area = 0;
    let painted = 0;
    for (let pixelIndex = 0; pixelIndex < pixelCount; pixelIndex++) {
      if (labels[pixelIndex] !== label || !pixelIsValid(coloredImage, pixelIndex)) {
        continue;
      }
      sum += probabilityMap[pixelIndex];
      area++;
      if (coloredImage.data[pixelIndex * 4 + 3] > 0) painted++;
    }
    if (area === 0 || painted === 0) continue;
    const mean = sum / area;
    if (mean > bestMean) {
      bestMean = mean;
      bestLabel = label;
    }
  }
  if (bestLabel === 0) {
    throw new Error('No painted semantic region is available for prediction.');
  }

  const counts = new Map<number, number>();
  const pixelIndices: number[] = [];
  for (let pixelIndex = 0; pixelIndex < pixelCount; pixelIndex++) {
    if (labels[pixelIndex] !== bestLabel || !pixelIsValid(coloredImage, pixelIndex)) {
      continue;
    }
    pixelIndices.push(pixelIndex);
    const rgbaIndex = pixelIndex * 4;
    if (coloredImage.data[rgbaIndex + 3] === 0) continue;
    const packed =
      (coloredImage.data[rgbaIndex] << 16) |
      (coloredImage.data[rgbaIndex + 1] << 8) |
      coloredImage.data[rgbaIndex + 2];
    counts.set(packed, (counts.get(packed) || 0) + 1);
  }

  let selectedColor = -1;
  let selectedCount = 0;
  for (const [packed, count] of counts) {
    if (count > selectedCount) {
      selectedColor = packed;
      selectedCount = count;
    }
  }
  if (selectedColor < 0) {
    throw new Error('The selected semantic region has no painted color.');
  }
  return {
    label: bestLabel,
    meanProbability: bestMean,
    rgb: unpackRgb(selectedColor),
    pixelIndices,
  };
}

function assertMatchingDimensions(
  coloredImage: PixelImage,
  lineArtImage: PixelImage,
  guidesImage: PixelImage,
): void {
  if (
    coloredImage.width !== lineArtImage.width ||
    coloredImage.height !== lineArtImage.height ||
    coloredImage.width !== guidesImage.width ||
    coloredImage.height !== guidesImage.height
  ) {
    throw new Error('ONNX postprocessing images must have matching dimensions.');
  }
}

function isSimilarColor(
  pixels: Uint8ClampedArray,
  pixelIndex: number,
  target: RgbColor,
  tolerance: number,
): boolean {
  const rgbaIndex = pixelIndex * 4;
  const difference =
    Math.abs(pixels[rgbaIndex] - target.r) +
    Math.abs(pixels[rgbaIndex + 1] - target.g) +
    Math.abs(pixels[rgbaIndex + 2] - target.b);
  return difference <= tolerance;
}

// Implementation of Paper Sec. 4.1.2 and 4.2.1:
// segment painted pixels without crossing Line Art or Guides so the predicted
// likelihood map selects a color from a valid neighboring painted region.
export function segmentColoredRegions(
  coloredImage: PixelImage,
  lineArtImage: PixelImage,
  guidesImage: PixelImage,
  colorTolerance = DEFAULT_COLOR_TOLERANCE,
): RegionSegmentation {
  assertMatchingDimensions(coloredImage, lineArtImage, guidesImage);

  const { width, height } = coloredImage;
  const pixelCount = width * height;
  const labels = new Int32Array(pixelCount);
  const blocked = new Uint8Array(pixelCount);
  const stack = new Uint32Array(pixelCount);
  let regionCount = 0;

  for (let pixelIndex = 0; pixelIndex < pixelCount; pixelIndex++) {
    const alphaIndex = pixelIndex * 4 + 3;
    blocked[pixelIndex] =
      coloredImage.data[alphaIndex] === 0 ||
      lineArtImage.data[alphaIndex] > 0 ||
      guidesImage.data[alphaIndex] > 0
        ? 1
        : 0;
  }

  for (let startIndex = 0; startIndex < pixelCount; startIndex++) {
    if (labels[startIndex] !== 0 || blocked[startIndex] !== 0) continue;

    const rgbaIndex = startIndex * 4;
    const targetColor = {
      r: coloredImage.data[rgbaIndex],
      g: coloredImage.data[rgbaIndex + 1],
      b: coloredImage.data[rgbaIndex + 2],
    };
    const label = ++regionCount;
    let stackLength = 0;

    labels[startIndex] = label;
    stack[stackLength++] = startIndex;

    while (stackLength > 0) {
      const pixelIndex = stack[--stackLength];
      const x = pixelIndex % width;
      const y = Math.floor(pixelIndex / width);

      const visitNeighbor = (neighborIndex: number) => {
        if (
          labels[neighborIndex] !== 0 ||
          blocked[neighborIndex] !== 0
        ) {
          return;
        }

        if (
          !isSimilarColor(
            coloredImage.data,
            neighborIndex,
            targetColor,
            colorTolerance,
          )
        ) {
          return;
        }

        labels[neighborIndex] = label;
        stack[stackLength++] = neighborIndex;
      };

      if (x > 0) visitNeighbor(pixelIndex - 1);
      if (x + 1 < width) visitNeighbor(pixelIndex + 1);
      if (y > 0) visitNeighbor(pixelIndex - width);
      if (y + 1 < height) visitNeighbor(pixelIndex + width);
    }
  }

  return { labels, regionCount };
}

function parseFallbackColor(fallbackColor: string): [number, number, number] {
  return resolveGapFillFallbackRgb(fallbackColor);
}

function unpackRgb(color: number): [number, number, number] {
  return [(color >> 16) & 0xff, (color >> 8) & 0xff, color & 0xff];
}

// Implementation of Paper Sec. 4.1.2 and 4.2.1:
// select the region with the highest mean ONNX probability, then return its
// most frequent RGB color as the suggested gap color.
export function selectRegionColor(
  coloredImage: PixelImage,
  labels: Int32Array,
  regionCount: number,
  probabilityMap: Float32Array,
  fallbackColor: string,
): [number, number, number] {
  const pixelCount = coloredImage.width * coloredImage.height;
  if (
    labels.length !== pixelCount ||
    probabilityMap.length < pixelCount ||
    regionCount <= 0
  ) {
    return parseFallbackColor(fallbackColor);
  }

  const probabilitySums = new Float64Array(regionCount + 1);
  const regionAreas = new Uint32Array(regionCount + 1);

  for (let pixelIndex = 0; pixelIndex < pixelCount; pixelIndex++) {
    const label = labels[pixelIndex];
    if (label <= 0 || label > regionCount) continue;

    const rgbaIndex = pixelIndex * 4;
    if (coloredImage.data[rgbaIndex + 3] === 0) continue;

    const probability = probabilityMap[pixelIndex];
    if (Number.isFinite(probability)) {
      probabilitySums[label] += probability;
    }
    regionAreas[label]++;
  }

  let bestLabel = 0;
  let bestProbability = -Infinity;

  for (let label = 1; label <= regionCount; label++) {
    if (regionAreas[label] === 0) continue;
    const meanProbability = probabilitySums[label] / regionAreas[label];
    if (meanProbability > bestProbability) {
      bestProbability = meanProbability;
      bestLabel = label;
    }
  }

  if (bestLabel === 0) return parseFallbackColor(fallbackColor);

  const colorCounts = new Map<number, number>();
  for (let pixelIndex = 0; pixelIndex < pixelCount; pixelIndex++) {
    if (labels[pixelIndex] !== bestLabel) continue;

    const rgbaIndex = pixelIndex * 4;
    if (coloredImage.data[rgbaIndex + 3] === 0) continue;

    const packedColor =
      (coloredImage.data[rgbaIndex] << 16) |
      (coloredImage.data[rgbaIndex + 1] << 8) |
      coloredImage.data[rgbaIndex + 2];
    colorCounts.set(packedColor, (colorCounts.get(packedColor) || 0) + 1);
  }

  let mostFrequentColor = -1;
  let highestCount = 0;
  for (const [color, count] of colorCounts) {
    if (count > highestCount) {
      highestCount = count;
      mostFrequentColor = color;
    }
  }

  return mostFrequentColor >= 0
    ? unpackRgb(mostFrequentColor)
    : parseFallbackColor(fallbackColor);
}
