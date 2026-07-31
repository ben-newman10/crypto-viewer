/**
 * Display names for well-known tickers.
 *
 * The Coinbase endpoints the app uses return symbols only, so this small lookup
 * lets the UI show a human-readable name where one is known and fall back to the
 * bare ticker where it is not.
 */

const ASSET_NAMES: Record<string, string> = {
  BTC: 'Bitcoin',
  ETH: 'Ethereum',
  SOL: 'Solana',
  ADA: 'Cardano',
  XRP: 'XRP',
  DOGE: 'Dogecoin',
  DOT: 'Polkadot',
  MATIC: 'Polygon',
  LTC: 'Litecoin',
  LINK: 'Chainlink',
  AVAX: 'Avalanche',
  USDC: 'USD Coin',
  GBP: 'Pound sterling',
  USD: 'US dollar',
  EUR: 'Euro',
}

export function assetName(currency: string): string | null {
  return ASSET_NAMES[currency.toUpperCase()] ?? null
}
