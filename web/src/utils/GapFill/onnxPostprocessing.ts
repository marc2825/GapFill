import { resolveGapFillFallbackRgb } from './gapFillColors.ts';

interface PixelImage {
  data: Uint8ClampedArray;
  width: number;
  height: number;
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

const DEFAULT_COLOR_TOLERANCE = 30;

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
