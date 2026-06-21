import { useCallback, useEffect, useRef, useState } from 'react';
import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import type { AddToHistory, Layer } from '../types';
import { createCanvas } from '../utils/canvasUtils';
import { appendHistoryEntry, redoHistory, undoHistory } from '../utils/historyStore';
import type { HistoryStore as StoredHistory } from '../utils/historyStore';
import { captureHistoryState, prepareHistoryCanvasBlobs } from '../utils/historySnapshot';
import type { HistoryLayer, HistoryState } from '../utils/historySnapshot';

function restoreHistoryLayer(historyLayer: HistoryLayer): Promise<Layer> {
  return new Promise((resolve) => {
    const canvas = createCanvas(historyLayer.width, historyLayer.height);
    const context = canvas.getContext('2d');
    const objectUrl = URL.createObjectURL(historyLayer.canvasBlob);
    const image = new Image();

    const finish = () => {
      URL.revokeObjectURL(objectUrl);
      resolve({
        id: historyLayer.id,
        name: historyLayer.name,
        visible: historyLayer.visible,
        opacity: historyLayer.opacity,
        order: historyLayer.order,
        canvas,
      });
    };

    image.onload = () => {
      context?.drawImage(image, 0, 0, historyLayer.width, historyLayer.height);
      finish();
    };
    image.onerror = finish;
    image.src = objectUrl;
  });
}

type HistoryStore = StoredHistory<HistoryState>;

interface UseHistoryManagerParams {
  layers: Layer[];
  setLayers: Dispatch<SetStateAction<Layer[]>>;
  isLoadingImageRef: MutableRefObject<boolean>;
  isLoadingGuidesRef: MutableRefObject<boolean>;
  isLoadingColoringRef: MutableRefObject<boolean>;
}

function useHistoryManager({
  layers,
  setLayers,
  isLoadingImageRef,
  isLoadingGuidesRef,
  isLoadingColoringRef,
}: UseHistoryManagerParams) {
  const [historyStore, setHistoryStore] = useState<HistoryStore>({
    entries: [],
    index: -1,
  });
  const historyStoreRef = useRef(historyStore);
  const historyQueueRef = useRef<Promise<void>>(Promise.resolve());
  const historyGenerationRef = useRef(0);
  const restoreRequestRef = useRef(0);
  const history = historyStore.entries;
  const historyIndex = historyStore.index;

  const replaceHistoryStore = useCallback((nextStore: HistoryStore) => {
    historyStoreRef.current = nextStore;
    setHistoryStore(nextStore);
  }, []);

  const appendHistoryState = useCallback((state: HistoryState) => {
    replaceHistoryStore(
      appendHistoryEntry(historyStoreRef.current, state),
    );
  }, [replaceHistoryStore]);

  const enqueueHistoryCapture = useCallback((
    sourceLayers: Layer[],
    replaceExistingHistory = false,
    changedLayerIds: readonly string[] = sourceLayers.map(
      (layer) => layer.id,
    ),
  ) => {
    const generation = historyGenerationRef.current;
    const changedLayerIdSet = new Set(changedLayerIds);
    const currentStore = historyStoreRef.current;
    const currentState = replaceExistingHistory
      ? null
      : currentStore.entries[currentStore.index] ?? null;
    const preparedBlobs = prepareHistoryCanvasBlobs(
      sourceLayers,
      currentState,
      changedLayerIdSet,
      replaceExistingHistory,
    );

    historyQueueRef.current = historyQueueRef.current.then(async () => {
      const latestStore = historyStoreRef.current;
      const previousState = replaceExistingHistory
        ? null
        : latestStore.entries[latestStore.index] ?? null;
      const result = await captureHistoryState(
        sourceLayers,
        previousState,
        changedLayerIdSet,
        preparedBlobs,
      ).then(
        (state) => ({ state, error: null }),
        (error: unknown) => ({ state: null, error }),
      );
      if (historyGenerationRef.current !== generation) return;

      if (result.error) {
        console.error('Failed to capture history state:', result.error);
        return;
      }

      if (result.state) {
        if (replaceExistingHistory) {
          replaceHistoryStore({
            entries: [result.state],
            index: 0,
          });
        } else {
          appendHistoryState(result.state);
        }
      }
    });
  }, [appendHistoryState, replaceHistoryStore]);

  const restoreState = useCallback(
    async (state: HistoryState, requestId: number) => {
      const restoredLayers = await Promise.all(
        state.layers.map(restoreHistoryLayer),
      );

      if (restoreRequestRef.current === requestId) {
        setLayers(restoredLayers);
      }
    },
    [setLayers],
  );

  const addToHistory: AddToHistory = useCallback((
    changedLayerIds,
    sourceLayers = layers,
  ) => {
    enqueueHistoryCapture(
      sourceLayers,
      false,
      changedLayerIds ?? sourceLayers.map((layer) => layer.id),
    );
  }, [enqueueHistoryCapture, layers]);

  const undo = useCallback(async () => {
    await historyQueueRef.current;

    const currentStore = historyStoreRef.current;
    const transition = undoHistory(currentStore);
    if (transition.entry) {
      const requestId = ++restoreRequestRef.current;

      replaceHistoryStore(transition.store);
      await restoreState(transition.entry, requestId);
    }
  }, [replaceHistoryStore, restoreState]);

  const redo = useCallback(async () => {
    await historyQueueRef.current;

    const currentStore = historyStoreRef.current;
    const transition = redoHistory(currentStore);
    if (transition.entry) {
      const requestId = ++restoreRequestRef.current;

      replaceHistoryStore(transition.store);
      await restoreState(transition.entry, requestId);
    }
  }, [replaceHistoryStore, restoreState]);

  const resetHistory = useCallback(() => {
    historyGenerationRef.current++;
    restoreRequestRef.current++;
    historyQueueRef.current = Promise.resolve();
    replaceHistoryStore({ entries: [], index: -1 });
  }, [replaceHistoryStore]);

  const initializeHistory = useCallback((initialLayers: Layer[]) => {
    historyGenerationRef.current++;
    restoreRequestRef.current++;
    historyQueueRef.current = Promise.resolve();
    replaceHistoryStore({ entries: [], index: -1 });
    enqueueHistoryCapture(
      initialLayers,
      true,
      initialLayers.map((layer) => layer.id),
    );
  }, [enqueueHistoryCapture, replaceHistoryStore]);

  useEffect(() => {
    if (
      (isLoadingImageRef.current || isLoadingGuidesRef.current || isLoadingColoringRef.current) &&
      layers.length > 0
    ) {
      const timer = setTimeout(() => {
        const changedLayerIds = isLoadingImageRef.current
          ? layers.map((layer) => layer.id)
          : layers
              .filter(
                (layer) =>
                  (isLoadingGuidesRef.current &&
                    layer.name === 'Guides') ||
                  (isLoadingColoringRef.current &&
                    layer.name === 'Coloring'),
              )
              .map((layer) => layer.id);
        enqueueHistoryCapture(layers, false, changedLayerIds);

        isLoadingImageRef.current = false;
        isLoadingGuidesRef.current = false;
        isLoadingColoringRef.current = false;
      }, 100);

      return () => clearTimeout(timer);
    }

    return undefined;
  }, [
    enqueueHistoryCapture,
    isLoadingColoringRef,
    isLoadingGuidesRef,
    isLoadingImageRef,
    layers,
  ]);

  return {
    history,
    historyIndex,
    initializeHistory,
    addToHistory,
    undo,
    redo,
    resetHistory,
  };
}

export default useHistoryManager;
