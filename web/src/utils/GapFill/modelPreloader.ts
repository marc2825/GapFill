// Model preloader utility for avoiding first-prediction loading latency.

import { preloadModel } from './onnxInference';
import { logInDev } from './devLog';
import { createModelInitializer } from './modelInitializer';

// Preload the ONNX model when the app starts.
export const initializeModel = createModelInitializer({
  preload: preloadModel,
  onStart: () => logInDev('Initializing ONNX model...'),
  onSuccess: () => logInDev('Model preloaded successfully'),
  onError: (error) => console.warn('Model preloading failed:', error),
});
