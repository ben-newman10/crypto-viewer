/**
 * Automated accessibility scanning with axe-core.
 *
 * `expectNoA11yViolations` fails on any critical or serious violation and
 * reports the offending rules and selectors so a failure is actionable without
 * opening the trace.
 */

import AxeBuilder from '@axe-core/playwright'
import { expect, type Page } from '@playwright/test'

/** WCAG 2.1 Level A and AA rule sets. */
const WCAG_AA_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

const BLOCKING_IMPACTS = new Set(['critical', 'serious'])

export interface A11yScanOptions {
  /** Restrict the scan to a CSS selector (defaults to the whole page). */
  include?: string
  /** Rules to skip, with a comment explaining why. */
  disableRules?: string[]
}

export async function expectNoA11yViolations(
  page: Page,
  label: string,
  options: A11yScanOptions = {},
): Promise<void> {
  let builder = new AxeBuilder({ page }).withTags(WCAG_AA_TAGS)

  if (options.include) builder = builder.include(options.include)
  if (options.disableRules?.length) builder = builder.disableRules(options.disableRules)

  const results = await builder.analyze()
  const blocking = results.violations.filter(
    (violation) => violation.impact && BLOCKING_IMPACTS.has(violation.impact),
  )

  const summary = blocking
    .map((violation) => {
      const targets = violation.nodes
        .slice(0, 5)
        .map((node) => node.target.join(' '))
        .join('\n      ')
      return `  • [${violation.impact}] ${violation.id}: ${violation.help}\n      ${targets}`
    })
    .join('\n')

  expect(
    blocking,
    `${label}: expected no critical or serious accessibility violations\n${summary}`,
  ).toEqual([])
}
