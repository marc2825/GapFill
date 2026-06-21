import { useCallback, useRef } from 'react';
import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import type { Layer, Point } from '../types';
import type { ImagePreset } from '../config/presets';
import { createCanvas } from '../utils/canvasUtils';
import { LatestRequestTracker } from '../utils/latestRequestTracker';

interface UsePresetHandlersParams {
  setSelectedPreset: Dispatch<SetStateAction<string>>;
  setCurrentPresetConfig: Dispatch<SetStateAction<ImagePreset | null>>;
  setIsStarted: Dispatch<SetStateAction<boolean>>;
  setIsDone: Dispatch<SetStateAction<boolean>>;
  setTimeRemaining: Dispatch<SetStateAction<number | null>>;
  stopTimer: () => void;
  setLayers: Dispatch<SetStateAction<Layer[]>>;
  setReferenceImage: Dispatch<SetStateAction<string | null>>;
  resetHistory: () => void;
  setPan: Dispatch<SetStateAction<Point>>;
  setZoom: Dispatch<SetStateAction<number>>;
  setCanvasSize: Dispatch<SetStateAction<{ width: number; height: number }>>;
  setBlackLightMode: Dispatch<SetStateAction<boolean>>;
  setGapFillMode: Dispatch<SetStateAction<boolean>>;
  setActiveLayerId: Dispatch<SetStateAction<string | null>>;
  setIsPresetLoading: Dispatch<SetStateAction<boolean>>;
  isLoadingImageRef: MutableRefObject<boolean>;
  isLoadingGuidesRef: MutableRefObject<boolean>;
  isLoadingColoringRef: MutableRefObject<boolean>;
  manualFileLoadEpochRef: MutableRefObject<number>;
}

function usePresetHandlers({
  setSelectedPreset,
  setCurrentPresetConfig,
  setIsStarted,
  setIsDone,
  setTimeRemaining,
  stopTimer,
  setLayers,
  setReferenceImage,
  resetHistory,
  setPan,
  setZoom,
  setCanvasSize,
  setBlackLightMode,
  setGapFillMode,
  setActiveLayerId,
  setIsPresetLoading,
  isLoadingImageRef,
  isLoadingGuidesRef,
  isLoadingColoringRef,
  manualFileLoadEpochRef,
}: UsePresetHandlersParams) {
  const presetLoadTrackerRef = useRef(new LatestRequestTracker());

  const createBasicLayerStructure = useCallback(() => {
    const defaultCanvasSize = { width: 800, height: 600 };
    const layers: Layer[] = [];

    const coloringLayer: Layer = {
      id: `layer-coloring-${Date.now()}`,
      name: 'Coloring',
      canvas: createCanvas(defaultCanvasSize.width, defaultCanvasSize.height),
      visible: true,
      opacity: 1,
      order: 2,
    };
    layers.push(coloringLayer);

    const backgroundLayer: Layer = {
      id: 'background-layer',
      name: 'Background',
      canvas: createCanvas(defaultCanvasSize.width, defaultCanvasSize.height),
      visible: true,
      opacity: 1,
      order: 0,
    };
    const backgroundCtx = backgroundLayer.canvas.getContext('2d');
    if (backgroundCtx) {
      backgroundCtx.fillStyle = '#ffffff';
      backgroundCtx.fillRect(
        0,
        0,
        defaultCanvasSize.width,
        defaultCanvasSize.height,
      );
    }
    layers.push(backgroundLayer);

    setLayers(layers);
    setActiveLayerId(coloringLayer.id);
  }, [setActiveLayerId, setLayers]);

  const loadImageFromDataUrl = useCallback(
    (
      dataUrl: string,
      type: 'lineArt' | 'guides' | 'coloring',
      requestId: number,
    ): Promise<boolean> => new Promise((resolve, reject) => {
      // Implementation of Paper Sec. 5.1 Methodology:
      // presets build the study paint software state by loading task assets into
      // the Line Art / Guides / Coloring / Background layer structure used by Canvas.
      const img = new Image();
      img.onload = () => {
        if (!presetLoadTrackerRef.current.isCurrent(requestId)) {
          resolve(false);
          return;
        }

        if (type === 'lineArt') {
          const newCanvasSize = {
            width: img.width,
            height: img.height,
          };

          isLoadingImageRef.current = true;
          setCanvasSize(newCanvasSize);
          setPan({ x: 0, y: 0 });
          setZoom(1);

          const timestamp = Date.now();
          const coloringLayerId = `layer-coloring-${timestamp}`;
          setLayers(() => {
            const layers: Layer[] = [];

            const lineArtLayer: Layer = {
              id: `layer-lineart-${timestamp}`,
              name: 'Line Art',
              canvas: createCanvas(newCanvasSize.width, newCanvasSize.height),
              visible: true,
              opacity: 1,
              order: 3,
            };
            const lineArtCtx = lineArtLayer.canvas.getContext('2d');
            if (lineArtCtx) {
              lineArtCtx.imageSmoothingEnabled = false;
              lineArtCtx.drawImage(img, 0, 0);
            }
            layers.push(lineArtLayer);

            const coloringLayer: Layer = {
              id: coloringLayerId,
              name: 'Coloring',
              canvas: createCanvas(newCanvasSize.width, newCanvasSize.height),
              visible: true,
              opacity: 1,
              order: 2,
            };
            layers.push(coloringLayer);

            const backgroundLayer: Layer = {
              id: 'background-layer',
              name: 'Background',
              canvas: createCanvas(newCanvasSize.width, newCanvasSize.height),
              visible: true,
              opacity: 1,
              order: 0,
            };
            const backgroundCtx = backgroundLayer.canvas.getContext('2d');
            if (backgroundCtx) {
              backgroundCtx.fillStyle = '#ffffff';
              backgroundCtx.fillRect(0, 0, newCanvasSize.width, newCanvasSize.height);
            }
            layers.push(backgroundLayer);

            return layers;
          });
          setActiveLayerId(coloringLayerId);
        } else if (type === 'guides') {
          isLoadingGuidesRef.current = true;

          setCanvasSize((currentSize) => ({
            width: Math.max(img.width, currentSize.width),
            height: Math.max(img.height, currentSize.height),
          }));

          setLayers((prevLayers) => {
            const newLayers = [...prevLayers];
            const existingGuidesIndex = newLayers.findIndex((layer) => layer.name === 'Guides');

            const guidesLayer: Layer = {
              id: `layer-guides-${Date.now()}`,
              name: 'Guides',
              canvas: createCanvas(img.width, img.height),
              visible: true,
              opacity: 0.5,
              order: 1,
            };

            const ctx = guidesLayer.canvas.getContext('2d');
            if (ctx) {
              ctx.imageSmoothingEnabled = false;
              ctx.drawImage(img, 0, 0);
            }

            if (existingGuidesIndex !== -1) {
              newLayers[existingGuidesIndex] = guidesLayer;
            } else {
              newLayers.push(guidesLayer);
            }
            return newLayers.map((layer) => {
              let order = layer.order;
              if (layer.name === 'Line Art') order = 3;
              else if (layer.name === 'Coloring') order = 2;
              else if (layer.name === 'Guides') order = 1;
              else if (layer.name === 'Background') order = 0;
              return { ...layer, order };
            });
          });
        } else if (type === 'coloring') {
          isLoadingColoringRef.current = true;

          setCanvasSize((currentSize) => ({
            width: Math.max(img.width, currentSize.width),
            height: Math.max(img.height, currentSize.height),
          }));

          setLayers((prevLayers) => {
            const coloringIndex = prevLayers.findIndex((layer) => layer.name === 'Coloring');

            if (coloringIndex !== -1) {
              const newColoringLayer = {
                ...prevLayers[coloringIndex],
                canvas: createCanvas(img.width, img.height),
              };

              const ctx = newColoringLayer.canvas.getContext('2d');
              if (ctx) {
                ctx.imageSmoothingEnabled = false;
                ctx.drawImage(img, 0, 0);
              }

              const newLayers = [...prevLayers];
              newLayers[coloringIndex] = newColoringLayer;

              return newLayers;
            }

            console.warn('No Coloring layer found to replace');
            return prevLayers;
          });
        }

        resolve(true);
      };
      img.onerror = () => {
        reject(new Error(`Failed to load ${type} preset image: ${dataUrl}`));
      };
      img.src = dataUrl;
    }),
    [
      isLoadingColoringRef,
      isLoadingGuidesRef,
      isLoadingImageRef,
      setActiveLayerId,
      setCanvasSize,
      setLayers,
      setPan,
      setZoom,
    ],
  );

  const handlePresetChange = useCallback(
    async (preset: ImagePreset) => {
      const requestId = presetLoadTrackerRef.current.begin();
      manualFileLoadEpochRef.current++;
      isLoadingImageRef.current = false;
      isLoadingGuidesRef.current = false;
      isLoadingColoringRef.current = false;
      setIsPresetLoading(true);

      // Implementation of Paper Sec. 5.1 Methodology:
      // switching presets swaps experimental conditions: task images, reference image,
      // enabled tools, default GapFill state, and time limit are all configured here.
      setSelectedPreset(preset.id);
      setCurrentPresetConfig(preset);

      setIsStarted(false);
      setIsDone(false);
      setTimeRemaining(null);
      stopTimer();

      setLayers([]);
      setReferenceImage(null);
      resetHistory();

      setPan({ x: 0, y: 0 });
      setZoom(1);
      setCanvasSize({ width: 800, height: 600 });

      setBlackLightMode(false);

      if (preset.enableGapFillMode !== undefined) {
        setGapFillMode(preset.enableGapFillMode);
      }

      if (preset.defaultGapFillMode !== undefined) {
        setGapFillMode(preset.defaultGapFillMode);
      }

      if (preset.id !== 'debug') {
        if (preset.reference) {
          setReferenceImage(preset.reference);
        }

        try {
          if (preset.lineArt) {
            const loaded = await loadImageFromDataUrl(
              preset.lineArt,
              'lineArt',
              requestId,
            );
            if (!loaded) return;
          } else {
            if (!presetLoadTrackerRef.current.isCurrent(requestId)) return;
            createBasicLayerStructure();
          }

          if (preset.guides) {
            const loaded = await loadImageFromDataUrl(
              preset.guides,
              'guides',
              requestId,
            );
            if (!loaded) return;
          }
          if (preset.coloring) {
            await loadImageFromDataUrl(
              preset.coloring,
              'coloring',
              requestId,
            );
          }
        } catch (error) {
          if (presetLoadTrackerRef.current.isCurrent(requestId)) {
            console.error('Failed to load preset images:', error);
          }
        }
      } else if (presetLoadTrackerRef.current.isCurrent(requestId)) {
        createBasicLayerStructure();
      }

      if (presetLoadTrackerRef.current.isCurrent(requestId)) {
        setIsPresetLoading(false);
      }
    },
    [
      createBasicLayerStructure,
      isLoadingColoringRef,
      isLoadingGuidesRef,
      isLoadingImageRef,
      loadImageFromDataUrl,
      manualFileLoadEpochRef,
      resetHistory,
      setBlackLightMode,
      setCanvasSize,
      setCurrentPresetConfig,
      setGapFillMode,
      setIsPresetLoading,
      setIsDone,
      setIsStarted,
      setLayers,
      setPan,
      setReferenceImage,
      setSelectedPreset,
      setTimeRemaining,
      setZoom,
      stopTimer,
    ],
  );

  return {
    handlePresetChange,
  };
}

export default usePresetHandlers;
