import { existsSync, rmSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const rootDirectory = fileURLToPath(new URL('.', import.meta.url))
const outputDirectory = fileURLToPath(new URL('./dist/', import.meta.url))
const taskCAssetDirectory = fileURLToPath(
  new URL('./public/preset-images/C/', import.meta.url),
)
const taskCAssetFiles = [1, 2, 3, 4].flatMap((index) =>
  ['line.png', 'guide.png', 'ref.png', 'coloring_full.png'].map(
    (fileName) => `${index}/${fileName}`,
  ),
)
const taskCAssetsAvailable = taskCAssetFiles.every((relativePath) =>
  existsSync(`${taskCAssetDirectory}${relativePath}`),
)
const includeTaskCPresets =
  taskCAssetsAvailable && process.env.GAPFILL_INCLUDE_TASK_C !== 'false'

const crossOriginIsolationHeaders = {
  'Cross-Origin-Embedder-Policy': 'require-corp',
  'Cross-Origin-Opener-Policy': 'same-origin',
}

// https://vite.dev/config/
export default defineConfig({
  base: './',
  define: {
    __INCLUDE_TASK_C_PRESETS__: JSON.stringify(includeTaskCPresets),
  },
  plugins: [
    react(),
    {
      name: 'exclude-unavailable-task-c-assets',
      closeBundle() {
        if (!includeTaskCPresets) {
          rmSync(`${outputDirectory}preset-images/C`, {
            recursive: true,
            force: true,
          })
        }
      },
    },
  ],
  root: rootDirectory,
  server: {
    headers: crossOriginIsolationHeaders,
  },
  preview: {
    headers: crossOriginIsolationHeaders,
  }
})
