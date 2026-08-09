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

/** Direction of a call. */
export type RecommendationAction = 'buy' | 'sell' | 'hold'

/** Confidence rating, tied to the rubric documented in the backend. */
export type Confidence = 'low' | 'medium' | 'high'

/**
 * One claim behind a call, already verified server-side against the grounding
 * data. `value` is always the measured value: when the model quoted something
 * else it is corrected here, `verified` is false and `model_stated_value`
 * records what it actually said.
 */
export interface SupportingFact {
  /** Field name in the grounding context, e.g. `BTC.rsi_14`. */
  metric: string
  label: string
  value: string
  unit: string
  interpretation: string
  /**
   * Plain-English definition of what the metric measures, authored server-side
   * in the metric catalogue rather than by the model. Empty string when the
   * backend has no definition for the field.
   */
  plain: string
  verified: boolean
  model_stated_value: string | null
}

export interface AssetRecommendation {
  symbol: string
  recommendation: RecommendationAction
  confidence: Confidence
  confidence_rationale: string
  /** What the model rated itself before the server applied the data ceiling. */
  model_confidence: Confidence
  /** Highest rating the available data can support, whatever the model said. */
  confidence_ceiling: Confidence
  ceiling_reason: string
  supporting_facts: SupportingFact[]
  risks_or_caveats: string[]
  /** 0-1 share of the intended grounding fields that were available. */
  data_completeness: number
  categories_available: string[]
  categories_missing: string[]
  verification_note: string | null
}

export interface GroundednessViolation {
  symbol: string
  metric: string
  kind: string
  detail: string
  model_value: string | null
  context_value: string | null
}

export interface GroundednessReport {
  status: 'verified' | 'corrected'
  facts_checked: number
  facts_dropped: number
  facts_corrected: number
  retried: boolean
  confidence_downgraded: boolean
  violations: GroundednessViolation[]
}

export interface RecommendationResponse {
  /** `empty` and `unavailable` carry a `message` instead of recommendations. */
  status: 'ok' | 'empty' | 'unavailable'
  message: string | null
  generated_at: string
  quote_currency: string
  summary: string
  recommendations: AssetRecommendation[]
  /** Injected by the server after the model call; never model-generated. */
  disclaimer: string
  groundedness: GroundednessReport
  sources: Record<string, string>
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
