/**
 * Loading and error states for every major async view.
 *
 * Delays and failures are produced by the backend's fake clients, so these
 * tests exercise the same code path a real outage would.
 */

import { expect, test } from './support/fixtures'
import { Scenario, useScenario } from './support/scenarios'

test.describe('Loading states', () => {
  test('the dashboard shows skeletons rather than a blank screen', async ({
    page,
    context,
  }) => {
    await useScenario(context, Scenario.slowPortfolio, Scenario.slowAi)
    await page.goto('/')

    await expect(page.getByTestId('holding-row-skeleton').first()).toBeVisible()
    await expect(page.getByTestId('recommendations-loading')).toBeVisible()

    // ...and resolve into real content.
    await expect(page.getByTestId('holding-row')).toHaveCount(4)
    await expect(page.getByTestId('holding-row-skeleton')).toHaveCount(0)
    await expect(page.getByTestId('recommendations-content')).toBeVisible()
  })

  test('holdings render before their prices arrive', async ({ page, context }) => {
    await useScenario(context, Scenario.slowPrices)
    await page.goto('/')

    // Balances come from the portfolio call and are shown immediately; the
    // price column fills in when the slower per-asset requests land.
    await expect(page.getByTestId('holding-row')).toHaveCount(4)
    await expect(page.getByTestId('metric-total-value')).toContainText('£37,853.88')
  })

  test('the coin chart shows a placeholder while candles load', async ({ page, context }) => {
    await useScenario(context, Scenario.slowHistorical)
    await page.goto('/coin/BTC')

    await expect(page.getByTestId('coin-chart-loading')).toBeVisible()
    await expect(page.getByTestId('price-chart')).toBeVisible()
  })
})

test.describe('Error states', () => {
  test('a failed portfolio fetch is announced and retryable', async ({ page, context }) => {
    await useScenario(context, Scenario.errorPortfolio)
    await page.goto('/')

    const error = page.getByTestId('portfolio-error')
    await expect(error).toBeVisible()
    await expect(error).toContainText("We couldn't load your portfolio")
    await expect(error).toHaveAttribute('role', 'alert')
    await expect(error.getByRole('button', { name: 'Try again' })).toBeEnabled()

    // Misleading zero-value figures are suppressed rather than shown as £0.00.
    await expect(page.getByTestId('metric-total-value')).toHaveCount(0)
  })

  test('a single failed price degrades one row, not the whole table', async ({
    page,
    context,
  }) => {
    await useScenario(context, Scenario.errorPrices)
    await page.goto('/')

    await expect(page.getByTestId('holding-row')).toHaveCount(4)

    const btc = page.getByTestId('holding-row').filter({ hasText: 'BTC' })
    await expect(btc).toContainText('Unavailable')
    // The cash row is unaffected because it needs no price lookup.
    await expect(page.getByTestId('holding-row').filter({ hasText: 'GBP' })).toContainText(
      '£1,250.75',
    )
    await expect(page.getByTestId('metric-assets')).toContainText('some prices unavailable')
  })

  test('recovers when a retry succeeds', async ({ page, context }) => {
    await useScenario(context, Scenario.errorPortfolio)
    await page.goto('/')
    await expect(page.getByTestId('portfolio-error')).toBeVisible()

    // Clear the failure scenario, then retry from the error panel itself.
    await context.clearCookies()
    await page.getByTestId('portfolio-error').getByRole('button', { name: 'Try again' }).click()

    await expect(page.getByTestId('holding-row')).toHaveCount(4)
    await expect(page.getByTestId('portfolio-error')).toHaveCount(0)
  })
})
