import { useCallback, useRef } from 'react';
import type { ChangeEvent, Dispatch, MutableRefObject, RefObject, SetStateAction } from 'react';
import type { Layer, Point } from '../types';
import { createCanvas } from '../utils/canvasUtils';
import { isCurrentGenerationRequest, LatestRequestTracker } from '../utils/latestRequestTracker';

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function loadImage(dataUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('Failed to decode image file.'));
    image.src = dataUrl;
  });
}

interface UseFileHandlersParams {
  fileInputRef: RefObject<HTMLInputElement | null>;
  guidesInputRef: RefObject<HTMLInputElement | null>;
  coloringInputRef: RefObject<HTMLInputElement | null>;
  canvasSize: { width: number; height: number };
  setCanvasSize: Dispatch<SetStateAction<{ width: number; height: number }>>;
  setPan: Dispatch<SetStateAction<Point>>;
  setZoom: Dispatch<SetStateAction<number>>;
  setLayers: Dispatch<SetStateAction<Layer[]>>;
  setReferenceImage: Dispatch<SetStateAction<string | null>>;
  isLoadingImageRef: MutableRefObject<boolean>;
  isLoadingGuidesRef: MutableRefObject<boolean>;
  isLoadingColoringRef: MutableRefObject<boolean>;
  manualFileLoadEpochRef: MutableRefObject<number>;
}

function useFileHandlers({
  fileInputRef,
  guidesInputRef,
  coloringInputRef,
  canvasSize,
  setCanvasSize,
  setPan,
  setZoom,
  setLayers,
  setReferenceImage,
  isLoadingImageRef,
  isLoadingGuidesRef,
  isLoadingColoringRef,
  manualFileLoadEpochRef,
}: UseFileHandlersParams) {
  const imageLoadTrackerRef = useRef(new LatestRequestTracker());
  const guidesLoadTrackerRef = useRef(new LatestRequestTracker());
  const coloringLoadTrackerRef = useRef(new LatestRequestTracker());
  const referenceLoadTrackerRef = useRef(new LatestRequestTracker());

  const handleImageLoad = useCallback(() => {
    fileInputRef.current?.click();
  }, [fileInputRef]);

  const handleGuidesLoad = useCallback(() => {
    guidesInputRef.current?.click();
  }, [guidesInputRef]);

  const handleColoringLoad = useCallback(() => {
    coloringInputRef.current?.click();
  }, [coloringInputRef]);

  const handleImageFileSelect = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      event.target.value = '';

      const epoch = manualFileLoadEpochRef.current;
      const requestId = imageLoadTrackerRef.current.begin();
      const isCurrent = () =>
        isCurrentGenerationRequest(
          imageLoadTrackerRef.current,
          requestId,
          epoch,
          manualFileLoadEpochRef.current,
        );

      try {
        const dataUrl = await readFileAsDataUrl(file);
        if (!isCurrent()) return;
        const img = await loadImage(dataUrl);
        if (!isCurrent()) return;

        const newCanvasSize = {
          width: img.width,
          height: img.height,
        };

        setCanvasSize(newCanvasSize);

        setPan({ x: 0, y: 0 });
        setZoom(1);

        setLayers((prevLayers) => {
          if (!isCurrent()) return prevLayers;
          isLoadingImageRef.current = true;

          const existingLineArtIndex = prevLayers.findIndex(
            (layer) => layer.name === 'Line Art',
          );
          const updatedLayers = prevLayers.map((layer) => {
            const newCanvas = createCanvas(
              newCanvasSize.width,
              newCanvasSize.height,
            );
            const newCtx = newCanvas.getContext('2d');
            if (newCtx) {
              newCtx.imageSmoothingEnabled = false;

              if (layer.name === 'Background') {
                newCtx.fillStyle = '#ffffff';
                newCtx.fillRect(
                  0,
                  0,
                  newCanvasSize.width,
                  newCanvasSize.height,
                );
              }

              newCtx.drawImage(layer.canvas, 0, 0);
            }
            return { ...layer, canvas: newCanvas };
          });

          const existingLineArt =
            existingLineArtIndex >= 0
              ? updatedLayers[existingLineArtIndex]
              : null;
          const lineArtLayer: Layer = {
            id: existingLineArt?.id || `layer-lineart-${Date.now()}`,
            name: 'Line Art',
            canvas: createCanvas(
              newCanvasSize.width,
              newCanvasSize.height,
            ),
            visible: true,
            opacity: 1,
            order: existingLineArt?.order ?? 3,
          };

          const context = lineArtLayer.canvas.getContext('2d');
          if (context) {
            context.imageSmoothingEnabled = false;
            context.drawImage(img, 0, 0, img.width, img.height);
          }

          if (existingLineArtIndex >= 0) {
            updatedLayers[existingLineArtIndex] = lineArtLayer;
            return updatedLayers;
          }

          return [...updatedLayers, lineArtLayer];
        });
      } catch (error) {
        if (isCurrent()) {
          console.error('Failed to load Line Art image:', error);
        }
      }
    },
    [
      isLoadingImageRef,
      manualFileLoadEpochRef,
      setCanvasSize,
      setLayers,
      setPan,
      setZoom,
    ],
  );

  const handleGuidesFileSelect = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      event.target.value = '';

      const epoch = manualFileLoadEpochRef.current;
      const requestId = guidesLoadTrackerRef.current.begin();
      const isCurrent = () =>
        isCurrentGenerationRequest(
          guidesLoadTrackerRef.current,
          requestId,
          epoch,
          manualFileLoadEpochRef.current,
        );

      try {
        const dataUrl = await readFileAsDataUrl(file);
        if (!isCurrent()) return;
        const img = await loadImage(dataUrl);
        if (!isCurrent()) return;

        setLayers((prevLayers) => {
          if (!isCurrent()) return prevLayers;
          isLoadingGuidesRef.current = true;

          const existingGuidesIndex = prevLayers.findIndex(
            (layer) => layer.name === 'Guides',
          );
          const existingGuides =
            existingGuidesIndex >= 0
              ? prevLayers[existingGuidesIndex]
              : null;
          const targetLayer =
            prevLayers.find((layer) => layer.name === 'Coloring') ??
            prevLayers.find((layer) => layer.name === 'Line Art');
          const width = targetLayer?.canvas.width ?? canvasSize.width;
          const height = targetLayer?.canvas.height ?? canvasSize.height;

          const guidesLayer: Layer = {
            id: existingGuides?.id ?? `layer-guides-${Date.now()}`,
            name: 'Guides',
            canvas: createCanvas(width, height),
            visible: true,
            opacity: 0.5,
            order: 0,
          };

          const context = guidesLayer.canvas.getContext('2d');
          if (context) {
            context.imageSmoothingEnabled = false;
            context.drawImage(img, 0, 0);
          }

          const newLayers: Layer[] = [...prevLayers];

          if (existingGuidesIndex !== -1) {
            newLayers[existingGuidesIndex] = guidesLayer;
          } else {
            newLayers.push(guidesLayer);
          }

          return newLayers.map((layer) => {
            let newOrder = layer.order;
            if (layer.name === 'Line Art') newOrder = 3;
            else if (layer.name === 'Coloring') newOrder = 2;
            else if (layer.name === 'Guides') newOrder = 1;
            else if (layer.name === 'Background') newOrder = 0;
            return { ...layer, order: newOrder };
          });
        });
      } catch (error) {
        if (isCurrent()) {
          console.error('Failed to load Guides image:', error);
        }
      }
    },
    [
      canvasSize.height,
      canvasSize.width,
      isLoadingGuidesRef,
      manualFileLoadEpochRef,
      setLayers,
    ],
  );

  const handleColoringFileSelect = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      event.target.value = '';

      const epoch = manualFileLoadEpochRef.current;
      const requestId = coloringLoadTrackerRef.current.begin();
      const isCurrent = () =>
        isCurrentGenerationRequest(
          coloringLoadTrackerRef.current,
          requestId,
          epoch,
          manualFileLoadEpochRef.current,
        );

      try {
        const dataUrl = await readFileAsDataUrl(file);
        if (!isCurrent()) return;
        const img = await loadImage(dataUrl);
        if (!isCurrent()) return;

        setLayers((prevLayers) => {
          if (!isCurrent()) return prevLayers;

          const coloringIndex = prevLayers.findIndex(
            (layer) => layer.name === 'Coloring',
          );

          if (coloringIndex !== -1) {
            isLoadingColoringRef.current = true;
            const currentLayer = prevLayers[coloringIndex];
            const newColoringLayer = {
              ...currentLayer,
              canvas: createCanvas(
                currentLayer.canvas.width,
                currentLayer.canvas.height,
              ),
            };

            const context = newColoringLayer.canvas.getContext('2d');
            if (context) {
              context.imageSmoothingEnabled = false;
              context.drawImage(img, 0, 0);
            }

            const newLayers = [...prevLayers];
            newLayers[coloringIndex] = newColoringLayer;

            return newLayers;
          }

          console.warn('No Coloring layer found to replace');
          return prevLayers;
        });
      } catch (error) {
        if (isCurrent()) {
          console.error('Failed to load Coloring image:', error);
        }
      }
    },
    [
      isLoadingColoringRef,
      manualFileLoadEpochRef,
      setLayers,
    ],
  );

  const handleReferenceImageSelect = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      event.target.value = '';

      const epoch = manualFileLoadEpochRef.current;
      const requestId = referenceLoadTrackerRef.current.begin();
      const isCurrent = () =>
        isCurrentGenerationRequest(
          referenceLoadTrackerRef.current,
          requestId,
          epoch,
          manualFileLoadEpochRef.current,
        );

      try {
        const dataUrl = await readFileAsDataUrl(file);
        if (isCurrent()) {
          setReferenceImage(dataUrl);
        }
      } catch (error) {
        if (isCurrent()) {
          console.error('Failed to load reference image:', error);
        }
      }
    },
    [manualFileLoadEpochRef, setReferenceImage],
  );

  return {
    handleImageLoad,
    handleGuidesLoad,
    handleColoringLoad,
    handleImageFileSelect,
    handleGuidesFileSelect,
    handleColoringFileSelect,
    handleReferenceImageSelect,
  };
}

export default useFileHandlers;
