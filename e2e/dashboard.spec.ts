/**
 * Dashboard: holdings rendering, derived figures, sorting, filtering and the
 * live-refresh affordance.
 */

import { assertBackendInTestMode, expect, test } from './support/fixtures'
import { Scenario, useScenario } from './support/scenarios'

test.describe('Dashboard', () => {
  test('runs against a backend with faked third-party clients', async ({ page }) => {
    await assertBackendInTestMode(page)
  })

  test('renders the fixture holdings with derived values', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('heading', { level: 1, name: 'Your portfolio' })).toBeVisible()

    const rows = page.getByTestId('holding-row')
    await expect(rows).toHaveCount(4)

    // Highest value first (default sort), so BTC leads.
    const btc = rows.filter({ has: page.getByRole('rowheader', { name: /BTC/ }) })
    await expect(btc).toContainText('0.4523')
    await expect(btc).toContainText('£52,341.87')
    await expect(btc).toContainText('+2.34%')
    // 0.4523 BTC × £52,341.87
    await expect(btc).toContainText('£23,674.23')

    const eth = rows.filter({ has: page.getByRole('rowheader', { name: /ETH/ }) })
    await expect(eth).toContainText('−1.87%')
    await expect(eth).toContainText('£7,895.20')

    // The fiat balance is treated as cash: no price lookup, no 24h change.
    const gbp = rows.filter({ hasText: 'GBP' })
    await expect(gbp).toContainText('Cash')
    await expect(gbp).toContainText('£1,250.75')
  })

  test('summarises the portfolio total and 24-hour movement', async ({ page }) => {
    await page.goto('/')

    // 23,674.23 + 7,895.20 + 5,033.70 + 1,250.75
    await expect(page.getByTestId('metric-total-value')).toContainText('£37,853.88')
    await expect(page.getByTestId('metric-change')).toContainText('+£659.26')
    await expect(page.getByTestId('metric-assets')).toContainText('4')
  })

  test('conveys gains and losses without relying on colour', async ({ page }) => {
    await page.goto('/')

    const rows = page.getByTestId('holding-row')

    // 1. An explicit +/− sign in the visible text.
    await expect(rows.filter({ hasText: 'BTC' })).toContainText('+2.34%')
    await expect(rows.filter({ hasText: 'ETH' })).toContainText('−1.87%')

    // 2. A direction word exposed only to assistive technology.
    await expect(rows.filter({ hasText: 'SOL' })).toContainText(
      'up over the last 24 hours for SOL',
    )
    await expect(rows.filter({ hasText: 'ETH' })).toContainText(
      'down over the last 24 hours for ETH',
    )

    // 3. A direction triangle rendered alongside the figure.
    await expect(
      rows.filter({ hasText: 'SOL' }).locator('svg[aria-hidden="true"]'),
    ).not.toHaveCount(0)
  })

  test('sorts holdings by a column header', async ({ page }) => {
    await page.goto('/')

    const assetHeader = page.getByRole('columnheader', { name: /^Asset/ })
    const valueHeader = page.getByRole('columnheader', { name: /^Value/ })

    // Value is the default sort, descending.
    await expect(valueHeader).toHaveAttribute('aria-sort', 'descending')
    await expect(assetHeader).toHaveAttribute('aria-sort', 'none')

    await assetHeader.getByRole('button').click()
    await expect(assetHeader).toHaveAttribute('aria-sort', 'ascending')
    await expect(page.getByTestId('holding-row').first()).toContainText('BTC')

    await assetHeader.getByRole('button').click()
    await expect(assetHeader).toHaveAttribute('aria-sort', 'descending')
    await expect(page.getByTestId('holding-row').first()).toContainText('SOL')
  })

  test('filters holdings and offers a way back', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByTestId('holding-row')).toHaveCount(4)

    const filter = page.getByLabel('Filter holdings by ticker')
    await filter.fill('eth')
    await expect(page.getByTestId('holding-row')).toHaveCount(1)
    await expect(page.getByTestId('holding-row')).toContainText('ETH')

    await filter.fill('zzz')
    const noMatches = page.getByTestId('portfolio-no-matches')
    await expect(noMatches).toBeVisible()
    await expect(noMatches).toContainText('No assets match')

    await noMatches.getByRole('button', { name: 'Clear filter' }).click()
    await expect(page.getByTestId('holding-row')).toHaveCount(4)
  })

  test('refetches on demand', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByTestId('holding-row')).toHaveCount(4)

    const requests: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('/api/crypto/portfolio')) requests.push(request.url())
    })

    await page.getByRole('button', { name: 'Refresh', exact: true }).click()
    await expect.poll(() => requests.length).toBeGreaterThan(0)
    await expect(page.getByTestId('holding-row')).toHaveCount(4)
  })

  test('shows an empty state when there are no holdings', async ({ page, context }) => {
    await useScenario(context, Scenario.emptyPortfolio)
    await page.goto('/')

    const empty = page.getByTestId('portfolio-empty')
    await expect(empty).toBeVisible()
    await expect(empty).toContainText('No holdings yet')
    await expect(page.getByTestId('holding-row')).toHaveCount(0)
  })
})
