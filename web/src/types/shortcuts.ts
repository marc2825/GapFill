export interface ShortcutConfig {
  [key: string]: [string, string]; // Two shortcuts per tool
}

export const DEFAULT_SHORTCUTS: ShortcutConfig = {
  // Tools
  move: ['Space', 'H'],
  zoom: ['Z', ''],
  colorpicker: ['Right Click', 'I'],
  fill: ['F', ''],
  'dot-pen': ['P', ''],
  eraser: ['E', ''],
  'enclose-and-fill': ['', ''],
  'leftover-pen': ['', ''],
  
  // Actions
  undo: ['Ctrl+Z', ''],
  redo: ['Ctrl+Y', ''],
  blackLight: ['Ctrl+B', ''],
  
  // Canvas controls
  zoomIn: ['Ctrl+=', ''],
  zoomOut: ['Ctrl+-', ''],
  resetZoom: ['Ctrl+0', ''],
  pan: ['Middle Mouse', ''],
};
