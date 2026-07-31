/**
 * Typed HTTP client for the Crypto Viewer backend.
 *
 * All requests go to the same origin and are proxied to FastAPI, so the E2E
 * suite exercises the real frontend -> backend path with only the outbound
 * third-party calls faked on the server side.
 */

import { QUOTE_CURRENCY } from './format'

export interface CryptoHolding {
  /** Cryptocurrency (or fiat) symbol, e.g. 'BTC'. */
  currency: string
  /** Total balance held. */
  balance: string
  /** Balance available to trade. */
  available: string
}

export interface CryptoPrice {
  price: string
  time: string
  change_24h: number
  price_24h_ago: string
}

/**
 * The price endpoint answers 200 with an `error` key when the upstream lookup
 * fails, so callers must handle a successful response that carries no price.
 */
export type CryptoPriceResponse = CryptoPrice | { error: string }

export interface Candle {
  time: string
  low: string
  high: string
  open: string
  close: string
  volume: string
}

export interface RecommendationResponse {
  recommendations: string
}

/** Error carrying the HTTP status so the UI can distinguish failure kinds. */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: 'application/json' }, ...init })
  } catch {
    // Network-level failure (offline, DNS, connection reset).
    throw new ApiError('Could not reach the Crypto Viewer service.', 0)
  }

  if (!response.ok) {
    throw new ApiError(
      `Request to ${path} failed with status ${response.status}.`,
      response.status,
    )
  }

  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError(`Received an unreadable response from ${path}.`, response.status)
  }
}

export const productIdFor = (currency: string): string =>
  `${currency.toUpperCase()}-${QUOTE_CURRENCY}`

export const api = {
  getPortfolio: () => request<CryptoHolding[]>('/api/crypto/portfolio'),

  getPrice: (currency: string) =>
    request<CryptoPriceResponse>(`/api/crypto/price/${productIdFor(currency)}`),

  getHistorical: (currency: string) =>
    request<Candle[]>(`/api/crypto/historical/${productIdFor(currency)}`),

  getRecommendations: () => request<RecommendationResponse>('/api/recommendations/'),
}

/** Narrowing helper for the price endpoint's dual-shaped response. */
export function isPriceError(
  value: CryptoPriceResponse | undefined | null,
): value is { error: string } {
  return !!value && 'error' in value
}
