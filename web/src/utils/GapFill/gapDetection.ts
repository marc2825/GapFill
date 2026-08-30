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
import { segmentLineRegions } from './onnxPostprocessing';

const YIELD_EVERY_PIXELS = 0x40000;
const ABORT_CHECK_EVERY_PIXELS = 0x10000;
const YIELD_EVERY_GAP_REGIONS = 64;

interface DetectedGapRegion {
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
  semanticLabels?: Int32Array;
  signal?: AbortSignal;
}

interface GapColorPrediction {
  predictedColor: string;
  predictionProvenance: 'learned' | 'fallback';
  learnedConfidence: number | null;
  fallbackReason?: string;
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

async function predictGapColor({
  canvas,
  lineArtCanvas,
  center,
  pixels,
  semanticLabels,
  signal,
}: PredictGapColorParams): Promise<GapColorPrediction> {
  if (!lineArtCanvas) {
    throw new Error('Line Art canvas is unavailable.');
  }

  throwIfAborted(signal);
  const learned = await predictColorWithONNX({
    lineArtCanvas,
    coloredCanvas: canvas,
    gapCenter: center,
    gapPixels: pixels,
    semanticLabels,
  });
  throwIfAborted(signal);
  return {
    predictedColor: learned.color,
    predictionProvenance: 'learned',
    learnedConfidence: learned.confidence,
  };
}

async function predictGapColorWithFallback(
  params: PredictGapColorParams,
): Promise<GapColorPrediction> {
  let fallbackReason = 'Line Art is unavailable.';
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
      fallbackReason = error instanceof Error ? error.message : String(error);
    }
  }

  return {
    predictedColor: predictColorGreedy(
      params.sourcePixels,
      params.width,
      params.height,
      params.pixels,
      params.fallbackColor,
      params.excludedPixels,
    ),
    predictionProvenance: 'fallback',
    learnedConfidence: null,
    fallbackReason,
  };
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
  const maxRegionSize = Math.max(0, Math.floor(threshold));
  const fallback = resolveGapFillFallbackColor(fallbackColor);
  const lineArtMask = createOpaquePixelMask(width, height, [lineArtCanvas]);
  const guidesMask = createOpaquePixelMask(width, height, [guidesCanvas]);
  const candidates = buildGapCandidateMap(
    pixels,
    lineArtMask,
    guidesMask,
  );
  const regions = await detectGapRegions(
    candidates,
    width,
    height,
    maxRegionSize,
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
  let semanticLabels: Int32Array | undefined;
  if (lineArtCanvas) {
    const lineContext = lineArtCanvas.getContext('2d');
    if (!lineContext) {
      throw new Error('Failed to read Line Art for semantic regions.');
    }
    semanticLabels = segmentLineRegions(
      lineContext.getImageData(0, 0, width, height),
    ).labels;
  }

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
    const prediction = await predictGapColorWithFallback({
      ...region,
      canvas,
      sourcePixels: pixels,
      width,
      height,
      excludedPixels,
      lineArtCanvas,
      guidesCanvas,
      fallbackColor: fallback,
      semanticLabels,
      signal,
    });

    gaps.push({
      id: `gap-${gaps.length}`,
      center: region.center,
      pixels: region.pixels,
      predictedColor: prediction.predictedColor,
      predictionProvenance: prediction.predictionProvenance,
      learnedConfidence: prediction.learnedConfidence,
      fallbackReason: prediction.fallbackReason,
    });
  }

  if (
    lineArtCanvas &&
    gaps.length > 0 &&
    gaps.every((gap) => gap.predictionProvenance === 'fallback')
  ) {
    throw new Error(
      `ONNX inference failed for every gap; heuristic fallback was not ` +
        `substituted for the batch: ${gaps[0].fallbackReason || 'unknown error'}`,
    );
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
