/**
 * Coin detail view: navigation from the dashboard, price figures, the 24-hour
 * chart and its accessible data-table alternative.
 */

import { expect, test } from './support/fixtures'
import { Scenario, useScenario } from './support/scenarios'

test.describe('Coin detail', () => {
  test('navigates from a holding to its detail page', async ({ page }) => {
    await page.goto('/')

    await page
      .getByTestId('holding-row')
      .filter({ hasText: 'ETH' })
      .getByRole('link', { name: /ETH/ })
      .click()

    await expect(page).toHaveURL(/\/coin\/ETH$/)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Ethereum (ETH)')
  })

  test('shows price, movement and the holding position', async ({ page }) => {
    await page.goto('/coin/BTC')

    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Bitcoin (BTC)')
    await expect(page.getByTestId('coin-price')).toContainText('£52,341.87')
    await expect(page.getByTestId('coin-price')).toContainText('+2.34%')
    await expect(page.getByTestId('coin-balance')).toContainText('0.4523 BTC')
    await expect(page.getByTestId('coin-value')).toContainText('£23,674.23')
  })

  test('renders a chart with an accessible summary and table alternative', async ({ page }) => {
    await page.goto('/coin/SOL')

    const chart = page.getByTestId('price-chart')
    await expect(chart).toBeVisible()
    // The canvas itself is inert; the wrapper carries the description.
    await expect(chart).toHaveAttribute('role', 'img')
    await expect(chart).toHaveAttribute('aria-label', /Line chart of SOL price/)

    const toggle = page.getByRole('button', { name: 'View price data as a table' })
    await expect(toggle).toHaveAttribute('aria-expanded', 'false')

    await toggle.click()
    await expect(page.getByRole('button', { name: 'Hide price data table' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )

    const table = page.getByRole('table', { name: /Hourly SOL closing prices/ })
    await expect(table).toBeVisible()
    await expect(table.getByRole('row')).toHaveCount(25) // header + 24 candles
  })

  test('treats a cash balance as having no market history', async ({ page }) => {
    await page.goto('/coin/GBP')

    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Pound sterling (GBP)')
    await expect(page.getByTestId('coin-chart-cash')).toContainText('No price history for cash')
    await expect(page.getByTestId('price-chart')).toHaveCount(0)
  })

  test('reports an unpriced pair without breaking the page', async ({ page, context }) => {
    await useScenario(context, Scenario.errorPrices)
    await page.goto('/coin/BTC')

    const error = page.getByTestId('coin-price-error')
    await expect(error).toBeVisible()
    await expect(error).toContainText("We couldn't price BTC")
    await expect(error.getByRole('button', { name: 'Try again' })).toBeVisible()
  })

  test('keeps current figures when only the candle history fails', async ({ page, context }) => {
    await useScenario(context, Scenario.errorHistorical)
    await page.goto('/coin/BTC')

    // Headline price still resolves...
    await expect(page.getByTestId('coin-price')).toContainText('£52,341.87')
    // ...while the chart degrades to a retryable error.
    const chartError = page.getByTestId('coin-chart-error')
    await expect(chartError).toBeVisible()
    await expect(chartError).toContainText('Price history is unavailable')
  })

  test('renders a not-found page for an unknown route', async ({ page }) => {
    await page.goto('/does-not-exist')
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Page not found')
    await page.getByRole('link', { name: 'Back to dashboard' }).click()
    await expect(page).toHaveURL(/\/$/)
  })
})
