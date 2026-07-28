/**
 * Number, currency and date formatting helpers.
 *
 * All display formatting lives here so that figures are presented consistently
 * across the portfolio table, summary tiles and coin detail view.
 */

const LOCALE = 'en-GB'
export const QUOTE_CURRENCY = 'GBP'

/** Currencies held as cash rather than as a tradeable crypto pair. */
const FIAT_CURRENCIES = new Set(['GBP', 'USD', 'EUR'])

export const isFiat = (currency: string): boolean =>
  FIAT_CURRENCIES.has(currency.toUpperCase())

/**
 * Format a monetary amount in the quote currency.
 *
 * Sub-£1 amounts get extra precision so that low-priced assets do not all
 * collapse to "£0.00".
 */
export function formatCurrency(
  value: number | null | undefined,
  options: { compact?: boolean } = {},
): string {
  if (value == null || !Number.isFinite(value)) return '—'

  const magnitude = Math.abs(value)

  if (options.compact && magnitude >= 10_000) {
    return new Intl.NumberFormat(LOCALE, {
      style: 'currency',
      currency: QUOTE_CURRENCY,
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value)
  }

  const fractionDigits = magnitude > 0 && magnitude < 1 ? 4 : 2

  return new Intl.NumberFormat(LOCALE, {
    style: 'currency',
    currency: QUOTE_CURRENCY,
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value)
}

/**
 * Compact currency formatting for chart axis ticks, where horizontal space is
 * scarce: thousands are abbreviated and pence are dropped above £100.
 */
export function formatAxisCurrency(value: number): string {
  if (!Number.isFinite(value)) return ''
  const magnitude = Math.abs(value)

  if (magnitude >= 10_000) {
    return new Intl.NumberFormat(LOCALE, {
      style: 'currency',
      currency: QUOTE_CURRENCY,
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value)
  }

  return new Intl.NumberFormat(LOCALE, {
    style: 'currency',
    currency: QUOTE_CURRENCY,
    minimumFractionDigits: 0,
    maximumFractionDigits: magnitude >= 100 ? 0 : 2,
  }).format(value)
}

/** Format a signed monetary delta, e.g. "+£1,204.55" / "−£88.10". */
export function formatCurrencyDelta(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${formatCurrency(Math.abs(value))}`
}

/** Format a percentage that already arrives as a percentage (not a ratio). */
export function formatPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${Math.abs(value).toFixed(2)}%`
}

/**
 * Format a crypto balance. Crypto keeps up to 8 decimals with trailing zeros
 * trimmed; fiat balances use standard 2-decimal money formatting.
 */
export function formatAmount(value: number | null | undefined, currency: string): string {
  if (value == null || !Number.isFinite(value)) return '—'

  if (isFiat(currency)) {
    return new Intl.NumberFormat(LOCALE, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value)
  }

  const formatted = new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 8,
  }).format(value)

  return formatted
}

/** Human-readable timestamp for "prices as of" labels. */
export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(LOCALE, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
    timeZoneName: 'short',
  }).format(date)
}

/** Short axis label for the 24h chart. */
export function formatHourLabel(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(LOCALE, {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  }).format(date)
}

/** Parse an API-supplied numeric string, returning null when unusable. */
export function toNumber(value: string | number | null | undefined): number | null {
  if (value == null || value === '') return null
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

/**
 * Direction of a change, used to pick colour, icon and screen-reader wording.
 * Values within a hair of zero are treated as flat so that "+0.00%" never
 * renders in green.
 */
export type Direction = 'up' | 'down' | 'flat'

export function directionOf(value: number | null | undefined): Direction {
  if (value == null || !Number.isFinite(value) || Math.abs(value) < 0.005) return 'flat'
  return value > 0 ? 'up' : 'down'
}
