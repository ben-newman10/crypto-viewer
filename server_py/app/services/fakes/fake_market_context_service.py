"""
In-process stand-in for MarketContextService.

Serves the CoinGecko and Fear & Greed figures from fixtures, so the E2E suite
exercises a full grounding context -- including the market-structure and
sentiment signal categories -- without an outbound request to either host.
"""

from typing import Dict, List, Optional

from ..market_context_service import (
    COINGECKO_IDS,
    AssetMarketStats,
    FearGreed,
    UniverseRow,
    _universe_row,
)
from . import fixtures, scenarios
from .scenarios import Scenario


class FakeMarketContextService:
    """Scenario-aware fake implementing the MarketContextService interface."""

    def __init__(self, scenario: Scenario = None) -> None:
        self.scenario = scenario or Scenario.parse(None)

    async def get_asset_stats(
        self,
        symbols: List[str],
        quote_currency: str = "GBP",
    ) -> Dict[str, AssetMarketStats]:
        if self.scenario.has(scenarios.ERROR_MARKET_CONTEXT):
            # Mirrors the real service's degradation: an unreachable source
            # returns nothing rather than raising, and the affected fields
            # become explicitly unavailable downstream.
            return {}

        stats: Dict[str, AssetMarketStats] = {}
        for symbol in symbols:
            row = fixtures.MARKET_STATS.get(symbol.upper())
            if row is None:
                continue
            stats[symbol.upper()] = AssetMarketStats(
                market_cap=row["market_cap"],
                circulating_supply=row["circulating_supply"],
                ath=row["ath"],
                ath_change_pct=row["ath_change_pct"],
            )
        return stats

    async def get_ranked_universe(
        self,
        quote_currency: str = "GBP",
        limit: int = 250,
    ) -> List[UniverseRow]:
        if self.scenario.has(scenarios.ERROR_MARKET_CONTEXT):
            return []
        # Parsed through the real reader so the fixture is held to the same
        # field names the live page uses -- a rename upstream breaks the fake
        # too, rather than letting it drift into agreeing with nothing.
        return [_universe_row(row) for row in fixtures.universe_rows()][:limit]

    async def resolve_ids(
        self,
        symbols: List[str],
        quote_currency: str = "GBP",
    ) -> Dict[str, str]:
        wanted = {symbol.upper() for symbol in symbols}
        resolved = {
            symbol: COINGECKO_IDS[symbol] for symbol in wanted if symbol in COINGECKO_IDS
        }
        for row in await self.get_ranked_universe(quote_currency):
            if row.symbol in wanted and row.symbol not in resolved:
                resolved[row.symbol] = row.gecko_id
        return resolved

    async def get_fear_greed(self) -> Optional[FearGreed]:
        if self.scenario.has(scenarios.ERROR_MARKET_CONTEXT):
            return None
        return FearGreed(
            value=fixtures.FEAR_GREED_VALUE,
            classification=fixtures.FEAR_GREED_CLASSIFICATION,
        )
