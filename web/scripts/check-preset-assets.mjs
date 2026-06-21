import { stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { IMAGE_PRESETS } from '../src/config/presets.ts';

const ASSET_FIELDS = ['lineArt', 'guides', 'coloring', 'reference'];
const publicDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../public',
);
const configuredAssets = new Set();

for (const preset of IMAGE_PRESETS) {
  for (const field of ASSET_FIELDS) {
    const assetPath = preset[field];
    if (!assetPath) continue;

    configuredAssets.add(assetPath);
  }
}

const missingAssets = [];

for (const assetPath of configuredAssets) {
  const relativePath = assetPath.replace(/^\/+/, '');
  const filePath = path.resolve(publicDirectory, relativePath);

  if (!filePath.startsWith(`${publicDirectory}${path.sep}`)) {
    missingAssets.push(`${assetPath} (outside public/)`);
    continue;
  }

  try {
    const file = await stat(filePath);
    if (!file.isFile() || file.size === 0) missingAssets.push(assetPath);
  } catch {
    missingAssets.push(assetPath);
  }
}

if (missingAssets.length > 0) {
  console.error('Missing or empty preset assets:');
  for (const assetPath of missingAssets) console.error(`- ${assetPath}`);
  process.exitCode = 1;
} else {
  console.log(`Verified ${configuredAssets.size} source-distributed preset assets.`);
}
