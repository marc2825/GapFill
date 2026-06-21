import React, { useCallback, useEffect, useRef, useState } from 'react';
import { getPixelColor } from '../utils/canvasUtils';
import './ReferenceCanvas.css';

interface ReferenceCanvasProps {
  referenceImage: string;
  onColorPick: (color: string) => void;
}

interface ZoomState {
  scale: number;
  offsetX: number;
  offsetY: number;
}

const ReferenceCanvas: React.FC<ReferenceCanvasProps> = ({
  referenceImage,
  onColorPick,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [colorPickerInfo, setColorPickerInfo] = useState<{x: number, y: number, color: string} | null>(null);
  const [zoomState, setZoomState] = useState<ZoomState>({
    scale: 1,
    offsetX: 0,
    offsetY: 0
  });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [isSpacePressed, setIsSpacePressed] = useState(false);

  // Implementation of Paper Sec. 5.1 Methodology:
  // the experiment paint software includes a reference-image panel with local zoom,
  // pan, and color-pick so users can inspect the target image while painting.

  const drawImage = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    const img = imageRef.current;

    if (!canvas || !container || !img) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const containerWidth = container.clientWidth - 20;
    const containerHeight = Math.min(600, container.clientHeight - 100);

    canvas.width = containerWidth;
    canvas.height = containerHeight;

    const baseScaleX = containerWidth / img.width;
    const baseScaleY = containerHeight / img.height;
    const baseScale = Math.min(baseScaleX, baseScaleY);
    const finalScale = baseScale * zoomState.scale;
    const scaledWidth = img.width * finalScale;
    const scaledHeight = img.height * finalScale;
    const baseOffsetX = (containerWidth - scaledWidth) / 2;
    const baseOffsetY = (containerHeight - scaledHeight) / 2;
    const offsetX = baseOffsetX + zoomState.offsetX;
    const offsetY = baseOffsetY + zoomState.offsetY;

    ctx.clearRect(0, 0, containerWidth, containerHeight);
    ctx.drawImage(img, offsetX, offsetY, scaledWidth, scaledHeight);
  }, [zoomState]);

  // Load reference image
  useEffect(() => {
    if (!referenceImage) return;

    const img = new Image();
    img.onload = () => {
      imageRef.current = img;
      // Reset zoom when new image loads
      setZoomState({
        scale: 1,
        offsetX: 0,
        offsetY: 0
      });
    };

    img.src = referenceImage;
  }, [referenceImage]);

  // Redraw when zoom state changes
  useEffect(() => {
    drawImage();
  }, [drawImage]);

  // Handle keyboard events for panning
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !e.repeat) {
        e.preventDefault();
        setIsSpacePressed(true);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        e.preventDefault();
        setIsSpacePressed(false);
        setIsPanning(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  const handleCanvasClick = (e: React.MouseEvent) => {
    // If space is pressed, don't zoom - this is for panning
    if (isSpacePressed) return;
    
    // Left click zooms in at cursor position
    const canvas = canvasRef.current;
    const container = containerRef.current;
    const img = imageRef.current;
    if (!canvas || !container || !img) return;

    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Get current image dimensions and position
    const containerWidth = container.clientWidth - 20;
    const containerHeight = Math.min(600, container.clientHeight - 100);
    const baseScaleX = containerWidth / img.width;
    const baseScaleY = containerHeight / img.height;
    const baseScale = Math.min(baseScaleX, baseScaleY);
    
    const currentScale = baseScale * zoomState.scale;
    const currentWidth = img.width * currentScale;
    const currentHeight = img.height * currentScale;
    const currentOffsetX = (containerWidth - currentWidth) / 2 + zoomState.offsetX;
    const currentOffsetY = (containerHeight - currentHeight) / 2 + zoomState.offsetY;

    // Convert mouse position to image coordinates
    const imgX = (mouseX - currentOffsetX) / currentScale;
    const imgY = (mouseY - currentOffsetY) / currentScale;

    // Calculate new scale
    const zoomFactor = 1.15; // 15% zoom
    const newScale = zoomState.scale * zoomFactor;
    const newActualScale = baseScale * newScale;
    const newWidth = img.width * newActualScale;
    const newHeight = img.height * newActualScale;

    // Calculate new offset to keep the clicked point at the same position
    const newBaseOffsetX = (containerWidth - newWidth) / 2;
    const newBaseOffsetY = (containerHeight - newHeight) / 2;
    
    // The clicked point should stay at the same screen position
    const newOffsetX = mouseX - (imgX * newActualScale + newBaseOffsetX);
    const newOffsetY = mouseY - (imgY * newActualScale + newBaseOffsetY);

    setZoomState({
      scale: newScale,
      offsetX: newOffsetX,
      offsetY: newOffsetY
    });
  };

  const handleCanvasRightClick = (e: React.MouseEvent) => {
    e.preventDefault(); // Prevent context menu
    
    // If space is pressed, don't pick color - this is for panning
    if (isSpacePressed) return;
    
    // Right click always picks color regardless of active tool
    pickColor(e);
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (isSpacePressed && e.button === 0) {
      setIsPanning(true);
      setPanStart({ x: e.clientX, y: e.clientY });
      e.preventDefault();
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning && isSpacePressed) {
      const deltaX = e.clientX - panStart.x;
      const deltaY = e.clientY - panStart.y;
      
      setZoomState(prev => ({
        ...prev,
        offsetX: prev.offsetX + deltaX,
        offsetY: prev.offsetY + deltaY
      }));
      
      setPanStart({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  const pickColor = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    const img = imageRef.current;
    const container = containerRef.current;
    if (!canvas || !img || !container) return;

    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    // Calculate the actual image coordinates considering zoom and offset
    const containerWidth = container.clientWidth - 20;
    const containerHeight = Math.min(600, container.clientHeight - 100);
    
    const baseScaleX = containerWidth / img.width;
    const baseScaleY = containerHeight / img.height;
    const baseScale = Math.min(baseScaleX, baseScaleY);
    const finalScale = baseScale * zoomState.scale;
    
    const scaledWidth = img.width * finalScale;
    const scaledHeight = img.height * finalScale;
    const baseOffsetX = (containerWidth - scaledWidth) / 2;
    const baseOffsetY = (containerHeight - scaledHeight) / 2;
    const offsetX = baseOffsetX + zoomState.offsetX;
    const offsetY = baseOffsetY + zoomState.offsetY;

    // Convert click position to image coordinates
    const imgX = (clickX - offsetX) / finalScale;
    const imgY = (clickY - offsetY) / finalScale;

    // Check if click is within image bounds
    if (imgX >= 0 && imgX < img.width && imgY >= 0 && imgY < img.height) {
      // Get color from canvas at clicked position
      const color = getPixelColor(canvas, Math.round(clickX), Math.round(clickY));
      if (color !== 'rgba(0,0,0,0)') {
        const hex = rgbaToHex(color);
        onColorPick(hex);

        // Show color picker info popup
        setColorPickerInfo({
          x: e.clientX,
          y: e.clientY,
          color: hex + ' (ref)'
        });

        // Hide popup after 2 seconds
        setTimeout(() => {
          setColorPickerInfo(null);
        }, 2000);
      }
    }
  };

  const handleResetZoom = () => {
    setZoomState({
      scale: 1,
      offsetX: 0,
      offsetY: 0
    });
  };

  const rgbaToHex = (rgba: string): string => {
    const match = rgba.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (!match) return '#000000';
    
    const r = parseInt(match[1]);
    const g = parseInt(match[2]);
    const b = parseInt(match[3]);
    
    return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
  };

  const getCursorStyle = () => {
    if (isSpacePressed) {
      return isPanning ? 'grabbing' : 'grab';
    }
    // Always show small green cursor
    return 'url(\'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12"><circle cx="6" cy="6" r="3" fill="green" stroke="white" stroke-width="1"/></svg>\') 6 6, auto';
  };

  return (
    <div className="reference-canvas-container" ref={containerRef}>
      <div className="reference-canvas-header">
        <div className="reference-title">Reference Image</div>
      </div>
      <div className="reference-canvas-wrapper">
        <canvas
          ref={canvasRef}
          className="reference-canvas"
          onClick={handleCanvasClick}
          onContextMenu={handleCanvasRightClick}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          style={{ 
            cursor: getCursorStyle()
          }}
        />
      </div>
      
      <div className="zoom-controls">
        <div className="zoom-hints">
          <div style={{ fontSize: '10px', color: '#666', fontStyle: 'italic' }}>🔍 Left-click to zoom</div>
          <div style={{ fontSize: '10px', color: '#666', fontStyle: 'italic' }}>💡 Right-click to pick color</div>
        </div>
        <button className="zoom-button reset-button" onClick={handleResetZoom}>
          Reset
        </button>
      </div>
      
      {colorPickerInfo && (
        <div
          className="color-picker-popup"
          style={{
            left: Math.min(colorPickerInfo.x + 10, window.innerWidth - 150),
            top: Math.max(colorPickerInfo.y - 40, 10)
          }}
        >
          <div className="color-picker-popup-content">
            <div
              className="color-picker-preview"
              style={{ backgroundColor: colorPickerInfo.color.split(' ')[0] }}
            />
            <span className="color-picker-text">{colorPickerInfo.color}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReferenceCanvas;
