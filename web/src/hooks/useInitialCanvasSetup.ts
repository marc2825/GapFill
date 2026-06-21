import { useEffect, useRef } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { Layer } from '../types';
import { createCanvas } from '../utils/canvasUtils';

interface UseInitialCanvasSetupParams {
  layers: Layer[];
  canvasSize: { width: number; height: number };
  isPresetLoading: boolean;
  setLayers: Dispatch<SetStateAction<Layer[]>>;
  setActiveLayerId: Dispatch<SetStateAction<string | null>>;
  initializeHistory: (layers: Layer[]) => void;
}

function useInitialCanvasSetup({
  layers,
  canvasSize,
  isPresetLoading,
  setLayers,
  setActiveLayerId,
  initializeHistory,
}: UseInitialCanvasSetupParams) {
  const isInitializedRef = useRef(false);

  useEffect(() => {
    if (isInitializedRef.current || isPresetLoading) return;
    isInitializedRef.current = true;
    if (layers.length > 0) return;

    const backgroundCanvas = createCanvas(canvasSize.width, canvasSize.height);
    const backgroundCtx = backgroundCanvas.getContext('2d');
    if (backgroundCtx) {
      backgroundCtx.fillStyle = '#ffffff';
      backgroundCtx.fillRect(0, 0, canvasSize.width, canvasSize.height);
    }

    const coloringCanvas = createCanvas(canvasSize.width, canvasSize.height);

    const initialLayers: Layer[] = [
      {
        id: 'background-layer',
        name: 'Background',
        canvas: backgroundCanvas,
        visible: true,
        opacity: 1,
        order: 0,
      },
      {
        id: 'coloring-layer',
        name: 'Coloring',
        canvas: coloringCanvas,
        visible: true,
        opacity: 1,
        order: 1,
      },
    ];

    setLayers(initialLayers);
    setActiveLayerId('coloring-layer');
    initializeHistory(initialLayers);
  }, [
    canvasSize,
    isPresetLoading,
    layers.length,
    initializeHistory,
    setActiveLayerId,
    setLayers,
  ]);
}

export default useInitialCanvasSetup;
