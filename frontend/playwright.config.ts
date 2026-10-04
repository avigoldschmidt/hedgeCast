import { defineConfig } from '@playwright/test'

const API_PORT = 8100
const WEB_PORT = 5180
const DB = '/tmp/hedgecast-e2e.db'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    channel: 'chrome',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `rm -f ${DB}* && cd ../backend && HEDGECAST_FAKES=1 HEDGECAST_WORKER=0 HEDGECAST_V2_DB=${DB} ../.venv/bin/python -m uvicorn hedgecast.main:app --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: false,
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { HEDGECAST_API: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
    },
  ],
})
