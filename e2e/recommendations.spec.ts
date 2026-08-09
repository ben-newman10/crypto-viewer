/**
 * AI analysis flow.
 *
 * The backend runs with a fake model that returns *structured JSON* matching
 * the real schema, and builds its supporting facts out of the same grounding
 * context the server verifies against. So these tests exercise the whole
 * pipeline — grounding, verification, confidence clamping, rendering — rather
 * than a fixture blob shown on a page.
 */

import type { Page } from '@playwright/test'

import { expect, test } from './support/fixtures'
import { Scenario, useScenario, type ScenarioFlag } from './support/scenarios'

/** The payload the page is rendering, read back from the API. */
async function readPayload(page: Page) {
  const response = await page.request.get('/api/recommendations/')
  expect(response.ok()).toBeTruthy()
  return response.json()
}

function card(page: Page, symbol: string) {
  return page.locator(`[data-testid="recommendation-card"][data-symbol="${symbol}"]`)
}

test.describe('AI analysis', () => {
  test('renders one structured call per holding', async ({ page }) => {
    await page.goto('/')

    const content = page.getByTestId('recommendations-content')
    await expect(content).toBeVisible()

    const cards = page.getByTestId('recommendation-card')
    await expect(cards).toHaveCount(3)
    await expect(cards.nth(0)).toHaveAttribute('data-symbol', 'BTC')
    await expect(cards.nth(1)).toHaveAttribute('data-symbol', 'ETH')
    await expect(cards.nth(2)).toHaveAttribute('data-symbol', 'SOL')

    // A direction and a rationale on every card.
    await expect(page.getByTestId('action-badge')).toHaveCount(3)
    await expect(page.getByTestId('confidence-rationale')).toHaveCount(3)
  })

  test('keeps the document outline ordered under the panel heading', async ({ page }) => {
    await page.goto('/')
    const content = page.getByTestId('recommendations-content')

    // The panel's own heading is the h2; each asset is an h3 beneath it.
    await expect(content.getByRole('heading', { level: 3 })).toHaveCount(3)
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

    await page.getByTestId('recommendations-refresh').click()

    // Busy state is exposed on the live region while the request is in flight.
    await expect(page.getByTestId('recommendations-region')).toHaveAttribute('aria-busy', 'true')
    await expect(page.getByRole('button', { name: 'Analysing' })).toBeVisible()

    await expect(page.getByTestId('recommendations-region')).toHaveAttribute('aria-busy', 'false')
    await expect(page.getByTestId('recommendation-card')).toHaveCount(3)
  })
})

test.describe('Confidence rating', () => {
  test('renders a distinct badge for each level', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByTestId('recommendation-card')).toHaveCount(3)

    // The fixture model rates the three holdings differently on purpose, so a
    // single load covers all three badge states.
    await expect(card(page, 'BTC').getByTestId('confidence-badge')).toHaveAttribute(
      'data-value',
      'high',
    )
    await expect(card(page, 'ETH').getByTestId('confidence-badge')).toHaveAttribute(
      'data-value',
      'medium',
    )
    await expect(card(page, 'SOL').getByTestId('confidence-badge')).toHaveAttribute(
      'data-value',
      'low',
    )
  })

  test('states the level in words, not by colour alone', async ({ page }) => {
    await page.goto('/')

    await expect(card(page, 'BTC').getByTestId('confidence-badge')).toHaveText(
      /High confidence/,
    )
    await expect(card(page, 'SOL').getByTestId('confidence-badge')).toHaveText(/Low confidence/)
    await expect(card(page, 'SOL').getByTestId('action-badge')).toHaveText(/Sell/)
  })

  test('is lowered when a market data source is missing', async ({ page, context }) => {
    await useScenario(context, Scenario.errorMarketContext)
    await page.goto('/')
    await expect(page.getByTestId('recommendation-card')).toHaveCount(3)

    // The model still rated BTC "high"; sentiment and market-structure data
    // were unavailable, so the served rating is capped at medium.
    const btc = card(page, 'BTC')
    await expect(btc.getByTestId('confidence-badge')).toHaveAttribute('data-value', 'medium')

    const capped = btc.getByTestId('confidence-capped')
    await expect(capped).toBeVisible()
    await expect(capped).toContainText('The model rated this high')
    // Named in words rather than by the payload's snake_case category key.
    await expect(capped).toContainText('market mood')

    const payload = await readPayload(page)
    const record = payload.recommendations.find((item: { symbol: string }) => item.symbol === 'BTC')
    expect(record.model_confidence).toBe('high')
    expect(record.confidence).toBe('medium')
  })

  test('drops to low across the board when grounding data is thin', async ({ page, context }) => {
    await useScenario(context, Scenario.partialData)
    await page.goto('/')

    const cards = page.getByTestId('recommendation-card')
    await expect(cards).toHaveCount(3)

    const badges = page.getByTestId('confidence-badge')
    for (let index = 0; index < 3; index += 1) {
      await expect(badges.nth(index)).toHaveAttribute('data-value', 'low')
    }

    // And the reason is on the page, not just in the payload.
    await expect(card(page, 'BTC').getByTestId('confidence-capped')).toContainText('price trend')

    const payload = await readPayload(page)
    for (const record of payload.recommendations) {
      expect(record.confidence).toBe('low')
      expect(record.data_completeness).toBeLessThan(0.5)
    }
  })
})

test.describe('Supporting facts', () => {
  test('are hidden behind a disclosure and open on click', async ({ page }) => {
    await page.goto('/')

    const btc = card(page, 'BTC')
    const toggle = btc.getByTestId('supporting-facts-toggle')

    await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await expect(btc.getByTestId('supporting-facts')).toBeHidden()

    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await expect(btc.getByTestId('supporting-facts')).toBeVisible()
  })

  test('are operable by keyboard', async ({ page }) => {
    await page.goto('/')

    const toggle = card(page, 'ETH').getByTestId('supporting-facts-toggle')
    await toggle.focus()
    await page.keyboard.press('Enter')

    await expect(card(page, 'ETH').getByTestId('supporting-facts')).toBeVisible()
  })

  test('show the same values the API served', async ({ page }) => {
    await page.goto('/')
    await card(page, 'BTC').getByTestId('supporting-facts-toggle').click()

    const payload = await readPayload(page)
    const btc = payload.recommendations.find((item: { symbol: string }) => item.symbol === 'BTC')
    expect(btc.supporting_facts.length).toBeGreaterThan(0)

    const rows = card(page, 'BTC').getByTestId('supporting-fact')
    await expect(rows).toHaveCount(btc.supporting_facts.length)

    for (const fact of btc.supporting_facts) {
      const row = card(page, 'BTC').locator(`[data-metric="${fact.metric}"]`)
      // The field name is on the page, so a reader can trace the claim back.
      await expect(row).toContainText(fact.metric)
      await expect(row.getByTestId('fact-value')).toHaveText(fact.value)
    }
  })

  test('explain what each figure means, behind a second disclosure', async ({ page }) => {
    // A reader who does not know what RSI is cannot judge a call built on it.
    // The definition is authored server-side, so it is present on every fact.
    await page.goto('/')
    await card(page, 'BTC').getByTestId('supporting-facts-toggle').click()

    const payload = await readPayload(page)
    const btc = payload.recommendations.find((item: { symbol: string }) => item.symbol === 'BTC')
    for (const fact of btc.supporting_facts) {
      expect(fact.plain, `${fact.metric} has no plain-English definition`).toBeTruthy()
    }

    const row = card(page, 'BTC').locator(`[data-metric="${btc.supporting_facts[0].metric}"]`)
    const toggle = row.getByTestId('fact-definition-toggle')

    await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await expect(row.getByTestId('fact-definition')).toBeHidden()

    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await expect(row.getByTestId('fact-definition')).toBeVisible()
    await expect(row.getByTestId('fact-definition')).toContainText(btc.supporting_facts[0].plain)
  })

  test('definitions are operable by keyboard and named individually', async ({ page }) => {
    await page.goto('/')
    const btc = card(page, 'BTC')
    await btc.getByTestId('supporting-facts-toggle').click()

    const payload = await readPayload(page)
    const record = payload.recommendations.find(
      (item: { symbol: string }) => item.symbol === 'BTC',
    )
    const first = record.supporting_facts[0]
    const row = btc.locator(`[data-metric="${first.metric}"]`)
    const toggle = row.getByTestId('fact-definition-toggle')

    // The visible label is identical on every row, so the accessible name has
    // to say which figure it belongs to.
    await expect(toggle).toHaveAccessibleName(`What is ${first.label}?`)

    await toggle.focus()
    await page.keyboard.press('Enter')
    await expect(row.getByTestId('fact-definition')).toBeVisible()
  })

  test('cite fields that exist in the grounding data', async ({ page }) => {
    await page.goto('/')
    const payload = await readPayload(page)

    // Nothing survives to the page that the server could not verify.
    expect(payload.groundedness.status).toBe('verified')
    expect(payload.groundedness.violations).toEqual([])
    for (const item of payload.recommendations) {
      for (const fact of item.supporting_facts) {
        expect(fact.verified).toBe(true)
      }
    }
  })
})

test.describe('Groundedness check', () => {
  test('corrects a fabricated figure and lowers the confidence for it', async ({
    page,
    context,
  }) => {
    await useScenario(context, Scenario.ungroundedAi)
    await page.goto('/')
    await expect(page.getByTestId('recommendation-card')).toHaveCount(3)

    const payload = await readPayload(page)
    expect(payload.groundedness.status).toBe('corrected')
    expect(payload.groundedness.retried).toBe(true)
    expect(payload.groundedness.facts_corrected).toBeGreaterThan(0)

    // BTC's data supports "high", but the model misquoted its own evidence.
    const btc = card(page, 'BTC')
    await expect(btc.getByTestId('confidence-badge')).toHaveAttribute('data-value', 'medium')
    await expect(btc.getByTestId('verification-note')).toBeVisible()

    await btc.getByTestId('supporting-facts-toggle').click()
    await expect(btc.getByTestId('fact-corrected').first()).toBeVisible()

    await expect(page.getByTestId('groundedness-note')).toContainText('corrected')
  })

  test('never renders a figure the app did not measure', async ({ page, context }) => {
    await useScenario(context, Scenario.ungroundedAi)
    await page.goto('/')

    await card(page, 'BTC').getByTestId('supporting-facts-toggle').click()

    const payload = await readPayload(page)
    const btc = payload.recommendations.find((item: { symbol: string }) => item.symbol === 'BTC')

    for (const fact of btc.supporting_facts) {
      const row = card(page, 'BTC').locator(`[data-metric="${fact.metric}"]`)
      await expect(row.getByTestId('fact-value')).toHaveText(fact.value)
      if (fact.model_stated_value) {
        // The model's number is recorded for the audit trail but never shown.
        await expect(row).not.toContainText(fact.model_stated_value)
      }
    }

    // The invented field the fake cited is absent from the page entirely.
    await expect(page.getByTestId('recommendations-content')).not.toContainText(
      'exchange_netflow_7d',
    )
  })

  test('reports a clean run as fully checked', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByTestId('groundedness-note')).toContainText(
      /All \d+ supporting figures were checked/,
    )
  })
})

test.describe('Disclaimer', () => {
  const cases: { name: string; flags: ScenarioFlag[] }[] = [
    { name: 'a normal run', flags: [] },
    { name: 'thin grounding data', flags: [Scenario.partialData] },
    { name: 'a corrected run', flags: [Scenario.ungroundedAi] },
    { name: 'an unavailable model', flags: [Scenario.degradedAi] },
    { name: 'an empty portfolio', flags: [Scenario.emptyPortfolio] },
  ]

  for (const { name, flags } of cases) {
    test(`is visible with the recommendations for ${name}`, async ({ page, context }) => {
      if (flags.length) await useScenario(context, ...flags)
      await page.goto('/')

      const disclaimer = page.getByTestId('recommendations-disclaimer')
      await expect(disclaimer).toBeVisible()
      await expect(disclaimer).toContainText('not financial advice')

      // Attached to the analysis panel itself, not relegated to a page footer.
      await expect(
        page.getByTestId('recommendations-content').getByTestId('recommendations-disclaimer'),
      ).toHaveCount(1)

      // Identical text on every path, because the server injects it as a
      // constant rather than the model producing it.
      const payload = await readPayload(page)
      await expect(disclaimer).toContainText(payload.disclaimer)
    })
  }
})

test.describe('Failure handling', () => {
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

  test('explains in place when the model is unreachable', async ({ page, context }) => {
    await useScenario(context, Scenario.degradedAi)
    await page.goto('/')

    // Not an error state: the portfolio data is still good.
    await expect(page.getByTestId('recommendations-message')).toContainText(
      'Unable to generate recommendations at this time',
    )
    await expect(page.getByTestId('recommendations-error')).toHaveCount(0)
    await expect(page.getByTestId('recommendation-card')).toHaveCount(0)
  })

  test('reports that there is nothing to analyse for an empty portfolio', async ({
    page,
    context,
  }) => {
    await useScenario(context, Scenario.emptyPortfolio)
    await page.goto('/')

    await expect(page.getByTestId('recommendations-message')).toContainText(
      'No cryptocurrency holdings found',
    )
  })

  test('still produces calls, at low confidence, when the candle feed is down', async ({
    page,
    context,
  }) => {
    await useScenario(context, Scenario.errorHistorical)
    await page.goto('/')

    // Missing indicators are a confidence problem, not an outage.
    await expect(page.getByTestId('recommendation-card')).toHaveCount(3)
    await expect(card(page, 'BTC').getByTestId('confidence-badge')).toHaveAttribute(
      'data-value',
      'low',
    )
  })
})
