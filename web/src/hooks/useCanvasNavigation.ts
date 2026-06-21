import { useCallback, useEffect, useState, type RefObject } from 'react';
import type { Point } from '../types';

interface UseCanvasNavigationOptions {
  canvasRef: RefObject<HTMLCanvasElement | null>;
  containerRef: RefObject<HTMLDivElement | null>;
  gapFillMode: boolean;
  screenMousePosition: Point | null;
  zoom: number;
  pan: Point;
  zoomStep: number;
  canvasSize: { width: number; height: number };
  onZoomChange: (zoom: number) => void;
  onPanChange: (pan: Point) => void;
  onToolChange: (tool: string) => void;
}

interface CanvasNavigationState {
  isCtrlBPressed: boolean;
  isSpacePressed: boolean;
  isZKeyPressed: boolean;
}

export function useCanvasNavigation({
  canvasRef,
  containerRef,
  gapFillMode,
  screenMousePosition,
  zoom,
  pan,
  zoomStep,
  canvasSize,
  onZoomChange,
  onPanChange,
  onToolChange,
}: UseCanvasNavigationOptions): CanvasNavigationState {
  const [isCtrlBPressed, setIsCtrlBPressed] = useState(false);
  const [isSpacePressed, setIsSpacePressed] = useState(false);
  const [isZKeyPressed, setIsZKeyPressed] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.key === 'b') {
        setIsCtrlBPressed(true);
        event.preventDefault();
      }
      if (event.code === 'Space' && !event.repeat) {
        setIsSpacePressed(true);
        event.preventDefault();
      }
      if (
        event.key.toLowerCase() === 'z' &&
        !event.repeat &&
        !event.ctrlKey &&
        !event.metaKey
      ) {
        setIsZKeyPressed(true);
        event.preventDefault();
      }

      if (
        event.key === '1' &&
        !event.ctrlKey &&
        !event.metaKey &&
        !event.altKey
      ) {
        const rect = containerRef.current?.getBoundingClientRect();
        if (rect && screenMousePosition) {
          const newZoom = Math.min(zoom * 1.2, 20);
          const clickX =
            screenMousePosition.x - rect.left - rect.width / 2;
          const clickY =
            screenMousePosition.y - rect.top - rect.height / 2;
          const scaleFactor = newZoom / zoom;
          onPanChange({
            x: clickX - (clickX - pan.x) * scaleFactor,
            y: clickY - (clickY - pan.y) * scaleFactor,
          });
          onZoomChange(newZoom);
        }
        event.preventDefault();
      } else if (
        event.key === '2' &&
        !event.ctrlKey &&
        !event.metaKey &&
        !event.altKey
      ) {
        const rect = containerRef.current?.getBoundingClientRect();
        if (rect && screenMousePosition) {
          const newZoom = Math.max(zoom / 1.2, 0.1);
          const clickX =
            screenMousePosition.x - rect.left - rect.width / 2;
          const clickY =
            screenMousePosition.y - rect.top - rect.height / 2;
          const scaleFactor = newZoom / zoom;
          onPanChange({
            x: clickX - (clickX - pan.x) * scaleFactor,
            y: clickY - (clickY - pan.y) * scaleFactor,
          });
          onZoomChange(newZoom);
        }
        event.preventDefault();
      }

      if (
        !gapFillMode &&
        !event.ctrlKey &&
        !event.metaKey &&
        !event.altKey
      ) {
        if (event.key.toLowerCase() === 'f') {
          onToolChange('fill');
          event.preventDefault();
        } else if (event.key.toLowerCase() === 'p') {
          onToolChange('dot-pen');
          event.preventDefault();
        } else if (event.key.toLowerCase() === 'e') {
          onToolChange('eraser');
          event.preventDefault();
        }
      }
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      if (!event.ctrlKey || event.key === 'b') {
        setIsCtrlBPressed(false);
      }
      if (event.code === 'Space') {
        setIsSpacePressed(false);
        event.preventDefault();
      }
      if (event.key.toLowerCase() === 'z') {
        setIsZKeyPressed(false);
        event.preventDefault();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [
    containerRef,
    gapFillMode,
    onPanChange,
    onToolChange,
    onZoomChange,
    pan,
    screenMousePosition,
    zoom,
  ]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    if (isSpacePressed) {
      const handIcon =
        "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"20\" height=\"20\"><text x=\"10\" y=\"15\" text-anchor=\"middle\" font-size=\"16\">✋</text></svg>') 10 10, grab";
      container.style.setProperty('cursor', handIcon, 'important');
    } else if (isZKeyPressed) {
      const zoomIcon =
        "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><circle cx=\"10\" cy=\"10\" r=\"7\" fill=\"white\" stroke=\"black\" stroke-width=\"2\"/><line x1=\"15.5\" y1=\"15.5\" x2=\"22\" y2=\"22\" stroke=\"black\" stroke-width=\"3\" stroke-linecap=\"round\"/><line x1=\"7\" y1=\"10\" x2=\"13\" y2=\"10\" stroke=\"black\" stroke-width=\"2\"/><line x1=\"10\" y1=\"7\" x2=\"10\" y2=\"13\" stroke=\"black\" stroke-width=\"2\"/></svg>') 12 12, zoom-in";
      container.style.setProperty('cursor', zoomIcon, 'important');
    } else {
      container.style.removeProperty('cursor');
    }

    return () => {
      container.style.removeProperty('cursor');
    };
  }, [containerRef, isSpacePressed, isZKeyPressed]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handlePointerDown = () => {
      if (!isSpacePressed) return;
      const grabbingIcon =
        "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"20\" height=\"20\"><text x=\"10\" y=\"15\" text-anchor=\"middle\" font-size=\"16\">✊</text></svg>') 10 10, grabbing";
      container.style.setProperty('cursor', grabbingIcon, 'important');
    };
    const handlePointerUp = () => {
      if (!isSpacePressed) return;
      const handIcon =
        "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"20\" height=\"20\"><text x=\"10\" y=\"15\" text-anchor=\"middle\" font-size=\"16\">✋</text></svg>') 10 10, grab";
      container.style.setProperty('cursor', handIcon, 'important');
    };

    container.addEventListener('pointerdown', handlePointerDown);
    container.addEventListener('pointerup', handlePointerUp);
    container.addEventListener('pointercancel', handlePointerUp);
    return () => {
      container.removeEventListener('pointerdown', handlePointerDown);
      container.removeEventListener('pointerup', handlePointerUp);
      container.removeEventListener('pointercancel', handlePointerUp);
    };
  }, [containerRef, isSpacePressed]);

  const handleWheel = useCallback(
    (event: WheelEvent) => {
      event.preventDefault();
      const rect = canvasRef.current?.getBoundingClientRect();
      const canvas = canvasRef.current;
      if (!rect || !canvas) return;

      if (rect.width === 0 || rect.height === 0) return;

      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const mouseX = (event.clientX - rect.left) * scaleX;
      const mouseY = (event.clientY - rect.top) * scaleY;
      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;
      const canvasPointX =
        (mouseX - centerX - pan.x * scaleX) / zoom +
        canvasSize.width / 2;
      const canvasPointY =
        (mouseY - centerY - pan.y * scaleY) / zoom +
        canvasSize.height / 2;
      const delta = event.deltaY > 0 ? 1 - zoomStep : 1 + zoomStep;
      const newZoom = Math.max(0.1, Math.min(20, zoom * delta));

      onZoomChange(newZoom);
      onPanChange({
        x: (
          mouseX -
          centerX -
          (canvasPointX - canvasSize.width / 2) * newZoom
        ) / scaleX,
        y: (
          mouseY -
          centerY -
          (canvasPointY - canvasSize.height / 2) * newZoom
        ) / scaleY,
      });
    },
    [
      canvasRef,
      canvasSize,
      onPanChange,
      onZoomChange,
      pan,
      zoom,
      zoomStep,
    ],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.addEventListener('wheel', handleWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', handleWheel);
  }, [canvasRef, handleWheel]);

  return { isCtrlBPressed, isSpacePressed, isZKeyPressed };
}
