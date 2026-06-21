export interface ImagePreset {
  id: string;
  name: string;
  description?: string;
  lineArt?: string;
  guides?: string;
  coloring?: string;
  reference?: string;
  enableGapFillMode?: boolean;
  enableEncloseAndFill?: boolean;
  enableLeftoverPen?: boolean;
  enableBucketTool?: boolean;
  enableBlackLight?: boolean;
  defaultGapFillMode?: boolean;
  lockGapFillMode?: boolean;
  enableGapThreshold?: boolean;
  enableHighlightColor?: boolean;
  timeLimit?: number;
  autoSaveOnDone?: boolean;
}

type PresetAssets = Pick<ImagePreset, 'lineArt' | 'guides' | 'reference'> &
  Partial<Pick<ImagePreset, 'coloring'>>;
type ToolProfile = Required<
  Pick<
    ImagePreset,
    | 'enableEncloseAndFill'
    | 'enableLeftoverPen'
    | 'enableBucketTool'
    | 'enableBlackLight'
  >
>;
type GapFillProfile = Required<
  Pick<
    ImagePreset,
    | 'enableGapFillMode'
    | 'defaultGapFillMode'
    | 'lockGapFillMode'
    | 'enableGapThreshold'
    | 'enableHighlightColor'
  >
>;
type SessionProfile = Required<
  Pick<ImagePreset, 'timeLimit' | 'autoSaveOnDone'>
>;

function publicAsset(path: string): string {
  return `${import.meta.env?.BASE_URL ?? '/'}${path.replace(/^\/+/, '')}`;
}

function presetAssets(
  basePath: string,
  options: { coloring?: boolean; coloringFile?: string } = {},
): PresetAssets {
  const coloringFile =
    options.coloringFile ?? (options.coloring ? 'coloring.png' : undefined);

  return {
    lineArt: publicAsset(`preset-images/${basePath}/line.png`),
    guides: publicAsset(`preset-images/${basePath}/guide.png`),
    reference: publicAsset(`preset-images/${basePath}/ref.png`),
    ...(coloringFile
      ? { coloring: publicAsset(`preset-images/${basePath}/${coloringFile}`) }
      : {}),
  };
}

function definePreset(preset: ImagePreset): ImagePreset {
  return preset;
}

const TASK_DESCRIPTIONS = {
  paintFromScratch:
    'Task A: Paint the image from scratch. You will color the entire image starting from a blank canvas, using the line art and guide images as reference.',
  fixGaps:
    'Task B: Detect and correct unpainted gaps. You will identify and fix missing colored areas (gaps) in a partially colored image.',
  observeAiResult:
    "This image shows the result after all the larger regions have been filled in correctly, followed by the automatic application of AI-based predictions to the remaining small unpainted areas (gaps). Please freely observe this image (no need to fix) under the assumption that it will be submitted to the next person in the workflow. You are given 30 seconds, but you may finish earlier if you feel it is sufficient. After you complete the task, you'll be asked two impression-rating questions (selection between 1-7) about the presented image.",
} as const;

const TOOL_PROFILES = {
  fullToolset: {
    enableEncloseAndFill: true,
    enableLeftoverPen: true,
    enableBucketTool: true,
    enableBlackLight: true,
  },
  oursPainting: {
    enableEncloseAndFill: false,
    enableLeftoverPen: false,
    enableBucketTool: true,
    enableBlackLight: false,
  },
  gapFillOnly: {
    enableEncloseAndFill: false,
    enableLeftoverPen: false,
    enableBucketTool: false,
    enableBlackLight: false,
  },
} satisfies Record<string, ToolProfile>;

const GAP_FILL_PROFILES = {
  debugUnlocked: {
    enableGapFillMode: true,
    defaultGapFillMode: false,
    lockGapFillMode: false,
    enableGapThreshold: true,
    enableHighlightColor: true,
  },
  disabledLocked: {
    enableGapFillMode: false,
    defaultGapFillMode: false,
    lockGapFillMode: true,
    enableGapThreshold: false,
    enableHighlightColor: false,
  },
  availableOff: {
    enableGapFillMode: true,
    defaultGapFillMode: false,
    lockGapFillMode: false,
    enableGapThreshold: false,
    enableHighlightColor: false,
  },
  availableOn: {
    enableGapFillMode: true,
    defaultGapFillMode: true,
    lockGapFillMode: false,
    enableGapThreshold: false,
    enableHighlightColor: false,
  },
  lockedOn: {
    enableGapFillMode: true,
    defaultGapFillMode: true,
    lockGapFillMode: true,
    enableGapThreshold: false,
    enableHighlightColor: false,
  },
} satisfies Record<string, GapFillProfile>;

const SESSION_PROFILES = {
  debug: {
    timeLimit: 600,
    autoSaveOnDone: false,
  },
  practice5mNoSave: {
    timeLimit: 300,
    autoSaveOnDone: false,
  },
  practiceLongNoSave: {
    timeLimit: 3000,
    autoSaveOnDone: false,
  },
  taskA: {
    timeLimit: 150,
    autoSaveOnDone: false,
  },
  taskB: {
    timeLimit: 90,
    autoSaveOnDone: false,
  },
  taskCObservation: {
    timeLimit: 30,
    autoSaveOnDone: false,
  },
} satisfies Record<string, SessionProfile>;

const DEBUG_PRESET = definePreset({
  id: 'debug',
  name: '---Select The Preset---',
  description: 'Please select the appropriate mode from the top-left dropdown!',
  ...TOOL_PROFILES.fullToolset,
  ...GAP_FILL_PROFILES.debugUnlocked,
  ...SESSION_PROFILES.debug,
});

function taskCObservationPreset(index: 1 | 2 | 3 | 4): ImagePreset {
  return definePreset({
    id: `C${index}_Observation`,
    name: `[Task C-${index}] `,
    description: TASK_DESCRIPTIONS.observeAiResult,
    ...presetAssets(`C/${index}`, { coloringFile: 'coloring_full.png' }),
    ...TOOL_PROFILES.gapFillOnly,
    ...GAP_FILL_PROFILES.lockedOn,
    ...SESSION_PROFILES.taskCObservation,
  });
}

const TASK_C_PRESETS =
  typeof __INCLUDE_TASK_C_PRESETS__ !== 'undefined' &&
  __INCLUDE_TASK_C_PRESETS__
    ? ([1, 2, 3, 4] as const).map(taskCObservationPreset)
    : [];

// Order follows userstudy_flow.png and the study conditions in GapFill_CHI.pdf Sec. 5.1.
// Each entry composes task assets, available tools, GapFill state, and session behavior.
export const IMAGE_PRESETS: ImagePreset[] = [
  DEBUG_PRESET,
  definePreset({
    id: 'A_Ex1_Base',
    name: '[Practice] A_ex1 (Base)',
    ...presetAssets('Ex2'),
    ...TOOL_PROFILES.fullToolset,
    ...GAP_FILL_PROFILES.disabledLocked,
    ...SESSION_PROFILES.practice5mNoSave,
  }),
  definePreset({
    id: 'A_Ex2_Base',
    name: '[Practice] A_ex2 (Base)',
    ...presetAssets('Ex', { coloring: true }),
    ...TOOL_PROFILES.fullToolset,
    ...GAP_FILL_PROFILES.disabledLocked,
    ...SESSION_PROFILES.practice5mNoSave,
  }),
  definePreset({
    id: 'A_Task_Base',
    name: '[Task A] Right (Base)',
    description: TASK_DESCRIPTIONS.paintFromScratch,
    ...presetAssets('A/R'),
    ...TOOL_PROFILES.fullToolset,
    ...GAP_FILL_PROFILES.disabledLocked,
    ...SESSION_PROFILES.taskA,
  }),
  definePreset({
    id: 'A_Ex1_Ours',
    name: '[Practice] A_ex1 (Ours)',
    ...presetAssets('Ex2'),
    ...TOOL_PROFILES.oursPainting,
    ...GAP_FILL_PROFILES.availableOff,
    ...SESSION_PROFILES.practice5mNoSave,
  }),
  definePreset({
    id: 'A_Ex2_Ours',
    name: '[Practice] A_ex2 (Ours)',
    ...presetAssets('Ex', { coloring: true }),
    ...TOOL_PROFILES.oursPainting,
    ...GAP_FILL_PROFILES.availableOn,
    ...SESSION_PROFILES.practice5mNoSave,
  }),
  definePreset({
    id: 'A_Task_Ours',
    name: '[Task A] Left (Ours)',
    description: TASK_DESCRIPTIONS.paintFromScratch,
    ...presetAssets('A/L'),
    ...TOOL_PROFILES.oursPainting,
    ...GAP_FILL_PROFILES.availableOff,
    ...SESSION_PROFILES.taskA,
  }),
  definePreset({
    id: 'B_Ex2_Base',
    name: '[Practice] B_ex (Base)',
    description: TASK_DESCRIPTIONS.fixGaps,
    ...presetAssets('Ex2', { coloring: true }),
    ...TOOL_PROFILES.fullToolset,
    ...GAP_FILL_PROFILES.disabledLocked,
    ...SESSION_PROFILES.practice5mNoSave,
  }),
  definePreset({
    id: 'B1_Easy_Base',
    name: '[Task B-1] Left (Base)',
    description: TASK_DESCRIPTIONS.fixGaps,
    ...presetAssets('B/Easy/L', { coloring: true }),
    ...TOOL_PROFILES.fullToolset,
    ...GAP_FILL_PROFILES.disabledLocked,
    ...SESSION_PROFILES.taskB,
  }),
  definePreset({
    id: 'B_Ex2_Ours',
    name: '[Practice] B_ex (Ours)',
    description: TASK_DESCRIPTIONS.fixGaps,
    ...presetAssets('Ex2', { coloring: true }),
    ...TOOL_PROFILES.gapFillOnly,
    ...GAP_FILL_PROFILES.lockedOn,
    ...SESSION_PROFILES.practice5mNoSave,
  }),
  definePreset({
    id: 'B1_Easy_Ours',
    name: '[Task B-1] Right (Ours)',
    description: TASK_DESCRIPTIONS.fixGaps,
    ...presetAssets('B/Easy/R', { coloring: true }),
    ...TOOL_PROFILES.gapFillOnly,
    ...GAP_FILL_PROFILES.lockedOn,
    ...SESSION_PROFILES.taskB,
  }),
  definePreset({
    id: 'B2_Hard_Base',
    name: '[Task B-2] Right (Base)',
    description: TASK_DESCRIPTIONS.fixGaps,
    ...presetAssets('B/Hard/R', { coloring: true }),
    ...TOOL_PROFILES.fullToolset,
    ...GAP_FILL_PROFILES.disabledLocked,
    ...SESSION_PROFILES.taskB,
  }),
  definePreset({
    id: 'B2_Hard_Ours',
    name: '[Task B-2] Left (Ours)',
    description: TASK_DESCRIPTIONS.fixGaps,
    ...presetAssets('B/Hard/L', { coloring: true }),
    ...TOOL_PROFILES.gapFillOnly,
    ...GAP_FILL_PROFILES.lockedOn,
    ...SESSION_PROFILES.taskB,
  }),
  ...TASK_C_PRESETS,
];
