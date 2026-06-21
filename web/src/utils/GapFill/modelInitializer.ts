interface ModelInitializerOptions {
  preload: () => Promise<void>;
  onStart?: () => void;
  onSuccess?: () => void;
  onError?: (error: unknown) => void;
}

export function createModelInitializer({
  preload,
  onStart,
  onSuccess,
  onError,
}: ModelInitializerOptions): () => Promise<void> {
  let preloadPromise: Promise<void> | null = null;
  let isPreloaded = false;

  return function initializeModel(): Promise<void> {
    if (isPreloaded) return Promise.resolve();
    if (preloadPromise) return preloadPromise;

    onStart?.();
    preloadPromise = preload()
      .then(() => {
        isPreloaded = true;
        onSuccess?.();
      })
      .catch((error) => {
        onError?.(error);
      })
      .finally(() => {
        preloadPromise = null;
      });

    return preloadPromise;
  };
}
