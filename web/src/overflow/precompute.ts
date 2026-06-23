import type { Point } from '../types';
import type { DetectedGapRegion } from '../utils/GapFill/gapDetection';
import { predictProbabilityMapWithONNX } from '../utils/GapFill/onnxInference';
import type { ProbabilityMapInference } from '../utils/GapFill/onnxInference';
import { buildOverflowOwnerRegions } from './ownerRegions';
import type {
  OverflowAssignment,
  OverflowGap,
  OverflowPrecomputeData,
} from './types';

interface PrecomputeOverflowParams {
  gaps: OverflowGap[];
  activeCanvas: HTMLCanvasElement;
  lineArtCanvas: HTMLCanvasElement;
  guidesCanvas?: HTMLCanvasElement;
  gapThreshold: number;
  signal?: AbortSignal;
  onProgress?: (status: string) => void;
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException('Overflow fill was aborted.', 'AbortError');
  }
}

export function toOverflowGaps(regions: DetectedGapRegion[]): OverflowGap[] {
  return regions.map((region, index) => ({
    id: `overflow-gap-${index}`,
    center: region.center,
    pixels: region.pixels,
    kind: region.kind,
  }));
}

function createTargetGapMaskCanvas(
  width: number,
  height: number,
  gap: OverflowGap,
): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;

  const context = canvas.getContext('2d');
  if (!context) return canvas;

  context.imageSmoothingEnabled = false;
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, width, height);
  for (const point of gap.pixels) {
    context.clearRect(point.x, point.y, 1, 1);
  }

  return canvas;
}

function scoreOwnerFromProbabilityMap(
  inference: ProbabilityMapInference,
  ownerLabels: Int32Array,
  ownerCount: number,
  width: number,
  height: number,
): Omit<OverflowAssignment, 'gapId'> | null {
  const sums = new Float64Array(ownerCount + 1);
  const counts = new Uint32Array(ownerCount + 1);
  const { patchBounds, patchSize, probabilityMap } = inference;

  for (let localY = 0; localY < patchSize; localY++) {
    const globalY = patchBounds.virtualY + localY;
    if (globalY < 0 || globalY >= height) continue;

    for (let localX = 0; localX < patchSize; localX++) {
      const globalX = patchBounds.virtualX + localX;
      if (globalX < 0 || globalX >= width) continue;

      const label = ownerLabels[globalY * width + globalX];
      if (label <= 0 || label > ownerCount) continue;

      const probability = probabilityMap[localY * patchSize + localX] ?? 0;
      if (!Number.isFinite(probability)) continue;

      sums[label] += probability;
      counts[label]++;
    }
  }

  let bestLabel = 0;
  let bestConfidence = -Infinity;
  for (let label = 1; label <= ownerCount; label++) {
    if (counts[label] === 0) continue;

    const confidence = sums[label] / counts[label];
    if (confidence > bestConfidence) {
      bestConfidence = confidence;
      bestLabel = label;
    }
  }

  if (bestLabel === 0 || bestConfidence < 0) return null;
  return {
    ownerId: `owner-${bestLabel}`,
    confidence: bestConfidence,
  };
}

export async function precomputeOverflowLinks({
  gaps,
  activeCanvas,
  lineArtCanvas,
  guidesCanvas,
  gapThreshold,
  signal,
  onProgress,
}: PrecomputeOverflowParams): Promise<OverflowPrecomputeData> {
  throwIfAborted(signal);

  const width = activeCanvas.width;
  const height = activeCanvas.height;
  const minOwnerArea = Math.max(1, Math.floor(gapThreshold) + 1);
  const { owners, ownerLabels } = buildOverflowOwnerRegions({
    width,
    height,
    minArea: minOwnerArea,
    lineArtCanvas,
    guidesCanvas,
  });

  if (owners.length === 0 || gaps.length === 0) {
    return {
      owners,
      ownerLabels,
      width,
      height,
      assignments: [],
    };
  }

  const assignments: OverflowAssignment[] = [];
  for (let index = 0; index < gaps.length; index++) {
    throwIfAborted(signal);

    const gap = gaps[index];
    const targetGapMaskCanvas = createTargetGapMaskCanvas(width, height, gap);
    const inference = await predictProbabilityMapWithONNX({
      lineArtCanvas,
      guidesCanvas: guidesCanvas || lineArtCanvas,
      coloredCanvas: targetGapMaskCanvas,
      gapCenter: gap.center,
      gapPixels: gap.pixels,
      targetIsGuideGap: gap.kind === 'guide',
    });
    const scoredOwner = scoreOwnerFromProbabilityMap(
      inference,
      ownerLabels,
      owners.length,
      width,
      height,
    );

    if (scoredOwner) {
      assignments.push({
        ...scoredOwner,
        gapId: gap.id,
      });
    }

    if ((index + 1) % 5 === 0 || index + 1 === gaps.length) {
      onProgress?.(`Computing overflow owners: ${index + 1}/${gaps.length}`);
      await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
    }
  }

  return {
    owners,
    ownerLabels,
    width,
    height,
    assignments,
  };
}

export function pointsBoundingBox(points: Point[]): {
  x: number;
  y: number;
  width: number;
  height: number;
} | null {
  if (points.length === 0) return null;

  let minX = points[0].x;
  let maxX = points[0].x;
  let minY = points[0].y;
  let maxY = points[0].y;

  for (const point of points) {
    minX = Math.min(minX, point.x);
    maxX = Math.max(maxX, point.x);
    minY = Math.min(minY, point.y);
    maxY = Math.max(maxY, point.y);
  }

  return {
    x: minX,
    y: minY,
    width: maxX - minX + 1,
    height: maxY - minY + 1,
  };
}
