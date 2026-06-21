import { useCallback, useRef } from 'react';
import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import type { Layer } from '../types';
import type { ImagePreset } from '../config/presets';
import { createCanvas } from '../utils/canvasUtils';

interface UseSessionHandlersParams {
  isStarted: boolean;
  isDone: boolean;
  currentPresetConfig: ImagePreset | null;
  layers: Layer[];
  canvasSize: { width: number; height: number };
  timerRef: MutableRefObject<number | null>;
  setIsStarted: Dispatch<SetStateAction<boolean>>;
  setIsDone: Dispatch<SetStateAction<boolean>>;
  setTimeRemaining: Dispatch<SetStateAction<number | null>>;
}

function useSessionHandlers({
  isStarted,
  isDone,
  currentPresetConfig,
  layers,
  canvasSize,
  timerRef,
  setIsStarted,
  setIsDone,
  setTimeRemaining,
}: UseSessionHandlersParams) {
  const isDoneRef = useRef(isDone);
  const presetRef = useRef(currentPresetConfig);
  const layersRef = useRef(layers);
  const canvasSizeRef = useRef(canvasSize);

  isDoneRef.current = isDone;
  presetRef.current = currentPresetConfig;
  layersRef.current = layers;
  canvasSizeRef.current = canvasSize;

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, [timerRef]);

  const handleDone = useCallback(() => {
    if (isDoneRef.current) return;
    isDoneRef.current = true;

    // Implementation of Paper Sec. 5.1 Methodology:
    // Done finalizes a timed trial. Saving is opt-in and disabled by every preset.
    setIsDone(true);
    stopTimer();

    const preset = presetRef.current;
    const currentLayers = layersRef.current;
    const currentCanvasSize = canvasSizeRef.current;
    const autoSaveOnDone = preset?.autoSaveOnDone === true;

    if (autoSaveOnDone) {
      const taskName = preset?.name || 'unknown';
      const sanitizedTaskName = taskName.replace(/[^a-zA-Z0-9-_]/g, '_');
      const timestamp = Date.now();

      const coloringLayer = currentLayers.find(
        (layer) => layer.name === 'Coloring',
      );

      if (coloringLayer) {
        const coloringCanvas = createCanvas(
          currentCanvasSize.width,
          currentCanvasSize.height,
        );
        const coloringCtx = coloringCanvas.getContext('2d');

        if (coloringCtx) {
          coloringCtx.imageSmoothingEnabled = false;
          coloringCtx.drawImage(coloringLayer.canvas, 0, 0);
        }

        const coloringDataUrl = coloringCanvas.toDataURL('image/png');
        const coloringLink = document.createElement('a');
        coloringLink.download = `${sanitizedTaskName}_coloring_done_${timestamp}.png`;
        coloringLink.href = coloringDataUrl;
        coloringLink.click();
      } else {
        console.warn('Coloring layer not found');
      }
    }

  }, [setIsDone, stopTimer]);

  const handleStart = useCallback(() => {
    if (isStarted) return;

    // Implementation of Paper Sec. 5.1 Methodology:
    // Start begins the controlled session and arms the countdown timer used in the study UI.
    isDoneRef.current = false;
    setIsStarted(true);
    setIsDone(false);

    if (currentPresetConfig?.timeLimit) {
      setTimeRemaining(currentPresetConfig.timeLimit);

      timerRef.current = window.setInterval(() => {
        setTimeRemaining((prev) => {
          if (prev === null || prev <= 1) {
            stopTimer();
            handleDone();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
  }, [currentPresetConfig, handleDone, isStarted, setIsDone, setIsStarted, setTimeRemaining, stopTimer, timerRef]);

  return {
    handleStart,
    handleDone,
    stopTimer,
  };
}

export default useSessionHandlers;
