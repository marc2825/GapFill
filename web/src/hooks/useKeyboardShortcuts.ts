import { useEffect, useRef } from 'react';
import type { Dispatch, SetStateAction } from 'react';

interface UseKeyboardShortcutsParams {
  zoom: number;
  zoomStep: number;
  blackLightMode: boolean;
  gapFillMode: boolean;
  overflowFillMode: boolean;
  setBlackLightMode: Dispatch<SetStateAction<boolean>>;
  setZoom: Dispatch<SetStateAction<number>>;
  onUndo: () => Promise<void> | void;
  onRedo: () => Promise<void> | void;
}

function useKeyboardShortcuts({
  zoom,
  zoomStep,
  blackLightMode,
  gapFillMode,
  overflowFillMode,
  setBlackLightMode,
  setZoom,
  onUndo,
  onRedo,
}: UseKeyboardShortcutsParams) {
  const keysPressed = useRef(new Set<string>());

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey) {
        const keyCombo = `ctrl+${event.key.toLowerCase()}`;

        if (keysPressed.current.has(keyCombo)) {
          return;
        }
        keysPressed.current.add(keyCombo);

        switch (event.key) {
          case 'z':
            if (event.shiftKey) {
              onRedo();
            } else {
              onUndo();
            }
            event.preventDefault();
            break;
          case 'y':
            onRedo();
            event.preventDefault();
            break;
          case 'b':
            if (!gapFillMode && !overflowFillMode) {
              setBlackLightMode(!blackLightMode);
            }
            event.preventDefault();
            break;
          case '=':
          case '+': {
            const newZoomIn = Math.min(20, zoom * (1 + zoomStep));
            setZoom(newZoomIn);
            event.preventDefault();
            break;
          }
          case '-': {
            const newZoomOut = Math.max(0.1, zoom * (1 - zoomStep));
            setZoom(newZoomOut);
            event.preventDefault();
            break;
          }
          case '0':
            setZoom(1);
            event.preventDefault();
            break;
          default:
            break;
        }
      }
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.key === 'Control') {
        const keyCombo = `ctrl+${event.key.toLowerCase()}`;
        keysPressed.current.delete(keyCombo);
        keysPressed.current.clear();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [blackLightMode, gapFillMode, onRedo, onUndo, overflowFillMode, setBlackLightMode, setZoom, zoom, zoomStep]);
}

export default useKeyboardShortcuts;
