/**
 * Portfolio data hooks.
 *
 * Combines the portfolio listing with one price request per holding and derives
 * the view model the UI renders. Prices are fetched as independent queries so a
 * single failing pair degrades to one "price unavailable" row rather than
 * blanking the whole table.
 */

import { useMemo } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'

import {
  api,
  isPriceError,
  type Candle,
  type CryptoHolding,
  type CryptoPriceResponse,
} from '../lib/api'
import { isFiat, toNumber } from '../lib/format'

/** Live data refresh cadence, matching the original 30-second polling. */
export const REFRESH_INTERVAL_MS = 30_000

export type PriceState = 'loading' | 'ready' | 'error'

export interface HoldingView {
  currency: string
  balance: number | null
  available: number | null
  /** True for fiat balances, which are cash rather than a tradeable pair. */
  isCash: boolean
  price: number | null
  price24hAgo: number | null
  change24h: number | null
  /** Current value of the holding in the quote currency. */
  value: number | null
  value24hAgo: number | null
  valueDelta: number | null
  priceTime: string | null
  priceState: PriceState
  priceError: string | null
}

export interface PortfolioTotals {
  totalValue: number
  total24hAgo: number
  delta: number
  /** Null until at least one holding has a priced 24h-ago comparison. */
  changePercent: number | null
  assetCount: number
  /** Number of holdings whose price resolved successfully. */
  pricedCount: number
  hasPriceErrors: boolean
  /** Most recent price timestamp reported by the backend. */
  asOf: string | null
}

/** Cash balances are valued 1:1 and never hit the price endpoint. */
function cashHolding(holding: CryptoHolding): HoldingView {
  const balance = toNumber(holding.balance)
  return {
    currency: holding.currency,
    balance,
    available: toNumber(holding.available),
    isCash: true,
    price: 1,
    price24hAgo: 1,
    change24h: 0,
    value: balance,
    value24hAgo: balance,
    valueDelta: 0,
    priceTime: null,
    priceState: 'ready',
    priceError: null,
  }
}

function pricedHolding(
  holding: CryptoHolding,
  data: CryptoPriceResponse | undefined,
  state: PriceState,
  errorMessage: string | null,
): HoldingView {
  const balance = toNumber(holding.balance)
  const base: HoldingView = {
    currency: holding.currency,
    balance,
    available: toNumber(holding.available),
    isCash: false,
    price: null,
    price24hAgo: null,
    change24h: null,
    value: null,
    value24hAgo: null,
    valueDelta: null,
    priceTime: null,
    priceState: state,
    priceError: errorMessage,
  }

  if (isPriceError(data)) {
    return { ...base, priceState: 'error', priceError: data.error }
  }

  if (state !== 'ready' || !data) return base

  const price = toNumber(data.price)
  const price24hAgo = toNumber(data.price_24h_ago)
  const value = balance != null && price != null ? balance * price : null
  const value24hAgo = balance != null && price24hAgo != null ? balance * price24hAgo : null

  return {
    ...base,
    price,
    price24hAgo,
    change24h: Number.isFinite(data.change_24h) ? data.change_24h : null,
    value,
    value24hAgo,
    valueDelta: value != null && value24hAgo != null ? value - value24hAgo : null,
    priceTime: data.time ?? null,
    priceState: 'ready',
  }
}

/**
 * Fetch the portfolio and its prices, returning holdings plus derived totals.
 */
export function usePortfolio() {
  const portfolioQuery = useQuery({
    queryKey: ['portfolio'],
    queryFn: api.getPortfolio,
    refetchInterval: REFRESH_INTERVAL_MS,
  })

  // Memoised so the empty-array fallback does not produce a new reference on
  // every render and invalidate everything downstream.
  const holdings = useMemo(() => portfolioQuery.data ?? [], [portfolioQuery.data])

  const tradeable = useMemo(
    () => holdings.filter((holding) => !isFiat(holding.currency)),
    [holdings],
  )

  const priceQueries = useQueries({
    queries: tradeable.map((holding) => ({
      queryKey: ['price', holding.currency],
      queryFn: () => api.getPrice(holding.currency),
      refetchInterval: REFRESH_INTERVAL_MS,
    })),
  })

  // `useQueries` returns a fresh array on every render, so the results are
  // reduced to a stable string that changes only when the data actually does.
  const priceSignature = priceQueries
    .map((query) => `${query.status}:${JSON.stringify(query.data ?? null)}`)
    .join('|')

  const views = useMemo<HoldingView[]>(() => {
    const priceByCurrency = new Map(
      tradeable.map((holding, index) => [holding.currency, priceQueries[index]]),
    )

    return holdings.map((holding) => {
      if (isFiat(holding.currency)) return cashHolding(holding)

      const query = priceByCurrency.get(holding.currency)
      const state: PriceState = query?.isError
        ? 'error'
        : query?.data
          ? 'ready'
          : 'loading'
      const errorMessage = query?.isError
        ? 'Price data is currently unavailable.'
        : null

      return pricedHolding(holding, query?.data, state, errorMessage)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [holdings, tradeable, priceSignature])

  const totals = useMemo<PortfolioTotals>(() => {
    let totalValue = 0
    let total24hAgo = 0
    let pricedCount = 0
    let hasPriceErrors = false
    let asOf: string | null = null

    for (const holding of views) {
      if (holding.priceState === 'error') {
        hasPriceErrors = true
        continue
      }
      if (holding.value == null) continue

      totalValue += holding.value
      total24hAgo += holding.value24hAgo ?? holding.value
      pricedCount += 1

      if (holding.priceTime && (!asOf || holding.priceTime > asOf)) {
        asOf = holding.priceTime
      }
    }

    const delta = totalValue - total24hAgo

    return {
      totalValue,
      total24hAgo,
      delta,
      changePercent: total24hAgo > 0 ? (delta / total24hAgo) * 100 : null,
      assetCount: views.length,
      pricedCount,
      hasPriceErrors,
      asOf,
    }
  }, [views])

  /** True only while the very first portfolio request is in flight. */
  const isInitialLoading = portfolioQuery.isPending
  /** True while prices are still resolving for an already-loaded portfolio. */
  const isPricesLoading =
    !isInitialLoading && views.some((holding) => holding.priceState === 'loading')

  return {
    holdings: views,
    totals,
    isInitialLoading,
    isPricesLoading,
    isError: portfolioQuery.isError,
    error: portfolioQuery.error,
    isEmpty: !isInitialLoading && !portfolioQuery.isError && views.length === 0,
    refetch: portfolioQuery.refetch,
    isRefetching: portfolioQuery.isRefetching,
  }
}

/** Price + 24h candles for a single asset, used by the coin detail view. */
export function useCoin(currency: string) {
  const cash = isFiat(currency)

  const priceQuery = useQuery({
    queryKey: ['price', currency],
    queryFn: () => api.getPrice(currency),
    refetchInterval: REFRESH_INTERVAL_MS,
    enabled: !cash,
  })

  const historyQuery = useQuery<Candle[]>({
    queryKey: ['historical', currency],
    queryFn: () => api.getHistorical(currency),
    refetchInterval: REFRESH_INTERVAL_MS,
    enabled: !cash,
  })

  const portfolioQuery = useQuery({
    queryKey: ['portfolio'],
    queryFn: api.getPortfolio,
    refetchInterval: REFRESH_INTERVAL_MS,
  })

  const holding = portfolioQuery.data?.find(
    (item) => item.currency.toUpperCase() === currency.toUpperCase(),
  )

  const price = isPriceError(priceQuery.data) ? undefined : priceQuery.data
  const priceErrorMessage = isPriceError(priceQuery.data)
    ? priceQuery.data.error
    : priceQuery.isError
      ? 'Price data is currently unavailable.'
      : null

  const balance = toNumber(holding?.balance ?? null)
  const currentPrice = cash ? 1 : toNumber(price?.price ?? null)

  /** Candles arrive newest-first from Coinbase; charts read oldest-first. */
  const series = useMemo(() => {
    const candles = historyQuery.data ?? []
    return [...candles].reverse()
  }, [historyQuery.data])

  return {
    currency: currency.toUpperCase(),
    isCash: cash,
    balance,
    price: currentPrice,
    change24h: cash ? 0 : (price?.change_24h ?? null),
    price24hAgo: cash ? 1 : toNumber(price?.price_24h_ago ?? null),
    value: balance != null && currentPrice != null ? balance * currentPrice : null,
    priceTime: price?.time ?? null,
    series,
    isPriceLoading: !cash && priceQuery.isPending,
    priceErrorMessage,
    isHistoryLoading: !cash && historyQuery.isPending,
    isHistoryError: historyQuery.isError,
    isHoldingLoading: portfolioQuery.isPending,
    /** True once the portfolio has loaded and this asset is not in it. */
    isUnknownHolding: !portfolioQuery.isPending && !portfolioQuery.isError && !holding,
    refetch: () => {
      void priceQuery.refetch()
      void historyQuery.refetch()
    },
  }
}
