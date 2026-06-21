import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { Layer } from '../types';

interface UseLayerHandlersParams {
  layers: Layer[];
  setLayers: Dispatch<SetStateAction<Layer[]>>;
}

function useLayerHandlers({
  layers,
  setLayers,
}: UseLayerHandlersParams) {
  const handleLayerToggleVisibility = useCallback(
    (layerId: string) => {
      setLayers(
        layers.map((layer) =>
          layer.id === layerId
            ? { ...layer, visible: !layer.visible }
            : layer,
        ),
      );
    },
    [layers, setLayers],
  );

  const handleLayerUpdate = useCallback(
    (layerId: string, canvas: HTMLCanvasElement) => {
      setLayers(
        layers.map((layer) =>
          layer.id === layerId
            ? { ...layer, canvas }
            : layer,
        ),
      );
    },
    [layers, setLayers],
  );

  return {
    handleLayerToggleVisibility,
    handleLayerUpdate,
  };
}

export default useLayerHandlers;
