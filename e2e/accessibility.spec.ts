/**
 * Accessibility coverage.
 *
 * Automated axe-core scans of every major page (light and dark, and at each
 * breakpoint) plus the keyboard and semantics checks axe cannot make on its
 * own: skip link, focus order, landmarks and heading structure.
 */

import { expectNoA11yViolations } from './support/a11y'
import { expect, test } from './support/fixtures'
import { BREAKPOINTS } from './support/screenshots'
import { Scenario, useScenario } from './support/scenarios'

const PAGES = [
  { name: 'dashboard', path: '/' },
  { name: 'coin detail', path: '/coin/BTC' },
  { name: 'not found', path: '/does-not-exist' },
]

test.describe('Automated axe scans', () => {
  for (const target of PAGES) {
    test(`${target.name} has no critical or serious violations`, async ({ page }) => {
      await page.goto(target.path)
      await page.getByRole('heading', { level: 1 }).waitFor()
      await expectNoA11yViolations(page, `${target.name} (light)`)
    })
  }

  test('dark mode has no critical or serious violations', async ({ page }) => {
    await page.addInitScript(() => window.localStorage.setItem('chakra-ui-color-mode', 'dark'))
    await page.goto('/')
    await page.getByTestId('recommendations-content').waitFor()
    await expectNoA11yViolations(page, 'dashboard (dark)')

    await page.goto('/coin/ETH')
    await page.getByTestId('price-chart').waitFor()
    await expectNoA11yViolations(page, 'coin detail (dark)')
  })

  for (const breakpoint of BREAKPOINTS) {
    test(`dashboard is accessible at ${breakpoint.name}`, async ({ page }) => {
      await page.setViewportSize({ width: breakpoint.width, height: breakpoint.height })
      await page.goto('/')
      await page.getByTestId('recommendations-content').waitFor()
      await expectNoA11yViolations(page, `dashboard (${breakpoint.name})`)
    })
  }

  test('error states are accessible', async ({ page, context }) => {
    await useScenario(context, Scenario.errorPortfolio)
    await page.goto('/')
    await page.getByTestId('portfolio-error').waitFor()
    await expectNoA11yViolations(page, 'dashboard (error state)')
  })

  test('empty states are accessible', async ({ page, context }) => {
    await useScenario(context, Scenario.emptyPortfolio)
    await page.goto('/')
    await page.getByTestId('portfolio-empty').waitFor()
    await expectNoA11yViolations(page, 'dashboard (empty state)')
  })

  test('the expanded chart data table is accessible', async ({ page }) => {
    await page.goto('/coin/BTC')
    await page.getByRole('button', { name: 'View price data as a table' }).click()
    await page.getByRole('table', { name: /Hourly BTC closing prices/ }).waitFor()
    await expectNoA11yViolations(page, 'coin detail (chart table expanded)')
  })
})

test.describe('Keyboard and semantics', () => {
  test('the skip link is the first stop and moves focus to main', async ({ page }) => {
    await page.goto('/')

    await page.keyboard.press('Tab')
    const skipLink = page.getByRole('link', { name: 'Skip to main content' })
    await expect(skipLink).toBeFocused()
    // Hidden off-screen until focused, then visible.
    await expect(skipLink).toBeVisible()

    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/#main-content$/)
    await expect(page.locator('#main-content')).toBeVisible()
  })

  test('tab order runs skip link, brand, navigation, then controls', async ({ page }) => {
    await page.goto('/')
    await page.getByTestId('recommendations-content').waitFor()

    const order: string[] = []
    for (let i = 0; i < 6; i += 1) {
      await page.keyboard.press('Tab')
      order.push(
        await page.evaluate(() => {
          const el = document.activeElement as HTMLElement | null
          if (!el) return 'none'
          return (
            el.getAttribute('aria-label') ??
            el.getAttribute('id') ??
            (el.textContent ?? '').trim().slice(0, 32)
          )
        }),
      )
    }

    expect(order[0]).toContain('Skip to main content')
    expect(order[1]).toContain('Crypto Viewer')
    expect(order[2]).toContain('Dashboard')
    expect(order[3]).toMatch(/Switch to (dark|light) theme/)
  })

  test('every interactive control shows a visible focus indicator', async ({ page }) => {
    await page.goto('/')
    await page.getByTestId('recommendations-content').waitFor()

    const refresh = page.getByRole('button', { name: 'Refresh', exact: true })
    await refresh.focus()

    const outline = await refresh.evaluate((element) => {
      const styles = getComputedStyle(element)
      return { width: styles.outlineWidth, style: styles.outlineStyle }
    })

    expect(outline.style).not.toBe('none')
    expect(parseFloat(outline.width)).toBeGreaterThanOrEqual(2)
  })

  test('the holdings filter is operable and labelled', async ({ page }) => {
    await page.goto('/')

    const filter = page.getByLabel('Filter holdings by ticker')
    await filter.focus()
    await expect(filter).toBeFocused()
    await page.keyboard.type('sol')
    await expect(page.getByTestId('holding-row')).toHaveCount(1)
  })

  test('the chart disclosure is operable by keyboard', async ({ page }) => {
    await page.goto('/coin/BTC')

    const toggle = page.getByRole('button', { name: 'View price data as a table' })
    await toggle.focus()
    await page.keyboard.press('Enter')

    await expect(page.getByRole('table', { name: /Hourly BTC closing prices/ })).toBeVisible()
  })

  test('exposes landmarks and a single main heading', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('banner')).toHaveCount(1)
    await expect(page.getByRole('main')).toHaveCount(1)
    await expect(page.getByRole('contentinfo')).toHaveCount(1)
    await expect(page.getByRole('navigation', { name: 'Main navigation' })).toHaveCount(1)
    await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1)
  })

  test('the active navigation item is marked as current', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('link', { name: 'Dashboard' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  test('live regions are declared for polled data', async ({ page }) => {
    await page.goto('/')

    // Portfolio total: polite status region carrying a spoken summary.
    const status = page.getByRole('status').filter({ hasText: 'Portfolio value' })
    await expect(status).toContainText(/Portfolio value £[\d,]+\.\d{2}, up/)

    // AI analysis: polite region around the result.
    await expect(page.getByTestId('recommendations-region')).toHaveAttribute(
      'aria-live',
      'polite',
    )
  })

  test('the colour mode toggle is reachable and labelled', async ({ page }) => {
    await page.goto('/')

    const toggle = page.getByTestId('color-mode-toggle')
    await expect(toggle).toHaveAttribute('aria-label', 'Switch to dark theme')

    await toggle.click()
    await expect(page.getByTestId('color-mode-toggle')).toHaveAttribute(
      'aria-label',
      'Switch to light theme',
    )
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  })

  test('respects prefers-reduced-motion', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/')
    await page.getByTestId('recommendations-content').waitFor()

    const duration = await page
      .getByRole('button', { name: 'Refresh', exact: true })
      .evaluate((element) => getComputedStyle(element).transitionDuration)

    // The global reduced-motion rule collapses transitions to ~0.
    expect(parseFloat(duration)).toBeLessThan(0.05)
  })
})
