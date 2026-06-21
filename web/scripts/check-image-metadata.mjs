import { readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { getEmbeddedText, getPngTextMetadata } from './image-metadata.mjs';

const COPYRIGHT = '©IIS-P / Ponnomichi Production Committee';
const AUTHOR = 'Masahiro Kono';
const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const presetDirectory = path.resolve(scriptDirectory, '../public/preset-images');
const docsImageDirectory = path.resolve(scriptDirectory, '../../docs/images');
const failures = [];

async function findImages(directory, extensions) {
  const images = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const filePath = path.join(directory, entry.name);
    if (entry.isDirectory()) images.push(...(await findImages(filePath, extensions)));
    else if (extensions.has(path.extname(entry.name).toLowerCase())) images.push(filePath);
  }
  return images;
}

function displayPath(filePath) {
  return path.relative(path.resolve(scriptDirectory, '../..'), filePath);
}

const presetImages = await findImages(presetDirectory, new Set(['.png']));
for (const filePath of presetImages) {
  const metadata = await getPngTextMetadata(filePath);
  if (metadata.get('Copyright') !== COPYRIGHT) {
    failures.push(`${displayPath(filePath)}: missing Copyright metadata`);
  }
}

const docsImages = await findImages(docsImageDirectory, new Set(['.png', '.gif']));
for (const filePath of docsImages) {
  if (path.extname(filePath).toLowerCase() === '.png') {
    const metadata = await getPngTextMetadata(filePath);
    if (metadata.get('Copyright') !== COPYRIGHT) {
      failures.push(`${displayPath(filePath)}: missing Copyright metadata`);
    }
    if (metadata.get('Author') !== AUTHOR) {
      failures.push(`${displayPath(filePath)}: missing Author metadata`);
    }
  } else {
    const embeddedText = await getEmbeddedText(filePath);
    if (!embeddedText.includes('<dc:rights>') || !embeddedText.includes(COPYRIGHT)) {
      failures.push(`${displayPath(filePath)}: missing Copyright metadata`);
    }
    if (!embeddedText.includes('<dc:creator>') || !embeddedText.includes(AUTHOR)) {
      failures.push(`${displayPath(filePath)}: missing Author metadata`);
    }
  }
}

if (failures.length > 0) {
  console.error('Invalid image metadata:');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exitCode = 1;
} else {
  console.log(
    `Verified metadata in ${presetImages.length} preset PNGs and ` +
      `${docsImages.length} documentation images.`,
  );
}
