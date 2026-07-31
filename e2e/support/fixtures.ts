/**
 * Shared test fixtures.
 *
 * Every test in the suite gets a network guard that fails if the browser ever
 * tries to reach a host other than the local frontend/backend. That is the
 * enforcement behind "no test calls Coinbase or OpenAI for real" — it is
 * checked, not assumed.
 */

import { test as base, expect, type Page } from '@playwright/test'

import { BACKEND_URL } from './env'

/** Hosts the app is allowed to talk to during a test run. */
const ALLOWED_HOSTS = new Set(['127.0.0.1', 'localhost'])

/** Called out explicitly so a leak produces an unmistakable failure message. */
const FORBIDDEN_HOST_PATTERNS = [/coinbase/i, /openai/i]

export interface Fixtures {
  /** Requests to non-local hosts observed during the test. */
  externalRequests: string[]
}

export const test = base.extend<Fixtures>({
  externalRequests: [
    async ({ page }, use) => {
      const external: string[] = []

      page.on('request', (request) => {
        const url = request.url()
        // data:, blob: and about: URLs never leave the browser.
        if (!/^https?:/i.test(url)) return

        const { hostname } = new URL(url)
        if (!ALLOWED_HOSTS.has(hostname)) external.push(url)
      })

      await use(external)

      // Asserted after the test body so a leak fails the test that caused it.
      const thirdParty = external.filter((url) =>
        FORBIDDEN_HOST_PATTERNS.some((pattern) => pattern.test(url)),
      )
      expect(
        thirdParty,
        'no request may reach Coinbase or OpenAI during an E2E run',
      ).toEqual([])
      expect(external, 'no request may leave the local test stack').toEqual([])
    },
    { auto: true },
  ],
})

export { expect }

/**
 * Confirm the backend under test is running with fake third-party clients.
 * A green suite against a live-credential backend would prove nothing.
 */
export async function assertBackendInTestMode(page: Page): Promise<void> {
  const response = await page.request.get(`${BACKEND_URL}/`)
  expect(response.ok()).toBeTruthy()
  const body = (await response.json()) as { test_mode?: boolean }
  expect(body.test_mode, 'backend must run with CRYPTO_VIEWER_TEST_MODE=1').toBe(true)
}
