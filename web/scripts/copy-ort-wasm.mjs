import { copyFileSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const rootDir = dirname(dirname(fileURLToPath(import.meta.url)));
const distDir = join(rootDir, 'node_modules', 'onnxruntime-web', 'dist');
const outputDir = join(rootDir, 'public', 'ort-wasm');

const files = [
  'ort-wasm-simd-threaded.wasm',
];

rmSync(outputDir, { recursive: true, force: true });
mkdirSync(outputDir, { recursive: true });

for (const file of files) {
  copyFileSync(join(distDir, file), join(outputDir, file));
}
