/**
 * Backend scenario control for the E2E suite.
 *
 * The FastAPI backend runs with fake Coinbase/OpenAI clients. Which fixture
 * behaviour those fakes exhibit is chosen per browser context by a cookie, so
 * tests stay parallel-safe: one context's "simulate an outage" never leaks into
 * another's.
 *
 * Keep these values in sync with server_py/app/services/fakes/scenarios.py.
 */

import type { BrowserContext } from '@playwright/test'

export const SCENARIO_COOKIE = 'cv_test_scenario'

export const Scenario = {
  /** Portfolio returns an empty list. */
  emptyPortfolio: 'empty-portfolio',

  /** Upstream failures. */
  errorPortfolio: 'error-portfolio',
  errorPrices: 'error-prices',
  errorHistorical: 'error-historical',
  errorAi: 'error-ai',
  /** OpenAI call fails but the service degrades to its fallback string. */
  degradedAi: 'degraded-ai',

  /** Delayed responses (~1.2s), long enough to observe loading states. */
  slowPortfolio: 'slow-portfolio',
  slowPrices: 'slow-prices',
  slowHistorical: 'slow-historical',
  slowAi: 'slow-ai',
  slowAll: 'slow',
} as const

export type ScenarioFlag = (typeof Scenario)[keyof typeof Scenario]

/**
 * Apply one or more scenario flags to a browser context. Must be called before
 * the page navigates, since the cookie is read on each API request.
 */
export async function useScenario(
  context: BrowserContext,
  ...flags: ScenarioFlag[]
): Promise<void> {
  await context.addCookies([
    {
      name: SCENARIO_COOKIE,
      value: flags.join(','),
      domain: '127.0.0.1',
      path: '/',
    },
  ])
}
