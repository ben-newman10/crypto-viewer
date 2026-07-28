/**
 * AI analysis flow: initial generation, explicit re-trigger, and graceful
 * handling of an upstream model failure.
 */

import { expect, test } from './support/fixtures'
import { Scenario, useScenario } from './support/scenarios'

test.describe('AI analysis', () => {
  test('renders the generated analysis as formatted content', async ({ page }) => {
    await page.goto('/')

    const content = page.getByTestId('recommendations-content')
    await expect(content).toBeVisible()
    await expect(content).toContainText('Portfolio Overview')
    await expect(content).toContainText('BTC — Hold.')

    // Markdown headings are shifted below the panel's own <h2> so the document
    // outline has no skipped levels: `##` becomes h3 and `###` becomes h4.
    await expect(content.getByRole('heading', { level: 3 })).toHaveCount(1)
    await expect(content.getByRole('heading', { level: 4 })).toHaveCount(3)
    await expect(content.getByRole('heading', { level: 2 })).toHaveCount(0)
  })

  test('announces results politely for screen readers', async ({ page }) => {
    await page.goto('/')

    const region = page.getByTestId('recommendations-region')
    await expect(region).toHaveAttribute('aria-live', 'polite')
    await expect(region).toHaveAttribute('aria-busy', 'false')
  })

  test('can be re-triggered and shows progress while it runs', async ({ page, context }) => {
    await useScenario(context, Scenario.slowAi)
    await page.goto('/')

    // First generation shows a skeleton rather than a blank panel.
    await expect(page.getByTestId('recommendations-loading')).toBeVisible()
    await expect(page.getByTestId('recommendations-content')).toBeVisible()

    const refresh = page.getByTestId('recommendations-refresh')
    await refresh.click()

    // Busy state is exposed on the live region while the request is in flight.
    await expect(page.getByTestId('recommendations-region')).toHaveAttribute(
      'aria-busy',
      'true',
    )
    await expect(page.getByRole('button', { name: 'Analysing' })).toBeVisible()

    await expect(page.getByTestId('recommendations-region')).toHaveAttribute(
      'aria-busy',
      'false',
    )
    await expect(page.getByTestId('recommendations-content')).toContainText(
      'Portfolio Overview',
    )
  })

  test('handles a simulated model failure with an in-place retry', async ({ page, context }) => {
    await useScenario(context, Scenario.errorAi)
    await page.goto('/')

    const error = page.getByTestId('recommendations-error')
    await expect(error).toBeVisible()
    await expect(error).toContainText('Analysis is unavailable')
    await expect(error).toHaveAttribute('role', 'alert')

    // The failure is contained: the portfolio panel still works.
    await expect(page.getByTestId('holding-row')).toHaveCount(4)

    // Retrying re-issues the request (and fails again under this scenario,
    // which is the point: the UI must not get stuck).
    await error.getByRole('button', { name: 'Try again' }).click()
    await expect(page.getByTestId('recommendations-error')).toBeVisible()
  })

  test('surfaces the service-level fallback text when the model degrades', async ({
    page,
    context,
  }) => {
    await useScenario(context, Scenario.degradedAi)
    await page.goto('/')

    await expect(page.getByTestId('recommendations-content')).toContainText(
      'Unable to generate recommendations at this time',
    )
  })

  test('reports that there is nothing to analyse for an empty portfolio', async ({
    page,
    context,
  }) => {
    await useScenario(context, Scenario.emptyPortfolio)
    await page.goto('/')

    await expect(page.getByTestId('recommendations-content')).toContainText(
      'No cryptocurrency holdings found',
    )
  })
})
