import { useLayoutEffect, type RefObject } from 'react';
import type { Layer, Point } from '../../types';
import type { GapFillRegion } from '../../types/GapFill';
import './GapMagnifier.css';

interface GapMagnifierProps {
  layers: Layer[];
  gaps: GapFillRegion[];
  hoveredGap: GapFillRegion | null;
  selectedGap: GapFillRegion | null;
  colorSelectionMode: boolean;
  temporaryColor: string;
  highlightColor: string;
  canvasMousePosition: Point | null;
  fixedPosition: Point | null;
  canvasRef: RefObject<HTMLCanvasElement | null>;
  minimapRef: RefObject<HTMLDivElement | null>;
  onCancel: () => void;
}

const MAGNIFIER_SIZE = 320;
const SOURCE_SIZE = 64;

export function GapMagnifier({
  layers,
  gaps,
  hoveredGap,
  selectedGap,
  colorSelectionMode,
  temporaryColor,
  highlightColor,
  canvasMousePosition,
  fixedPosition,
  canvasRef,
  minimapRef,
  onCancel,
}: GapMagnifierProps) {
  const currentGap = selectedGap || hoveredGap;
  const position =
    colorSelectionMode && fixedPosition ? fixedPosition : canvasMousePosition;

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !currentGap) return;

    const context = canvas.getContext('2d');
    if (!context) return;

    context.clearRect(0, 0, MAGNIFIER_SIZE, MAGNIFIER_SIZE);
    context.imageSmoothingEnabled = false;

    // Implementation of Paper Sec. 4.1.3:
    // fixed 5x magnification independent of the main canvas zoom.
    const sourceX = currentGap.center.x - SOURCE_SIZE / 2;
    const sourceY = currentGap.center.y - SOURCE_SIZE / 2;
    const scale = MAGNIFIER_SIZE / SOURCE_SIZE;

    layers
      .filter((layer) => layer.visible)
      .sort((a, b) => a.order - b.order)
      .forEach((layer) => {
        const visibleX = Math.max(0, sourceX);
        const visibleY = Math.max(0, sourceY);
        const visibleEndX = Math.min(
          layer.canvas.width,
          sourceX + SOURCE_SIZE,
        );
        const visibleEndY = Math.min(
          layer.canvas.height,
          sourceY + SOURCE_SIZE,
        );
        const visibleWidth = Math.max(0, visibleEndX - visibleX);
        const visibleHeight = Math.max(0, visibleEndY - visibleY);
        if (visibleWidth === 0 || visibleHeight === 0) return;

        context.globalAlpha = layer.opacity;
        context.drawImage(
          layer.canvas,
          visibleX,
          visibleY,
          visibleWidth,
          visibleHeight,
          (visibleX - sourceX) * scale,
          (visibleY - sourceY) * scale,
          visibleWidth * scale,
          visibleHeight * scale,
        );
      });
    context.globalAlpha = 1;

    gaps
      .filter((gap) => {
        const centerIsVisible =
          gap.center.x >= sourceX &&
          gap.center.x < sourceX + SOURCE_SIZE &&
          gap.center.y >= sourceY &&
          gap.center.y < sourceY + SOURCE_SIZE;
        return (
          centerIsVisible ||
          gap.pixels.some(
            (pixel) =>
              pixel.x >= sourceX &&
              pixel.x < sourceX + SOURCE_SIZE &&
              pixel.y >= sourceY &&
              pixel.y < sourceY + SOURCE_SIZE,
          )
        );
      })
      .forEach((gap) => {
        context.fillStyle =
          gap.id === currentGap.id && colorSelectionMode && selectedGap
            ? temporaryColor
            : gap.predictedColor;

        gap.pixels.forEach((pixel) => {
          const localX = (pixel.x - sourceX) * scale;
          const localY = (pixel.y - sourceY) * scale;
          if (
            localX >= 0 &&
            localX < MAGNIFIER_SIZE &&
            localY >= 0 &&
            localY < MAGNIFIER_SIZE
          ) {
            context.fillRect(
              Math.floor(localX),
              Math.floor(localY),
              Math.ceil(scale),
              Math.ceil(scale),
            );
          }
        });
      });

    // Implementation of Paper Sec. 4.1.3: hollow translucent marker at the exact gap position.
    const pixelSize = scale;
    context.strokeStyle = highlightColor;
    context.globalAlpha = 0.75;
    context.lineWidth = 0.5;
    context.strokeRect(
      MAGNIFIER_SIZE / 2 - pixelSize * 0.4,
      MAGNIFIER_SIZE / 2 - pixelSize * 0.4,
      pixelSize * 1.8,
      pixelSize * 1.8,
    );
    context.globalAlpha = 1;
  }, [
    canvasRef,
    colorSelectionMode,
    currentGap,
    gaps,
    highlightColor,
    layers,
    selectedGap,
    temporaryColor,
  ]);

  if (!currentGap) return null;

  return (
    <div
      ref={minimapRef}
      className="popup-minimap"
      style={{
        left: position ? position.x - MAGNIFIER_SIZE / 2 : 50,
        top: position ? position.y - MAGNIFIER_SIZE / 2 : 50,
      }}
    >
      <canvas
        ref={canvasRef}
        width={MAGNIFIER_SIZE}
        height={MAGNIFIER_SIZE}
      />
      {colorSelectionMode && (
        <button
          type="button"
          className="minimap-cancel-button"
          data-color-selection-cancel
          aria-label="Cancel color correction"
          onPointerDown={(event) => {
            event.preventDefault();
            event.stopPropagation();
          }}
          onPointerUp={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onCancel();
          }}
        />
      )}
    </div>
  );
}
