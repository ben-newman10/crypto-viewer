/**
 * Screenshot capture for the documented breakpoints.
 *
 * Images land in `screenshots/` at the repository root with predictable
 * `<view>-<breakpoint>.png` names. These are review artefacts, not visual
 * regression baselines, so they are captured rather than compared.
 */

import { mkdirSync } from 'node:fs'
import path from 'node:path'

import type { Page } from '@playwright/test'

export const SCREENSHOT_DIR = path.resolve(process.cwd(), 'screenshots')

export interface Breakpoint {
  name: 'desktop' | 'tablet' | 'mobile'
  width: number
  height: number
}

/** The three widths audited in the UI pass. */
export const BREAKPOINTS: Breakpoint[] = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'mobile', width: 375, height: 812 },
]

/**
 * Capture a full-page screenshot as `screenshots/<name>.png`.
 *
 * Animations are frozen so the image is stable regardless of when in a
 * transition the capture lands.
 */
export async function captureFullPage(page: Page, name: string): Promise<string> {
  mkdirSync(SCREENSHOT_DIR, { recursive: true })
  const file = path.join(SCREENSHOT_DIR, `${name}.png`)
  await page.screenshot({ path: file, fullPage: true, animations: 'disabled' })
  return file
}
