export const UNASSIGNED_MATERIAL_COLOR = '#FF00FF';

export function parseHexColor(color: string): [number, number, number] | null {
  const match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(color);
  if (!match) return null;

  return [
    Number.parseInt(match[1], 16),
    Number.parseInt(match[2], 16),
    Number.parseInt(match[3], 16),
  ];
}

const UNASSIGNED_MATERIAL_RGB = parseHexColor(UNASSIGNED_MATERIAL_COLOR)!;

export function resolveGapFillFallbackColor(color?: string): string {
  if (color === undefined) return UNASSIGNED_MATERIAL_COLOR;
  if (parseHexColor(color)) return color;

  console.error(
    `GapFill received an invalid fallback color: "${color}". ` +
      `Using ${UNASSIGNED_MATERIAL_COLOR} instead.`,
  );
  return UNASSIGNED_MATERIAL_COLOR;
}

export function resolveGapFillFallbackRgb(
  color: string,
): [number, number, number] {
  const parsed = parseHexColor(color);
  if (parsed) return parsed;

  console.error(
    `GapFill received an invalid fallback color: "${color}". ` +
      `Using ${UNASSIGNED_MATERIAL_COLOR} instead.`,
  );
  return [...UNASSIGNED_MATERIAL_RGB];
}
