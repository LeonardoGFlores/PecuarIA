import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // maplibre-gl instancia seu worker via `new Worker(new URL(...))`; o
  // pre-bundling do esbuild em dev nao resolve esse arquivo corretamente
  // (fica um 404 em .vite/deps/maplibre-gl-worker.mjs), entao excluimos a
  // lib do dep optimizer — ela ja e ESM valido sem pre-bundling.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
})
