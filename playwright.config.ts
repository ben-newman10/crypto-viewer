/**
 * Playwright configuration for the Crypto Viewer E2E suite.
 *
 * The suite runs against the real stack: a production frontend build served by
 * `vite preview`, proxying `/api` to a real FastAPI backend. The backend is
 * started with CRYPTO_VIEWER_TEST_MODE=1, which swaps only the outbound
 * Coinbase and OpenAI clients for in-process fakes. No test performs a network
 * call to a third-party API.
 */

import { defineConfig, devices } from '@playwright/test'

import { BACKEND_PORT, BACKEND_URL, BASE_URL, FRONTEND_PORT } from './e2e/support/env'

/** Python interpreter from the backend virtualenv, overridable in CI. */
const PYTHON = process.env.E2E_PYTHON ?? './venv/bin/python'

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  timeout: 45_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // Pinned so currency formatting and date labels are deterministic.
    locale: 'en-GB',
    timezoneId: 'UTC',
    // Escape hatch for running the suite against a Chrome already on the
    // machine, when `npx playwright install` cannot fetch its pinned build.
    // Unset by default, so CI and a normal checkout are unaffected.
    ...(process.env.E2E_CHROME_PATH
      ? { launchOptions: { executablePath: process.env.E2E_CHROME_PATH } }
      : {}),
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    // Firefox and WebKit are declared but skipped unless their browsers are
    // installed; run `npx playwright install firefox webkit` to enable them.
    ...(process.env.E2E_ALL_BROWSERS
      ? [
          { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
          { name: 'webkit', use: { ...devices['Desktop Safari'] } },
        ]
      : []),
  ],

  webServer: [
    {
      // Backend in test mode: fake Coinbase/OpenAI clients, real HTTP stack.
      command: `${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT} --log-level warning`,
      cwd: 'server_py',
      url: `${BACKEND_URL}/`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        CRYPTO_VIEWER_TEST_MODE: '1',
        // Guard rails: even if a code path slipped past the fakes, there are no
        // credentials for it to use.
        COINBASE_API_KEY: '',
        COINBASE_API_SECRET: '',
        OPENAI_API_KEY: '',
      },
    },
    {
      // Production build served with the same /api proxy as the dev server.
      command: `npm run build && npx vite preview --port ${FRONTEND_PORT} --strictPort`,
      url: BASE_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: { VITE_API_PROXY_TARGET: BACKEND_URL },
    },
  ],
})
