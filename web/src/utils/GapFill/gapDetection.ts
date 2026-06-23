import type { Point } from '../../types';
import type { GapFillRegion } from '../../types/GapFill';
import {
  ensureONNXModelAvailable,
  ONNXModelLoadError,
  predictColorWithONNX,
} from './onnxInference';
import {
  buildGapCandidateMap,
  findConnectedCandidateRegion,
  GUIDE_GAP_CANDIDATE,
} from './gapRegionDetection';
import {
  createOpaquePixelMask,
  predictColorGreedy,
} from './greedyColorPrediction';
import { resolveGapFillFallbackColor } from './gapFillColors.ts';
import { warnInDev } from './devLog';

const YIELD_EVERY_PIXELS = 0x40000;
const ABORT_CHECK_EVERY_PIXELS = 0x10000;
const YIELD_EVERY_GAP_REGIONS = 64;

export interface DetectedGapRegion {
  center: Point;
  pixels: Point[];
  kind: 'transparent' | 'guide';
}

interface PredictGapColorParams extends DetectedGapRegion {
  canvas: HTMLCanvasElement;
  sourcePixels: Uint8ClampedArray;
  width: number;
  height: number;
  excludedPixels?: Uint8Array;
  lineArtCanvas?: HTMLCanvasElement;
  guidesCanvas?: HTMLCanvasElement;
  fallbackColor: string;
  signal?: AbortSignal;
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException('Gap detection was aborted.', 'AbortError');
  }
}

function yieldPeriodically(
  pixelIndex: number,
  signal?: AbortSignal,
): Promise<void> | undefined {
  if ((pixelIndex & (ABORT_CHECK_EVERY_PIXELS - 1)) === 0) {
    throwIfAborted(signal);
  }

  if (
    pixelIndex === 0 ||
    (pixelIndex & (YIELD_EVERY_PIXELS - 1)) !== 0
  ) {
    return undefined;
  }

  return yieldToUiThread(signal);
}

function yieldToUiThread(signal?: AbortSignal): Promise<void> {
  return new Promise<void>((resolve) => window.setTimeout(resolve, 0)).then(() => {
    throwIfAborted(signal);
  });
}

async function detectGapRegions(
  candidates: Uint8Array,
  width: number,
  height: number,
  maxRegionSize: number,
  signal?: AbortSignal,
): Promise<DetectedGapRegion[]> {
  const pixelCount = width * height;
  const visited = new Uint8Array(pixelCount);
  const stack = new Uint32Array(pixelCount);
  const regions: DetectedGapRegion[] = [];

  for (let pixelIndex = 0; pixelIndex < pixelCount; pixelIndex++) {
    // Periodically yield to the UI thread and check for cancellation.
    const pendingYield = yieldPeriodically(pixelIndex, signal);
    if (pendingYield) await pendingYield;

    if (visited[pixelIndex] !== 0) continue;

    const candidateType = candidates[pixelIndex];
    if (candidateType === 0) continue;

    const pixelsInRegion = findConnectedCandidateRegion(
      candidates,
      width,
      height,
      pixelIndex,
      candidateType,
      maxRegionSize,
      visited,
      stack,
    );

    if (pixelsInRegion) {
      regions.push({
        center: calculateCenter(pixelsInRegion),
        pixels: pixelsInRegion,
        kind:
          candidateType === GUIDE_GAP_CANDIDATE
            ? 'guide'
            : 'transparent',
      });
    }
  }

  throwIfAborted(signal);
  return regions;
}

function buildGapCandidates(
  pixels: Uint8ClampedArray,
  width: number,
  height: number,
  lineArtCanvas?: HTMLCanvasElement,
  guidesCanvas?: HTMLCanvasElement,
): Uint8Array {
  const lineArtMask = createOpaquePixelMask(width, height, [lineArtCanvas]);
  const guidesMask = createOpaquePixelMask(width, height, [guidesCanvas]);
  return buildGapCandidateMap(
    pixels,
    lineArtMask,
    guidesMask,
  );
}

async function detectGapRegionsFromPixels(
  pixels: Uint8ClampedArray,
  width: number,
  height: number,
  threshold: number,
  lineArtCanvas?: HTMLCanvasElement,
  guidesCanvas?: HTMLCanvasElement,
  signal?: AbortSignal,
): Promise<DetectedGapRegion[]> {
  const candidates = buildGapCandidates(
    pixels,
    width,
    height,
    lineArtCanvas,
    guidesCanvas,
  );

  return detectGapRegions(
    candidates,
    width,
    height,
    Math.max(0, Math.floor(threshold)),
    signal,
  );
}

export async function detectGapRegionsForCanvas(
  canvas: HTMLCanvasElement,
  threshold: number,
  lineArtCanvas?: HTMLCanvasElement,
  guidesCanvas?: HTMLCanvasElement,
  signal?: AbortSignal,
): Promise<DetectedGapRegion[]> {
  throwIfAborted(signal);

  const context = canvas.getContext('2d');
  if (!context) return [];

  const { width, height } = canvas;
  const imageData = context.getImageData(0, 0, width, height);
  return detectGapRegionsFromPixels(
    imageData.data,
    width,
    height,
    threshold,
    lineArtCanvas,
    guidesCanvas,
    signal,
  );
}

async function predictGapColor({
  canvas,
  lineArtCanvas,
  guidesCanvas,
  fallbackColor,
  center,
  pixels,
  kind,
  signal,
}: PredictGapColorParams): Promise<string> {
  if (!lineArtCanvas) {
    throw new Error('Line Art canvas is unavailable.');
  }

  throwIfAborted(signal);
  const predictedColor = await predictColorWithONNX({
    lineArtCanvas,
    guidesCanvas: guidesCanvas || lineArtCanvas,
    coloredCanvas: canvas,
    gapCenter: center,
    gapPixels: pixels,
    targetIsGuideGap: kind === 'guide',
    fallbackColor,
  });
  throwIfAborted(signal);
  return predictedColor;
}

async function predictGapColorWithFallback(
  params: PredictGapColorParams,
): Promise<string> {
  if (params.lineArtCanvas) {
    try {
      return await predictGapColor(params);
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw error;
      }
      if (error instanceof ONNXModelLoadError) {
        throw error;
      }
      warnInDev('ONNX model prediction failed, using fallback:', error);
    }
  }

  return predictColorGreedy(
    params.sourcePixels,
    params.width,
    params.height,
    params.pixels,
    params.fallbackColor,
    params.excludedPixels,
  );
}

function warnAboutMissingLineArt(
  lineArtCanvas: HTMLCanvasElement | undefined,
): void {
  if (lineArtCanvas) return;
  warnInDev(
    'Line Art canvas is unavailable; using the temporary greedy fallback.',
  );
}

// Implementation of Paper Sec. 4.1.1:
// Identify connected transparent regions whose pixel count is at most threshold (= "small gaps").
// Possible extention: apply Trapped-ball segmentation for broken line-resistant region segmentation (cf. https://cg.cs.tsinghua.edu.cn/papers/tr080701.pdf)
export async function detectGaps(
  canvas: HTMLCanvasElement,
  threshold: number,
  lineArtCanvas?: HTMLCanvasElement,
  guidesCanvas?: HTMLCanvasElement,
  fallbackColor?: string,
  signal?: AbortSignal,
): Promise<GapFillRegion[]> {
  throwIfAborted(signal);

  const ctx = canvas.getContext('2d');
  if (!ctx) return [];

  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const pixels = imageData.data;
  const width = canvas.width;
  const height = canvas.height;
  const fallback = resolveGapFillFallbackColor(fallbackColor);
  const regions = await detectGapRegionsFromPixels(
    pixels,
    width,
    height,
    threshold,
    lineArtCanvas,
    guidesCanvas,
    signal,
  );

  if (regions.length === 0) return [];

  if (lineArtCanvas) {
    await ensureONNXModelAvailable();
  }
  throwIfAborted(signal);
  warnAboutMissingLineArt(lineArtCanvas);

  const excludedPixels = createOpaquePixelMask(
    width,
    height,
    [lineArtCanvas, guidesCanvas],
  );
  const gaps: GapFillRegion[] = [];

  // Implementation of Paper Sec. 4.1.2:
  // Attach a deep-learning-based suggested color to each detected gap.
  for (let regionIndex = 0; regionIndex < regions.length; regionIndex++) {
    if (
      regionIndex > 0 &&
      regionIndex % YIELD_EVERY_GAP_REGIONS === 0
    ) {
      await yieldToUiThread(signal);
    }

    const region = regions[regionIndex];
    const predictedColor = await predictGapColorWithFallback({
      ...region,
      canvas,
      sourcePixels: pixels,
      width,
      height,
      excludedPixels,
      lineArtCanvas,
      guidesCanvas,
      fallbackColor: fallback,
      signal,
    });

    gaps.push({
      id: `gap-${gaps.length}`,
      center: region.center,
      pixels: region.pixels,
      predictedColor,
    });
  }

  return gaps;
}

function calculateCenter(points: Point[]): Point {
  if (points.length === 0) {
    return { x: 0, y: 0 };
  }
  
  let sumX = 0;
  let sumY = 0;
  
  for (const point of points) {
    sumX += point.x;
    sumY += point.y;
  }
  
  return {
    // Region coordinates are nonnegative, so floor matches NumPy astype(int)
    // in the ML preprocessing pipeline.
    x: Math.floor(sumX / points.length),
    y: Math.floor(sumY / points.length)
  };
}
