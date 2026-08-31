// ONNX Runtime Web client-side model inference for GapFill using a UNet-based color prediction model.

import * as ort from 'onnxruntime-web/wasm';
import type * as OrtType from 'onnxruntime-web';
import ortWasmModuleUrl from '../../../node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.mjs?url';
import { segmentColoredRegions, selectRegionColor } from './onnxPostprocessing';
import {
  assertMatchingCanvasDimensions,
  calculateCenteredPatchBounds,
  extractCanvasPatchWithBounds,
} from './onnxPatchExtraction';
import {
  buildGapMaskForPatch,
  excludeTargetGapFromGuides,
} from './onnxGapMask';
import { buildLegacyWebModelInput } from './webModelInput';
import { errorInDev, logInDev } from './devLog';
import { getValidatedProbabilityMap } from './onnxOutputValidation';

const MODEL_PATH = 'models/unet32.onnx';
const MODEL_PATCH_SIZE = 32;
const MODEL_INPUT_CHANNELS = 2;
const MODEL_OUTPUT_CHANNELS = 1;

interface PredictColorParams {
  lineArtCanvas: HTMLCanvasElement;
  guidesCanvas: HTMLCanvasElement;
  coloredCanvas: HTMLCanvasElement;
  gapCenter: { x: number; y: number };
  gapPixels?: Array<{ x: number; y: number }>;
  targetIsGuideGap?: boolean;
  fallbackColor: string;
}

export class ONNXModelLoadError extends Error {
  constructor(cause: unknown) {
    super(
      'Failed to load the AI color prediction model. GapFill is unavailable.',
      { cause },
    );
    this.name = 'ONNXModelLoadError';
  }
}

let modelSession: OrtType.InferenceSession | null = null;
let modelLoadPromise: Promise<OrtType.InferenceSession> | null = null;

function publicAsset(path: string): string {
  return `${import.meta.env?.BASE_URL ?? '/'}${path.replace(/^\/+/, '')}`;
}

// Let Vite serve the runtime module through its module pipeline. The WASM
// binary remains a static public asset so both development and builds use a
// stable URL.
ort.env.wasm.wasmPaths = {
  mjs: ortWasmModuleUrl,
  wasm: publicAsset('ort-wasm/ort-wasm-simd-threaded.wasm'),
};
ort.env.wasm.numThreads = globalThis.crossOriginIsolated
  ? navigator.hardwareConcurrency || 4
  : 1;
ort.env.wasm.simd = true;

// Load and reuse a single ONNX model session.
function loadModel(): Promise<OrtType.InferenceSession> {
  if (modelSession) {
    return Promise.resolve(modelSession);
  }

  if (modelLoadPromise) {
    return modelLoadPromise;
  }

  logInDev('Loading ONNX model...');
  modelLoadPromise = ort.InferenceSession.create(publicAsset(MODEL_PATH), {
    executionProviders: ['wasm'],
    graphOptimizationLevel: 'all',
    enableCpuMemArena: true,
    enableMemPattern: true,
    executionMode: 'sequential',
    interOpNumThreads: 1,
    intraOpNumThreads: 4,
  })
    .then((session) => {
      // Preserve the historical Web behavior: use the names exposed by the
      // loaded session instead of imposing the cross-host parity names here.
      modelSession = session;
      logInDev('ONNX model loaded successfully');
      return session;
    })
    .catch((error) => {
      modelSession = null;
      console.error('Failed to load ONNX model:', error);
      throw error instanceof ONNXModelLoadError
        ? error
        : new ONNXModelLoadError(error);
    })
    .finally(() => {
      modelLoadPromise = null;
    });

  return modelLoadPromise;
}

// Implementation of Paper Sec. 4.1.2 and 4.2.1:
// compute the suggested color shown by the Web UI using its historical
// pre-addon runtime behavior. The model was trained with Line-only channel 0;
// the Web product intentionally retains Line OR effective Guides for backward
// compatibility.
export async function predictColorWithONNX({
  lineArtCanvas,
  guidesCanvas,
  coloredCanvas,
  gapCenter,
  gapPixels,
  targetIsGuideGap = false,
  fallbackColor,
}: PredictColorParams): Promise<string> {
  try {
    assertMatchingCanvasDimensions(
      lineArtCanvas,
      guidesCanvas,
      coloredCanvas,
    );

    const session = modelSession || (await loadModel());
    const { x: cx, y: cy } = gapCenter;
    const patchBounds = calculateCenteredPatchBounds(
      coloredCanvas.width,
      coloredCanvas.height,
      cx,
      cy,
      MODEL_PATCH_SIZE,
    );

    // Keep the target gap at patch coordinate (16, 16), including near canvas
    // edges, and zero-pad every part of the virtual patch outside each canvas.
    const lineImageData = extractCanvasPatchWithBounds(
      lineArtCanvas,
      patchBounds,
      MODEL_PATCH_SIZE,
    );
    const guidesImageData = extractCanvasPatchWithBounds(
      guidesCanvas,
      patchBounds,
      MODEL_PATCH_SIZE,
    );
    const coloredImageData = extractCanvasPatchWithBounds(
      coloredCanvas,
      patchBounds,
      MODEL_PATCH_SIZE,
    );

    const gapMask = buildGapMaskForPatch(
      coloredImageData,
      patchBounds,
      { x: cx, y: cy },
      gapPixels,
    );
    const inputData = buildLegacyWebModelInput(
      lineImageData,
      guidesImageData,
      gapMask,
      targetIsGuideGap,
    );

    const inputTensor = new ort.Tensor('float32', inputData, [
      1,
      MODEL_INPUT_CHANNELS,
      MODEL_PATCH_SIZE,
      MODEL_PATCH_SIZE,
    ]);
    const inputName = session.inputNames[0];
    const outputName = session.outputNames[0];
    const outputMap = await session.run({ [inputName]: inputTensor });
    const outputTensor = outputMap[outputName];
    if (!outputTensor) {
      throw new Error('ONNX inference failed: no output tensor');
    }
    const probMap = getValidatedProbabilityMap(
      outputTensor.data,
      outputTensor.dims,
      [1, MODEL_OUTPUT_CHANNELS, MODEL_PATCH_SIZE, MODEL_PATCH_SIZE],
    );

    // Preserve the historical patch-local, color-sensitive segmentation.
    // Line Art and effective Guides split regions before the highest-mean
    // probability region supplies its modal RGB.
    const effectiveGuidesImageData = targetIsGuideGap
      ? excludeTargetGapFromGuides(guidesImageData, gapMask)
      : guidesImageData;
    const segmentation = segmentColoredRegions(
      coloredImageData,
      lineImageData,
      effectiveGuidesImageData,
    );
    const [r, g, b] = selectRegionColor(
      coloredImageData,
      segmentation.labels,
      segmentation.regionCount,
      probMap,
      fallbackColor,
    );

    return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
  } catch (error) {
    errorInDev('ONNX inference error:', error);
    throw error;
  }
}

// Ensure model-loading errors remain visible to the caller instead of being
// mistaken for an ordinary prediction fallback.
export async function ensureONNXModelAvailable(): Promise<void> {
  await loadModel();
}

// Preload the model to avoid loading latency during the first prediction.
export async function preloadModel(): Promise<void> {
  await loadModel();
}
