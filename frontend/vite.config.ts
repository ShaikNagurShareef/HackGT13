import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const API_TARGET = process.env.PATHPULSE_API ?? 'http://127.0.0.1:8000'

export default defineConfig({
  // Static hosts can serve the app under a sub-path; the Vultr/tunnel build uses /.
  base: process.env.VITE_BASE ?? '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: API_TARGET, rewrite: (path) => path.replace(/^\/api/, '') },
      '/static': { target: API_TARGET },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/main.tsx', 'src/App.tsx', 'src/hooks/useBundle.ts', 'src/map/**', 'src/vite-env.d.ts'], // shell + WebGL: covered by Playwright
      thresholds: { lines: 80, functions: 80, branches: 75, statements: 80 },
    },
  },
})
