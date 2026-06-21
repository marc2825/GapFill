export interface SizedHistoryEntry {
  byteSize: number;
}

export interface HistoryStore<T extends SizedHistoryEntry> {
  entries: T[];
  index: number;
}

const MAX_HISTORY_ENTRIES = 50;
const MAX_HISTORY_BYTES = 128 * 1024 * 1024;

export function appendHistoryEntry<T extends SizedHistoryEntry>(
  store: HistoryStore<T>,
  entry: T,
  maxEntries = MAX_HISTORY_ENTRIES,
  maxBytes = MAX_HISTORY_BYTES,
): HistoryStore<T> {
  const entries = [
    ...store.entries.slice(0, store.index + 1),
    entry,
  ];
  let totalBytes = entries.reduce(
    (total, currentEntry) => total + currentEntry.byteSize,
    0,
  );

  while (
    entries.length > 1 &&
    (entries.length > maxEntries || totalBytes > maxBytes)
  ) {
    const removedEntry = entries.shift();
    if (removedEntry) totalBytes -= removedEntry.byteSize;
  }

  return {
    entries,
    index: entries.length - 1,
  };
}

interface HistoryTransition<T extends SizedHistoryEntry> {
  store: HistoryStore<T>;
  entry: T | null;
}

export function undoHistory<T extends SizedHistoryEntry>(
  store: HistoryStore<T>,
): HistoryTransition<T> {
  if (store.index <= 0) return { store, entry: null };

  const index = store.index - 1;
  return {
    store: { ...store, index },
    entry: store.entries[index],
  };
}

export function redoHistory<T extends SizedHistoryEntry>(
  store: HistoryStore<T>,
): HistoryTransition<T> {
  if (store.index >= store.entries.length - 1) {
    return { store, entry: null };
  }

  const index = store.index + 1;
  return {
    store: { ...store, index },
    entry: store.entries[index],
  };
}
