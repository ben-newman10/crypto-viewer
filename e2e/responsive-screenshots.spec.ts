/**
 * Responsive rendering checks and screenshot capture.
 *
 * Asserts the layout adapts correctly at each breakpoint (table on wide
 * viewports, stacked cards on mobile, no horizontal overflow anywhere) and
 * writes a full-page screenshot of every view/breakpoint pair to
 * `screenshots/`.
 */

import { expect, test } from './support/fixtures'
import { BREAKPOINTS, captureFullPage } from './support/screenshots'
import { Scenario, useScenario } from './support/scenarios'

/** The page must never scroll sideways at any supported width. */
async function expectNoHorizontalOverflow(page: import('@playwright/test').Page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  // One pixel of slack for sub-pixel rounding.
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1)
}

for (const breakpoint of BREAKPOINTS) {
  test.describe(`${breakpoint.name} (${breakpoint.width}px)`, () => {
    test.use({ viewport: { width: breakpoint.width, height: breakpoint.height } })

    test('dashboard lays out correctly', async ({ page }) => {
      await page.goto('/')
      await page.getByTestId('recommendations-content').waitFor()

      // Both presentations are in the DOM; CSS decides which one is shown, so
      // assert on visibility rather than presence.
      const rows = page.getByTestId('holding-row')
      const cards = page.getByTestId('holding-card')
      await expect(rows).toHaveCount(4)
      await expect(cards).toHaveCount(4)

      if (breakpoint.name === 'mobile') {
        // Table columns are unreadable at 375px, so holdings stack as cards.
        await expect(cards.first()).toBeVisible()
        await expect(rows.first()).toBeHidden()
      } else {
        await expect(rows.first()).toBeVisible()
        await expect(cards.first()).toBeHidden()
      }

      await expectNoHorizontalOverflow(page)
      await captureFullPage(page, `dashboard-${breakpoint.name}`)
    })

    test('coin detail lays out correctly', async ({ page }) => {
      await page.goto('/coin/BTC')
      await page.getByTestId('price-chart').waitFor()

      await expect(page.getByTestId('coin-price')).toBeVisible()
      await expectNoHorizontalOverflow(page)
      await captureFullPage(page, `coin-detail-${breakpoint.name}`)
    })

    test('empty state lays out correctly', async ({ page, context }) => {
      await useScenario(context, Scenario.emptyPortfolio)
      await page.goto('/')
      await page.getByTestId('portfolio-empty').waitFor()

      await expectNoHorizontalOverflow(page)
      await captureFullPage(page, `dashboard-empty-${breakpoint.name}`)
    })

    test('error state lays out correctly', async ({ page, context }) => {
      await useScenario(context, Scenario.errorPortfolio, Scenario.errorAi)
      await page.goto('/')
      await page.getByTestId('portfolio-error').waitFor()
      await page.getByTestId('recommendations-error').waitFor()

      await expectNoHorizontalOverflow(page)
      await captureFullPage(page, `dashboard-error-${breakpoint.name}`)
    })
  })
}

test.describe('Additional screenshots', () => {
  test('captures the loading state', async ({ page, context }) => {
    await useScenario(context, Scenario.slowAll)
    await page.goto('/')

    await page.getByTestId('holding-row-skeleton').first().waitFor()
    await captureFullPage(page, 'dashboard-loading-desktop')
  })

  test('captures dark mode', async ({ page }) => {
    await page.addInitScript(() => window.localStorage.setItem('chakra-ui-color-mode', 'dark'))

    await page.goto('/')
    await page.getByTestId('recommendations-content').waitFor()
    await captureFullPage(page, 'dashboard-dark-desktop')

    await page.goto('/coin/SOL')
    await page.getByTestId('price-chart').waitFor()
    await captureFullPage(page, 'coin-detail-dark-desktop')
  })
})
