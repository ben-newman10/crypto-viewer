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

#: CoinGecko is keyed by its own asset ids, not ticker symbols. This map is the
#: curated override: where it has an answer, that answer wins, because a hand
#: checked id cannot be wrong. Symbols outside it are resolved against the
#: ranked universe (see :meth:`MarketContextService.get_ranked_universe`), which
#: carries id and symbol together and so is not a guess either.
#:
#: It used to be the *only* source, which quietly capped market-structure data
#: at these fifteen symbols -- a holding in, say, BCH or FIL reported market cap
#: as unavailable purely because it was not listed here.
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


class UniverseRow:
    """
    One coin's row in the market-cap-ranked page.

    Carries ``symbol`` and ``gecko_id`` together, which is what makes symbol
    resolution a lookup rather than a guess, and enough ranking material for the
    screener to shortlist without a second request.
    """

    __slots__ = (
        "symbol",
        "gecko_id",
        "name",
        "market_cap_rank",
        "market_cap",
        "total_volume",
        "change_24h_pct",
        "change_7d_pct",
        "change_30d_pct",
        "ath_change_pct",
        "circulating_supply",
    )

    def __init__(
        self,
        symbol: str,
        gecko_id: str,
        name: str = "",
        market_cap_rank: Optional[int] = None,
        market_cap: Optional[float] = None,
        total_volume: Optional[float] = None,
        change_24h_pct: Optional[float] = None,
        change_7d_pct: Optional[float] = None,
        change_30d_pct: Optional[float] = None,
        ath_change_pct: Optional[float] = None,
        circulating_supply: Optional[float] = None,
    ) -> None:
        self.symbol = symbol
        self.gecko_id = gecko_id
        self.name = name
        self.market_cap_rank = market_cap_rank
        self.market_cap = market_cap
        self.total_volume = total_volume
        self.change_24h_pct = change_24h_pct
        self.change_7d_pct = change_7d_pct
        self.change_30d_pct = change_30d_pct
        self.ath_change_pct = ath_change_pct
        self.circulating_supply = circulating_supply

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"UniverseRow({self.symbol}, rank={self.market_cap_rank})"


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

    async def get_ranked_universe(
        self,
        quote_currency: str = "GBP",
        limit: int = 250,
    ) -> List[UniverseRow]:
        """
        The top ``limit`` coins by market capitalisation, in rank order.

        One request, and it does double duty: it is the pool candidate
        discovery screens, and it is how an arbitrary ticker is resolved to a
        CoinGecko id without guessing.

        Returns:
            Rows in rank order, or an empty list when the page cannot be read.
            Never raises -- an unavailable universe means "no candidates", which
            is a smaller failure than an unavailable recommendation.
        """
        if not self.enabled:
            return []

        cache_key = f"universe:{quote_currency.lower()}:{limit}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        params = {
            "vs_currency": quote_currency.lower(),
            "order": "market_cap_desc",
            "per_page": str(limit),
            "page": "1",
            "price_change_percentage": "24h,7d,30d",
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(COINGECKO_URL, params=params)
                response.raise_for_status()
                rows = response.json()
        except Exception as error:  # noqa: BLE001
            logging.warning("CoinGecko universe unavailable: %s", error)
            return []

        if not isinstance(rows, list):
            logging.warning("CoinGecko universe had an unexpected shape")
            return []

        universe = [
            _universe_row(row) for row in rows if isinstance(row, dict) and row.get("id")
        ]
        logging.info("Ranked universe: %d coins in %s", len(universe), quote_currency)
        return self._store(cache_key, universe)

    async def resolve_ids(
        self,
        symbols: List[str],
        quote_currency: str = "GBP",
    ) -> Dict[str, str]:
        """
        Map tickers to CoinGecko ids: curated map first, ranked universe second.

        A ticker is not unique across CoinGecko, and picking the wrong id
        silently returns a *different* asset's market cap. So the curated map
        wins where it has an answer, and where it does not, the universe is used
        only when exactly one coin in it claims the ticker. An ambiguous ticker
        resolves to nothing rather than to a coin flip.
        """
        wanted = {symbol.upper() for symbol in symbols}
        resolved = {
            symbol: COINGECKO_IDS[symbol] for symbol in wanted if symbol in COINGECKO_IDS
        }

        missing = wanted - set(resolved)
        if not missing:
            return resolved

        universe = await self.get_ranked_universe(quote_currency)
        claimants: Dict[str, List[UniverseRow]] = {}
        for row in universe:
            claimants.setdefault(row.symbol, []).append(row)

        for symbol in missing:
            rows = claimants.get(symbol, [])
            if len(rows) == 1:
                resolved[symbol] = rows[0].gecko_id
            elif len(rows) > 1:
                logging.info(
                    "Ticker %s is claimed by %d coins; leaving it unresolved",
                    symbol,
                    len(rows),
                )

        return resolved

    async def get_asset_stats(
        self,
        symbols: List[str],
        quote_currency: str = "GBP",
    ) -> Dict[str, AssetMarketStats]:
        """
        Market cap, circulating supply and all-time-high distance per symbol.

        Symbols whose CoinGecko id cannot be resolved are simply absent from the
        result, which the context builder renders as explicitly unavailable
        fields.
        """
        if not self.enabled:
            return {}

        wanted = await self.resolve_ids(symbols, quote_currency)
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


def _universe_row(row: Dict[str, Any]) -> UniverseRow:
    """Read one ``/coins/markets`` row, tolerating any missing field."""
    rank = row.get("market_cap_rank")
    return UniverseRow(
        symbol=str(row.get("symbol", "")).upper(),
        gecko_id=str(row["id"]),
        name=str(row.get("name", "")),
        market_cap_rank=int(rank) if isinstance(rank, (int, float)) else None,
        market_cap=_as_float(row.get("market_cap")),
        total_volume=_as_float(row.get("total_volume")),
        # The `_in_currency` variants are the ones that honour `vs_currency`;
        # the bare `price_change_percentage_24h` is USD-denominated.
        change_24h_pct=_as_float(row.get("price_change_percentage_24h_in_currency")),
        change_7d_pct=_as_float(row.get("price_change_percentage_7d_in_currency")),
        change_30d_pct=_as_float(row.get("price_change_percentage_30d_in_currency")),
        ath_change_pct=_as_float(row.get("ath_change_percentage")),
        circulating_supply=_as_float(row.get("circulating_supply")),
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
