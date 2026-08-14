// ONNX Runtime Web client-side model inference for GapFill using a UNet-based color prediction model.

import * as ort from 'onnxruntime-web/wasm';
import type * as OrtType from 'onnxruntime-web';
import ortWasmModuleUrl from '../../../node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.mjs?url';
import {
  buildCanonicalModelInput,
  canonicalBoundaryMask,
  segmentLineRegions,
  selectCanonicalRegion,
} from './onnxPostprocessing';
import {
  assertMatchingCanvasDimensions,
  calculateCenteredPatchBounds,
  extractCanvasPatchWithBounds,
} from './onnxPatchExtraction';
import { buildGapMaskForPatch } from './onnxGapMask';
import { errorInDev, logInDev } from './devLog';
import { getValidatedProbabilityMap } from './onnxOutputValidation';

const MODEL_PATH = 'models/unet32.onnx';
const MODEL_PATCH_SIZE = 32;
const MODEL_INPUT_CHANNELS = 2;
const MODEL_OUTPUT_CHANNELS = 1;

interface PredictColorParams {
  lineArtCanvas: HTMLCanvasElement;
  coloredCanvas: HTMLCanvasElement;
  gapCenter: { x: number; y: number };
  gapPixels?: Array<{ x: number; y: number }>;
  semanticLabels?: Int32Array;
}

export interface LearnedColorPrediction {
  color: string;
  confidence: number;
  regionLabel: number;
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
    intraOpNumThreads: 4 // Use multiple threads for operations
  })
    .then((session) => {
      if (
        session.inputNames.length !== 1 ||
        session.inputNames[0] !== 'input_mask' ||
        session.outputNames.length !== 1 ||
        session.outputNames[0] !== 'nearest_region_mask'
      ) {
        throw new Error(
          'GapFill model contract mismatch: expected input_mask and nearest_region_mask.',
        );
      }
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
// compute the suggested color shown by the UI using region correspondence.
export async function predictColorWithONNX({
  lineArtCanvas,
  coloredCanvas,
  gapCenter,
  gapPixels,
  semanticLabels,
}: PredictColorParams): Promise<LearnedColorPrediction> {
  try {
    assertMatchingCanvasDimensions(
      lineArtCanvas,
      coloredCanvas,
    );

    const session = modelSession || await loadModel();
    
    const { x: cx, y: cy } = gapCenter;
    const patchBounds = calculateCenteredPatchBounds(
      coloredCanvas.width,
      coloredCanvas.height,
      cx,
      cy,
      MODEL_PATCH_SIZE,
    );

    // Implementation of Paper Sec. 4.1.2 and 4.2.1:
    // keep the target gap at patch coordinate (16, 16), including near canvas
    // edges, and zero-pad every part of the virtual patch outside each canvas.
    const lineImageData = extractCanvasPatchWithBounds(
      lineArtCanvas,
      patchBounds,
      MODEL_PATCH_SIZE,
    );
    const coloredImageData = extractCanvasPatchWithBounds(
      coloredCanvas,
      patchBounds,
      MODEL_PATCH_SIZE,
    );
    
    // Create binary masks
    const patchPixelCount = MODEL_PATCH_SIZE * MODEL_PATCH_SIZE;
    const gapMask = buildGapMaskForPatch(
      coloredImageData,
      patchBounds,
      { x: cx, y: cy },
      gapPixels,
    );
    // Phase 5 intentionally keeps Guides out of the model. Training supplied
    // Line Art only; Guide-composed tensors are characterized but out of
    // distribution. Guides remain detection boundaries in the calling stage.
    const inputData = buildCanonicalModelInput(
      canonicalBoundaryMask(lineImageData),
      gapMask,
    );
    
    const inputTensor = new ort.Tensor('float32', inputData, [
      1,
      MODEL_INPUT_CHANNELS,
      MODEL_PATCH_SIZE,
      MODEL_PATCH_SIZE,
    ]);
    
    // Run inference
    const feeds: Record<string, OrtType.Tensor> = {};
    const inputName = session.inputNames[0];
    feeds[inputName] = inputTensor;
    
    // console.log('ONNX Model inference:', {
    //   inputName,
    //   inputShape: inputTensor.dims,
    //   gapCenter,
    //   patchBounds: {
    //     xStart: patchBounds.virtualX,
    //     yStart: patchBounds.virtualY,
    //     size: patchSize
    //   }
    // });
    
    const outputMap = await session.run(feeds);
    const outputName = session.outputNames[0];
    const outputTensor = outputMap[outputName];
    
    if (!outputTensor) {
      throw new Error('ONNX inference failed: no output tensor');
    }
    const probMap = getValidatedProbabilityMap(
      outputTensor.data,
      outputTensor.dims,
      [1, MODEL_OUTPUT_CHANNELS, MODEL_PATCH_SIZE, MODEL_PATCH_SIZE],
    );
    
    // console.log('ONNX Model output:', {
    //   outputName,
    //   outputShape: outputTensor.dims,
    //   probMapLength: probMap.length,
    //   probMapSample: [probMap[0], probMap[100], probMap[500]].map(v => v?.toFixed(3))
    // });
    
    let fullLabels = semanticLabels;
    if (!fullLabels) {
      const fullLineContext = lineArtCanvas.getContext('2d');
      if (!fullLineContext) {
        throw new Error('Failed to read Line Art for semantic regions.');
      }
      const fullLine = fullLineContext.getImageData(
        0,
        0,
        lineArtCanvas.width,
        lineArtCanvas.height,
      );
      fullLabels = segmentLineRegions(fullLine).labels;
    }
    if (fullLabels.length !== coloredCanvas.width * coloredCanvas.height) {
      throw new Error('Full semantic label map has the wrong dimensions.');
    }
    const patchLabels = new Int32Array(patchPixelCount);
    for (let y = 0; y < patchBounds.sourceHeight; y++) {
      for (let x = 0; x < patchBounds.sourceWidth; x++) {
        const sourceIndex =
          (patchBounds.sourceY + y) * coloredCanvas.width +
          patchBounds.sourceX + x;
        const patchIndex =
          (patchBounds.destinationY + y) * MODEL_PATCH_SIZE +
          patchBounds.destinationX + x;
        patchLabels[patchIndex] = fullLabels[sourceIndex];
      }
    }
    const selection = selectCanonicalRegion(
      coloredImageData,
      patchLabels,
      probMap,
    );
    const [r, g, b] = selection.rgb;
    
    // Convert to hex
    const hexColor = `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
    
    // console.log('ONNX Model prediction result:', {
    //   predictedColor: hexColor,
    //   rgb: { r, g, b },
    //   gapCenter,
    //   fallbackColor
    // });
    
    return {
      color: hexColor,
      confidence: selection.meanProbability,
      regionLabel: selection.label,
    };
    
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
