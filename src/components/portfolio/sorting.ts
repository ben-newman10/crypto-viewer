/**
 * Sorting and filtering for the holdings list.
 *
 * Kept separate from the presentation components so the table and the mobile
 * card list stay in lockstep.
 */

import type { HoldingView } from '../../hooks/usePortfolio'

export type SortKey = 'currency' | 'balance' | 'price' | 'change24h' | 'value'
export type SortDirection = 'asc' | 'desc'

export interface SortState {
  key: SortKey
  direction: SortDirection
}

export const DEFAULT_SORT: SortState = { key: 'value', direction: 'desc' }

/** Columns default to descending on first click, except the text column. */
export function nextSortState(current: SortState, key: SortKey): SortState {
  if (current.key === key) {
    return { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
  }
  return { key, direction: key === 'currency' ? 'asc' : 'desc' }
}

function valueFor(holding: HoldingView, key: SortKey): number | string | null {
  switch (key) {
    case 'currency':
      return holding.currency
    case 'balance':
      return holding.balance
    case 'price':
      return holding.price
    case 'change24h':
      return holding.change24h
    case 'value':
      return holding.value
  }
}

export function sortHoldings(holdings: HoldingView[], sort: SortState): HoldingView[] {
  const factor = sort.direction === 'asc' ? 1 : -1

  return [...holdings].sort((a, b) => {
    const left = valueFor(a, sort.key)
    const right = valueFor(b, sort.key)

    // Rows without a value (unpriced or failed) always sink to the bottom so
    // the ordering of real figures stays readable.
    if (left == null && right == null) return a.currency.localeCompare(b.currency)
    if (left == null) return 1
    if (right == null) return -1

    if (typeof left === 'string' || typeof right === 'string') {
      return String(left).localeCompare(String(right)) * factor
    }

    if (left === right) return a.currency.localeCompare(b.currency)
    return (left < right ? -1 : 1) * factor
  })
}

export function filterHoldings(holdings: HoldingView[], query: string): HoldingView[] {
  const trimmed = query.trim().toLowerCase()
  if (!trimmed) return holdings
  return holdings.filter((holding) => holding.currency.toLowerCase().includes(trimmed))
}

/** `aria-sort` value for a column header. */
export function ariaSortFor(sort: SortState, key: SortKey): 'ascending' | 'descending' | 'none' {
  if (sort.key !== key) return 'none'
  return sort.direction === 'asc' ? 'ascending' : 'descending'
}
