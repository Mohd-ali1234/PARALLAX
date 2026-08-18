import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// The dev server proxies /api to FastAPI so the browser only ever talks to one
// origin. That keeps CORS out of the local loop entirely and means the app
// ships with no hardcoded backend host.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [react()],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
      host: true, // bind 0.0.0.0 so the container port mapping works
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
      watch: {
        // Bind mounts on Windows/Docker don't deliver inotify events.
        usePolling: env.VITE_USE_POLLING === 'true',
      },
    },
    preview: { host: true, port: 4173, strictPort: true },
    build: {
      outDir: 'dist',
      sourcemap: mode !== 'production',
    },
  }
})
