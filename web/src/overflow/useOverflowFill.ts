import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { AddToHistory, BrushSettings, Layer, Point } from '../types';
import { detectGapRegionsForCanvas } from '../utils/GapFill/gapDetection';
import { ONNXModelLoadError } from '../utils/GapFill/onnxInference';
import { getOverflowOwnerAtPoint } from './ownerRegions';
import { paintOverflowOwner } from './paint';
import { precomputeOverflowLinks, toOverflowGaps } from './precompute';
import type {
  LastOverflowPropagation,
  OverflowAssignment,
  OverflowGap,
  OverflowOwnerRegion,
  OverflowPrecomputeData,
  OverflowPropagationFlash,
} from './types';

interface UseOverflowFillOptions {
  layers: Layer[];
  activeLayerId: string | null;
  enabled: boolean;
  gapThreshold: number;
  likelihoodThreshold: number;
  brushSettings: BrushSettings;
  historyIndex: number;
  onLayerUpdate: (layerId: string, canvas: HTMLCanvasElement) => void;
  onAddToHistory: AddToHistory;
  onStatusChange: (status: string) => void;
  onLinkedGapCountChange?: (count: number) => void;
}

export interface OverflowFillState {
  enabled: boolean;
  status: string;
  data: OverflowPrecomputeData | null;
  gaps: OverflowGap[];
  hoveredOwnerId: string | null;
  highlightedRegions: Point[][];
  propagationFlash: OverflowPropagationFlash | null;
  propagationSuppressed: boolean;
  handleHover: (point: Point) => void;
  handleBucketFill: (point: Point) => boolean;
  handleStandardBucketFill: () => void;
}

function findLayer(layers: Layer[], name: string): Layer | undefined {
  return layers.find((layer) => layer.name === name);
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

export function useOverflowFill({
  layers,
  activeLayerId,
  enabled,
  gapThreshold,
  likelihoodThreshold,
  brushSettings,
  historyIndex,
  onLayerUpdate,
  onAddToHistory,
  onStatusChange,
  onLinkedGapCountChange,
}: UseOverflowFillOptions): OverflowFillState {
  const [status, setStatus] = useState('Overflow Fill off');
  const [data, setData] = useState<OverflowPrecomputeData | null>(null);
  const [gaps, setGaps] = useState<OverflowGap[]>([]);
  const [hoveredOwnerId, setHoveredOwnerId] = useState<string | null>(null);
  const [propagationFlash, setPropagationFlash] =
    useState<OverflowPropagationFlash | null>(null);
  const [propagationSuppressed, setPropagationSuppressed] = useState(false);
  const requestRef = useRef(0);
  const flashIntervalRef = useRef<number | null>(null);
  const flashTimeoutRef = useRef<number | null>(null);
  const suppressedOwnerIdsRef = useRef<Set<string>>(new Set());
  const lastPropagationRef = useRef<LastOverflowPropagation | null>(null);
  const previousHistoryIndexRef = useRef(historyIndex);

  const setStatusBoth = useCallback((nextStatus: string) => {
    setStatus(nextStatus);
    onStatusChange(nextStatus);
  }, [onStatusChange]);

  const clearFlashTimers = useCallback(() => {
    if (flashIntervalRef.current !== null) {
      window.clearInterval(flashIntervalRef.current);
      flashIntervalRef.current = null;
    }
    if (flashTimeoutRef.current !== null) {
      window.clearTimeout(flashTimeoutRef.current);
      flashTimeoutRef.current = null;
    }
  }, []);

  const clearFlash = useCallback(() => {
    clearFlashTimers();
    setPropagationFlash(null);
  }, [clearFlashTimers]);

  const showFlash = useCallback((regions: Point[][]) => {
    if (regions.length === 0) {
      clearFlash();
      return;
    }

    clearFlashTimers();
    setPropagationFlash({ regions, visible: true });
    flashIntervalRef.current = window.setInterval(() => {
      setPropagationFlash((current) =>
        current ? { ...current, visible: !current.visible } : current,
      );
    }, 180);
    flashTimeoutRef.current = window.setTimeout(clearFlash, 1200);
  }, [clearFlash, clearFlashTimers]);

  useEffect(() => clearFlashTimers, [clearFlashTimers]);

  useEffect(() => {
    const previousIndex = previousHistoryIndexRef.current;
    previousHistoryIndexRef.current = historyIndex;

    if (!enabled || historyIndex >= previousIndex) return;

    const lastPropagation = lastPropagationRef.current;
    if (!lastPropagation) return;

    suppressedOwnerIdsRef.current.add(lastPropagation.ownerId);
    setPropagationSuppressed(true);
    lastPropagationRef.current = null;
    clearFlash();
    setStatusBoth('Undo detected. Retry fills the last owner without propagation.');
  }, [clearFlash, enabled, historyIndex, setStatusBoth]);

  useEffect(() => {
    const requestId = ++requestRef.current;
    const abortController = new AbortController();

    if (!enabled || !activeLayerId) {
      setData(null);
      setGaps([]);
      setHoveredOwnerId(null);
      suppressedOwnerIdsRef.current.clear();
      lastPropagationRef.current = null;
      setPropagationSuppressed(false);
      clearFlash();
      setStatusBoth('Overflow Fill off');
      onLinkedGapCountChange?.(0);
      return undefined;
    }

    const activeLayer = layers.find((layer) => layer.id === activeLayerId);
    const lineArtLayer = findLayer(layers, 'Line Art');
    const guidesLayer = findLayer(layers, 'Guides');

    if (!activeLayer || !lineArtLayer) {
      setData(null);
      setGaps([]);
      setHoveredOwnerId(null);
      setStatusBoth('Line Art and active Coloring layer are required.');
      onLinkedGapCountChange?.(0);
      return undefined;
    }

    setData(null);
    setHoveredOwnerId(null);
    setStatusBoth('Detecting overflow gaps...');

    const timer = window.setTimeout(async () => {
      try {
        const regions = await detectGapRegionsForCanvas(
          activeLayer.canvas,
          gapThreshold,
          lineArtLayer.canvas,
          guidesLayer?.canvas,
          abortController.signal,
        );
        if (requestRef.current !== requestId) return;

        const overflowGaps = toOverflowGaps(regions);
        setGaps(overflowGaps);

        if (overflowGaps.length === 0) {
          setData(null);
          onLinkedGapCountChange?.(0);
          setStatusBoth('No small gaps found.');
          return;
        }

        setStatusBoth(`Computing overflow owners: 0/${overflowGaps.length}`);
        const nextData = await precomputeOverflowLinks({
          gaps: overflowGaps,
          activeCanvas: activeLayer.canvas,
          lineArtCanvas: lineArtLayer.canvas,
          guidesCanvas: guidesLayer?.canvas,
          gapThreshold,
          signal: abortController.signal,
          onProgress: setStatusBoth,
        });
        if (requestRef.current !== requestId) return;

        setData(nextData);
        setStatusBoth(
          `Ready: ${nextData.assignments.length}/${overflowGaps.length} gaps linked to ${nextData.owners.length} owners.`,
        );
      } catch (error) {
        if (isAbortError(error) || requestRef.current !== requestId) return;

        console.error('Overflow Fill precompute failed:', error);
        setData(null);
        setGaps([]);
        setHoveredOwnerId(null);
        onLinkedGapCountChange?.(0);
        setStatusBoth(
          error instanceof ONNXModelLoadError
            ? error.message
            : 'Overflow Fill precompute failed.',
        );
      }
    }, 100);

    return () => {
      abortController.abort();
      window.clearTimeout(timer);
    };
  }, [
    activeLayerId,
    clearFlash,
    enabled,
    gapThreshold,
    layers,
    onLinkedGapCountChange,
    setStatusBoth,
  ]);

  useEffect(() => {
    if (!enabled || !data) {
      onLinkedGapCountChange?.(0);
      return;
    }

    const linkedGapIds = new Set<string>();
    for (const assignment of data.assignments) {
      if (assignment.confidence >= likelihoodThreshold) {
        linkedGapIds.add(assignment.gapId);
      }
    }
    onLinkedGapCountChange?.(linkedGapIds.size);
  }, [data, enabled, likelihoodThreshold, onLinkedGapCountChange]);

  const assignmentsForOwner = useCallback((ownerId: string): OverflowAssignment[] => {
    if (!data || suppressedOwnerIdsRef.current.has(ownerId)) return [];

    return data.assignments.filter(
      (assignment) =>
        assignment.ownerId === ownerId &&
        assignment.confidence >= likelihoodThreshold,
    );
  }, [data, likelihoodThreshold]);

  const linkedGapsForOwner = useCallback((ownerId: string): OverflowGap[] => {
    const gapById = new Map(gaps.map((gap) => [gap.id, gap]));
    return assignmentsForOwner(ownerId)
      .map((assignment) => gapById.get(assignment.gapId))
      .filter((gap): gap is OverflowGap => Boolean(gap));
  }, [assignmentsForOwner, gaps]);

  const highlightedRegions = useMemo(() => {
    if (!hoveredOwnerId) return [];
    return linkedGapsForOwner(hoveredOwnerId).map((gap) => gap.pixels);
  }, [hoveredOwnerId, linkedGapsForOwner]);

  const handleHover = useCallback((point: Point) => {
    if (!enabled || !data) {
      setHoveredOwnerId(null);
      return;
    }

    const owner = getOverflowOwnerAtPoint(data, point);
    setHoveredOwnerId(owner?.id ?? null);
  }, [data, enabled]);

  const clearSuppressionForOwner = useCallback((ownerId: string) => {
    if (!suppressedOwnerIdsRef.current.delete(ownerId)) return;
    setPropagationSuppressed(suppressedOwnerIdsRef.current.size > 0);
  }, []);

  const handleBucketFill = useCallback((point: Point): boolean => {
    if (!enabled) return false;
    if (!activeLayerId) return true;
    if (!data) {
      setStatusBoth(
        'Overflow Fill is still preparing. Please try again in a moment.',
      );
      return true;
    }

    const owner: OverflowOwnerRegion | null = getOverflowOwnerAtPoint(data, point);
    if (!owner) return false;

    const activeLayer = layers.find((layer) => layer.id === activeLayerId);
    if (!activeLayer) return true;

    const propagationWasSuppressed =
      suppressedOwnerIdsRef.current.has(owner.id);
    const linkedGaps = linkedGapsForOwner(owner.id);
    const result = paintOverflowOwner({
      canvas: activeLayer.canvas,
      owner,
      linkedGaps,
      clickPoint: point,
      fillColor: brushSettings.color,
    });

    clearSuppressionForOwner(owner.id);

    if (!result.changed) {
      lastPropagationRef.current = null;
      clearFlash();
      setStatusBoth(
        propagationWasSuppressed
          ? 'Filled owner only; propagation suppressed after undo.'
          : 'No linked gaps above threshold.',
      );
      return true;
    }

    onLayerUpdate(activeLayerId, activeLayer.canvas);
    onAddToHistory([activeLayerId]);

    if (result.propagatedGapIds.length > 0) {
      lastPropagationRef.current = {
        ownerId: owner.id,
        gapIds: result.propagatedGapIds,
      };
      showFlash(result.propagatedRegions);
    } else {
      lastPropagationRef.current = null;
      clearFlash();
    }

    setData(null);
    setHoveredOwnerId(null);
    setStatusBoth(
      propagationWasSuppressed
        ? 'Filled owner only; propagation suppressed after undo. Updating...'
        : result.usedExistingOwnerColor
          ? `Propagated owner color to ${result.propagatedGapIds.length} gaps. Updating...`
          : `Filled 1 owner + ${result.propagatedGapIds.length} gaps. Updating...`,
    );
    return true;
  }, [
    activeLayerId,
    brushSettings.color,
    clearFlash,
    clearSuppressionForOwner,
    data,
    enabled,
    layers,
    linkedGapsForOwner,
    onAddToHistory,
    onLayerUpdate,
    setStatusBoth,
    showFlash,
  ]);

  const handleStandardBucketFill = useCallback(() => {
    if (!enabled) return;
    lastPropagationRef.current = null;
    setData(null);
    setHoveredOwnerId(null);
    clearFlash();
    setStatusBoth('No overflow owner at click. Ran standard bucket fill. Updating...');
  }, [clearFlash, enabled, setStatusBoth]);

  return {
    enabled,
    status,
    data,
    gaps,
    hoveredOwnerId,
    highlightedRegions,
    propagationFlash,
    propagationSuppressed,
    handleHover,
    handleBucketFill,
    handleStandardBucketFill,
  };
}
