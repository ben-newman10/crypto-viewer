"""
In-process stand-in for MarketContextService.

Serves the CoinGecko and Fear & Greed figures from fixtures, so the E2E suite
exercises a full grounding context -- including the market-structure and
sentiment signal categories -- without an outbound request to either host.
"""

from typing import Dict, List, Optional

from ..market_context_service import AssetMarketStats, FearGreed
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

    async def get_fear_greed(self) -> Optional[FearGreed]:
        if self.scenario.has(scenarios.ERROR_MARKET_CONTEXT):
            return None
        return FearGreed(
            value=fixtures.FEAR_GREED_VALUE,
            classification=fixtures.FEAR_GREED_CLASSIFICATION,
        )
