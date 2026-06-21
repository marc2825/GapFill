import { useEffect, useRef, useState } from 'react';
import type { Layer } from '../../types';
import type { GapFillRegion } from '../../types/GapFill';
import { detectGaps } from '../../utils/GapFill/gapDetection';
import { fillGapRegions } from '../../utils/GapFill/gapFillApplication';
import { ONNXModelLoadError } from '../../utils/GapFill/onnxInference';

interface UseGapDetectionOptions {
  layers: Layer[];
  activeLayerId: string | null;
  gapFillMode: boolean;
  gapFillThreshold: number;
  fallbackColor: string;
  onGapsChange?: (gaps: GapFillRegion[]) => void;
}

interface GapDetectionResult {
  gaps: GapFillRegion[];
  precomputedGapCanvas: HTMLCanvasElement | null;
  error: string | null;
}

export function useGapDetection({
  layers,
  activeLayerId,
  gapFillMode,
  gapFillThreshold,
  fallbackColor,
  onGapsChange,
}: UseGapDetectionOptions): GapDetectionResult {
  const [gaps, setGaps] = useState<GapFillRegion[]>([]);
  const [precomputedGapCanvas, setPrecomputedGapCanvas] =
    useState<HTMLCanvasElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef(0);

  useEffect(() => {
    const requestId = ++requestRef.current;
    const abortController = new AbortController();
    let cancelled = false;
    setError(null);

    if (!gapFillMode || !activeLayerId) {
      setGaps([]);
      onGapsChange?.([]);
      setPrecomputedGapCanvas(null);
      return;
    }

    const activeLayer = layers.find((layer) => layer.id === activeLayerId);
    if (!activeLayer) return;

    // Implementation of Paper Sec. 4.1.1 and 4.1.2:
    // detect transparent isolated small regions (below threshold), predict each color, and prepare the temporary overlay.
    const timer = window.setTimeout(async () => {
      const lineArtLayer = layers.find((layer) => layer.name === 'Line Art');
      const guidesLayer = layers.find((layer) => layer.name === 'Guides');

      try {
        // Detect against the Coloring canvas itself. Line Art and Guides are
        // passed separately so boundaries and transparent Coloring pixels
        // above Guides do not overwrite the Coloring transparency information.
        const detectedGaps = await detectGaps(
          activeLayer.canvas,
          gapFillThreshold,
          lineArtLayer?.canvas,
          guidesLayer?.canvas,
          fallbackColor,
          abortController.signal,
        );

        if (cancelled || requestRef.current !== requestId) return;

        setGaps(detectedGaps);
        setError(null);
        onGapsChange?.(detectedGaps);

        if (detectedGaps.length === 0) {
          setPrecomputedGapCanvas(null);
          return;
        }

        const gapCanvas = document.createElement('canvas');
        gapCanvas.width = activeLayer.canvas.width;
        gapCanvas.height = activeLayer.canvas.height;
        const context = gapCanvas.getContext('2d');

        if (!context) {
          setPrecomputedGapCanvas(null);
          return;
        }

        context.imageSmoothingEnabled = false;
        context.drawImage(activeLayer.canvas, 0, 0);
        fillGapRegions(gapCanvas, detectedGaps);
        setPrecomputedGapCanvas(gapCanvas);
      } catch (error) {
        if (cancelled || requestRef.current !== requestId) return;
        if (error instanceof DOMException && error.name === 'AbortError') return;
        console.error('Gap detection failed:', error);
        setGaps([]);
        onGapsChange?.([]);
        setPrecomputedGapCanvas(null);
        setError(
          error instanceof ONNXModelLoadError
            ? error.message
            : 'Gap detection failed. Please try again.',
        );
      }
    }, 100);

    return () => {
      cancelled = true;
      abortController.abort();
      window.clearTimeout(timer);
    };
  }, [
    activeLayerId,
    fallbackColor,
    gapFillMode,
    gapFillThreshold,
    layers,
    onGapsChange,
  ]);

  return { gaps, precomputedGapCanvas, error };
}
