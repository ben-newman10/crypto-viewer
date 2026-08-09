"""
Free, keyless market context that the Coinbase trading API does not expose.

Two sources, both optional:

* **CoinGecko** (`/coins/markets`) for market capitalisation, circulating
  supply and distance from the all-time high.
* **alternative.me** (`/fng/`) for the market-wide Fear & Greed Index.

Neither is load-bearing. Every call is wrapped so that a timeout, a rate limit
or a schema change degrades to "unavailable" for the affected fields rather
than failing the recommendation -- and "unavailable" then propagates all the
way through to a lower confidence ceiling, which is the point.

What is deliberately *not* here: true on-chain data (exchange netflows, MVRV,
whale wallet activity). Those need a paid provider such as Glassnode,
CryptoQuant or Santiment. Approximating them from price and volume data would
manufacture exactly the kind of confident-sounding, unverifiable claim this
pipeline exists to prevent, so they are simply absent.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
FEAR_GREED_URL = "https://api.alternative.me/fng/"

REQUEST_TIMEOUT_SECONDS = 6.0

#: Results are cached in-process: these figures move on the scale of hours, and
#: the free tiers of both APIs are rate limited.
CACHE_TTL_SECONDS = 15 * 60

#: CoinGecko is keyed by its own asset ids, not ticker symbols. A small static
#: map covers the assets Coinbase lists in GBP; anything outside it resolves to
#: "unavailable" rather than to a guess, because guessing an id can silently
#: return a *different* asset's market cap.
COINGECKO_IDS: Dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "LINK": "chainlink",
    "LTC": "litecoin",
    "MATIC": "matic-network",
    "XLM": "stellar",
    "XRP": "ripple",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "ALGO": "algorand",
}


class AssetMarketStats:
    """Market-structure figures for one asset."""

    __slots__ = ("market_cap", "circulating_supply", "ath", "ath_change_pct")

    def __init__(
        self,
        market_cap: Optional[float] = None,
        circulating_supply: Optional[float] = None,
        ath: Optional[float] = None,
        ath_change_pct: Optional[float] = None,
    ) -> None:
        self.market_cap = market_cap
        self.circulating_supply = circulating_supply
        self.ath = ath
        self.ath_change_pct = ath_change_pct


class FearGreed:
    """Market-wide sentiment reading."""

    __slots__ = ("value", "classification")

    def __init__(self, value: float, classification: str) -> None:
        self.value = value
        self.classification = classification


class MarketContextService:
    """Fetches supplementary market data, degrading to ``None`` on any failure."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._cache: Dict[str, Any] = {}
        self._cache_at: Dict[str, float] = {}

    # -- caching ------------------------------------------------------------

    def _cached(self, key: str) -> Any:
        stamped = self._cache_at.get(key)
        if stamped is None or (time.monotonic() - stamped) > CACHE_TTL_SECONDS:
            return None
        return self._cache.get(key)

    def _store(self, key: str, value: Any) -> Any:
        self._cache[key] = value
        self._cache_at[key] = time.monotonic()
        return value

    # -- sources ------------------------------------------------------------

    async def get_asset_stats(
        self,
        symbols: List[str],
        quote_currency: str = "GBP",
    ) -> Dict[str, AssetMarketStats]:
        """
        Market cap, circulating supply and all-time-high distance per symbol.

        Symbols with no known CoinGecko id are simply absent from the result,
        which the context builder renders as explicitly unavailable fields.
        """
        if not self.enabled:
            return {}

        wanted = {
            symbol.upper(): COINGECKO_IDS[symbol.upper()]
            for symbol in symbols
            if symbol.upper() in COINGECKO_IDS
        }
        if not wanted:
            return {}

        cache_key = f"coingecko:{quote_currency}:{','.join(sorted(wanted.values()))}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        params = {
            "vs_currency": quote_currency.lower(),
            "ids": ",".join(sorted(wanted.values())),
            "price_change_percentage": "24h",
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(COINGECKO_URL, params=params)
                response.raise_for_status()
                rows = response.json()
        except Exception as error:  # noqa: BLE001 - any failure means "unavailable"
            logging.warning("CoinGecko market data unavailable: %s", error)
            return {}

        by_id = {row.get("id"): row for row in rows if isinstance(row, dict)}
        stats: Dict[str, AssetMarketStats] = {}

        for symbol, gecko_id in wanted.items():
            row = by_id.get(gecko_id)
            if not row:
                continue
            stats[symbol] = AssetMarketStats(
                market_cap=_as_float(row.get("market_cap")),
                circulating_supply=_as_float(row.get("circulating_supply")),
                ath=_as_float(row.get("ath")),
                ath_change_pct=_as_float(row.get("ath_change_percentage")),
            )

        return self._store(cache_key, stats)

    async def get_fear_greed(self) -> Optional[FearGreed]:
        """Current Fear & Greed Index, or ``None`` if the source is unreachable."""
        if not self.enabled:
            return None

        cached = self._cached("fng")
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(FEAR_GREED_URL, params={"limit": 1})
                response.raise_for_status()
                body = response.json()
        except Exception as error:  # noqa: BLE001
            logging.warning("Fear & Greed Index unavailable: %s", error)
            return None

        entries = body.get("data") if isinstance(body, dict) else None
        if not entries:
            return None

        entry = entries[0]
        value = _as_float(entry.get("value"))
        if value is None:
            return None

        return self._store(
            "fng",
            FearGreed(
                value=value,
                classification=str(entry.get("value_classification", "unknown")),
            ),
        )


def _as_float(value: Any) -> Optional[float]:
    """Coerce an API field to a float, or ``None`` when it is not a number."""
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed else None  # reject NaN
