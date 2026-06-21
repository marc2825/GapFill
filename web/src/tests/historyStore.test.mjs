import assert from 'node:assert/strict';
import test from 'node:test';
import {
  appendHistoryEntry,
  redoHistory,
  undoHistory,
} from '../utils/historyStore.ts';

function entry(id, byteSize = 1) {
  return { id, byteSize };
}

test('Undo and Redo move through history entries', () => {
  let store = { entries: [], index: -1 };
  store = appendHistoryEntry(store, entry('a'));
  store = appendHistoryEntry(store, entry('b'));
  store = appendHistoryEntry(store, entry('c'));

  const undone = undoHistory(store);
  assert.equal(undone.store.index, 1);
  assert.equal(undone.entry.id, 'b');

  const redone = redoHistory(undone.store);
  assert.equal(redone.store.index, 2);
  assert.equal(redone.entry.id, 'c');
});

test('adding after Undo discards the Redo branch', () => {
  let store = { entries: [], index: -1 };
  store = appendHistoryEntry(store, entry('a'));
  store = appendHistoryEntry(store, entry('b'));
  store = appendHistoryEntry(store, entry('c'));
  store = undoHistory(store).store;
  store = appendHistoryEntry(store, entry('d'));

  assert.deepEqual(store.entries.map(({ id }) => id), ['a', 'b', 'd']);
  assert.equal(redoHistory(store).entry, null);
});

test('history respects entry-count and byte-size limits', () => {
  let store = { entries: [], index: -1 };
  store = appendHistoryEntry(store, entry('a', 3), 2, 5);
  store = appendHistoryEntry(store, entry('b', 3), 2, 5);
  assert.deepEqual(store.entries.map(({ id }) => id), ['b']);

  store = appendHistoryEntry(store, entry('c', 1), 2, 5);
  store = appendHistoryEntry(store, entry('d', 1), 2, 5);
  assert.deepEqual(store.entries.map(({ id }) => id), ['c', 'd']);
});
