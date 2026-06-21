import type { Layer } from '../types';

export interface HistoryLayer {
  id: string;
  name: string;
  visible: boolean;
  opacity: number;
  order: number;
  canvasBlob: Blob;
  width: number;
  height: number;
}

export interface HistoryState {
  layers: HistoryLayer[];
  byteSize: number;
}

export interface PreparedCanvasBlob {
  blob: Blob | null;
  error: unknown;
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
      } else {
        reject(new Error('Failed to encode canvas history snapshot.'));
      }
    }, 'image/png');
  });
}

export function prepareHistoryCanvasBlobs(
  layers: Layer[],
  currentState: HistoryState | null,
  changedLayerIds: ReadonlySet<string>,
  replaceExistingHistory: boolean,
): Map<string, Promise<PreparedCanvasBlob>> {
  const currentLayers = new Map(
    currentState?.layers.map((layer) => [layer.id, layer]) ?? [],
  );
  const preparedBlobs = new Map<string, Promise<PreparedCanvasBlob>>();

  layers.forEach((layer) => {
    const currentLayer = currentLayers.get(layer.id);
    const needsSnapshot =
      replaceExistingHistory ||
      changedLayerIds.has(layer.id) ||
      currentLayer?.width !== layer.canvas.width ||
      currentLayer?.height !== layer.canvas.height;

    if (needsSnapshot) {
      preparedBlobs.set(
        layer.id,
        canvasToBlob(layer.canvas).then(
          (blob) => ({ blob, error: null }),
          (error: unknown) => ({ blob: null, error }),
        ),
      );
    }
  });

  return preparedBlobs;
}

export async function captureHistoryState(
  layers: Layer[],
  previousState: HistoryState | null,
  changedLayerIds: ReadonlySet<string>,
  preparedBlobs: ReadonlyMap<string, Promise<PreparedCanvasBlob>>,
): Promise<HistoryState> {
  const previousLayers = new Map(
    previousState?.layers.map((layer) => [layer.id, layer]) ?? [],
  );
  const historyLayers = await Promise.all(
    layers.map(async (layer): Promise<HistoryLayer> => {
      const width = layer.canvas.width;
      const height = layer.canvas.height;
      const previousLayer = previousLayers.get(layer.id);
      const canReuseBlob =
        !changedLayerIds.has(layer.id) &&
        previousLayer?.width === width &&
        previousLayer.height === height;
      let canvasBlob: Blob;

      if (canReuseBlob) {
        canvasBlob = previousLayer.canvasBlob;
      } else {
        const preparedBlob = await preparedBlobs.get(layer.id);
        if (preparedBlob?.blob) {
          canvasBlob = preparedBlob.blob;
        } else if (preparedBlob?.error) {
          throw preparedBlob.error;
        } else {
          canvasBlob = await canvasToBlob(layer.canvas);
        }
      }

      return {
        id: layer.id,
        name: layer.name,
        visible: layer.visible,
        opacity: layer.opacity,
        order: layer.order,
        canvasBlob,
        width,
        height,
      };
    }),
  );

  return {
    layers: historyLayers,
    byteSize: historyLayers.reduce(
      (total, layer) => total + layer.canvasBlob.size,
      0,
    ),
  };
}
