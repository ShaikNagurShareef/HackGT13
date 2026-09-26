import { defineConfig, devices } from '@playwright/test'

const WEB = 'http://127.0.0.1:5173'

export default defineConfig({
  testDir: './e2e',
  // WebGL runs on SwiftShader (CPU) headless; full map flows (search → route → navigate) need headroom.
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: WEB,
    trace: 'retain-on-failure',
    launchOptions: { args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } }, testIgnore: /mobile\.spec\.ts/ },
    { name: 'phone', use: { ...devices['Pixel 7'] }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: [
    {
      command: 'cd ../backend && uv run --package pathpulse-backend uvicorn app.main:create_app --factory --port 8000',
      url: 'http://127.0.0.1:8000/healthz',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    { command: 'npx vite --host 127.0.0.1 --port 5173 --strictPort', url: WEB, reuseExistingServer: true },
  ],
})
