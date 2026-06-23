import type { Point } from '../types';
import type { OverflowOwnerRegion } from './types';

interface BuildOwnerRegionsParams {
  width: number;
  height: number;
  minArea: number;
  lineArtCanvas?: HTMLCanvasElement;
  guidesCanvas?: HTMLCanvasElement;
}

interface AlphaSource {
  data: Uint8ClampedArray;
}

function getAlphaSource(
  canvas: HTMLCanvasElement | undefined,
  width: number,
  height: number,
): AlphaSource | null {
  if (!canvas) return null;
  if (canvas.width !== width || canvas.height !== height) {
    throw new Error('Overflow owner canvases must have matching dimensions.');
  }

  const context = canvas.getContext('2d');
  if (!context) return null;
  return { data: context.getImageData(0, 0, width, height).data };
}

function alphaAt(source: AlphaSource | null, pixelIndex: number): number {
  return source?.data[pixelIndex * 4 + 3] ?? 0;
}

function calculateCenter(points: Point[]): Point {
  let sumX = 0;
  let sumY = 0;

  for (const point of points) {
    sumX += point.x;
    sumY += point.y;
  }

  return {
    x: Math.round(sumX / points.length),
    y: Math.round(sumY / points.length),
  };
}

// Overflow owner regions are the large connected regions separated by clean
// binary Line Art and Guides. Smaller components are left unlabelled so they
// cannot become owners for propagated gap fills.
export function buildOverflowOwnerRegions({
  width,
  height,
  minArea,
  lineArtCanvas,
  guidesCanvas,
}: BuildOwnerRegionsParams): {
  owners: OverflowOwnerRegion[];
  ownerLabels: Int32Array;
} {
  const pixelCount = width * height;
  const lineArt = getAlphaSource(lineArtCanvas, width, height);
  const guides = getAlphaSource(guidesCanvas, width, height);
  const visited = new Uint8Array(pixelCount);
  const ownerLabels = new Int32Array(pixelCount);
  const stack = new Uint32Array(pixelCount);
  const owners: OverflowOwnerRegion[] = [];

  const isBlocked = (pixelIndex: number) =>
    alphaAt(lineArt, pixelIndex) > 0 || alphaAt(guides, pixelIndex) > 0;

  for (let startIndex = 0; startIndex < pixelCount; startIndex++) {
    if (visited[startIndex] !== 0 || isBlocked(startIndex)) {
      visited[startIndex] = 1;
      continue;
    }

    let stackLength = 0;
    let minX = width;
    let minY = height;
    let maxX = -1;
    let maxY = -1;
    const regionPixels: Point[] = [];

    visited[startIndex] = 1;
    stack[stackLength++] = startIndex;

    while (stackLength > 0) {
      const pixelIndex = stack[--stackLength];
      const x = pixelIndex % width;
      const y = Math.floor(pixelIndex / width);

      regionPixels.push({ x, y });
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);

      const visit = (neighborIndex: number) => {
        if (
          visited[neighborIndex] !== 0 ||
          isBlocked(neighborIndex)
        ) {
          visited[neighborIndex] = 1;
          return;
        }

        visited[neighborIndex] = 1;
        stack[stackLength++] = neighborIndex;
      };

      if (x > 0) visit(pixelIndex - 1);
      if (x + 1 < width) visit(pixelIndex + 1);
      if (y > 0) visit(pixelIndex - width);
      if (y + 1 < height) visit(pixelIndex + width);
    }

    if (regionPixels.length < minArea) continue;

    const label = owners.length + 1;
    for (const point of regionPixels) {
      ownerLabels[point.y * width + point.x] = label;
    }

    owners.push({
      id: `owner-${label}`,
      label,
      pixels: regionPixels,
      center: calculateCenter(regionPixels),
      boundingBox: {
        x: minX,
        y: minY,
        width: maxX - minX + 1,
        height: maxY - minY + 1,
      },
      area: regionPixels.length,
    });
  }

  return { owners, ownerLabels };
}

export function getOverflowOwnerAtPoint(
  data: {
    owners: OverflowOwnerRegion[];
    ownerLabels: Int32Array;
    width: number;
    height: number;
  } | null,
  point: Point,
): OverflowOwnerRegion | null {
  if (!data) return null;

  const x = Math.round(point.x);
  const y = Math.round(point.y);
  if (x < 0 || y < 0 || x >= data.width || y >= data.height) return null;

  const label = data.ownerLabels[y * data.width + x];
  if (label <= 0) return null;
  return data.owners.find((owner) => owner.label === label) ?? null;
}
