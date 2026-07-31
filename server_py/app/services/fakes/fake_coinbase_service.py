"""
In-process stand-in for CoinbaseService.

Implements the same async surface as the real service but serves fixture data
and never opens a socket, so tests can exercise the full frontend -> FastAPI
path without touching the Coinbase Advanced Trade API.
"""

import asyncio
import logging
from typing import Any, Dict, List

from . import fixtures, scenarios
from .scenarios import Scenario


class FakeCoinbaseService:
    """Scenario-aware fake implementing the CoinbaseService interface."""

    def __init__(self, scenario: Scenario = None) -> None:
        self.scenario = scenario or Scenario.parse(None)

    async def _maybe_delay(self, flag: str) -> None:
        if self.scenario.has(flag):
            await asyncio.sleep(scenarios.SLOW_DELAY_SECONDS)

    async def get_portfolio(self) -> List[Dict[str, Any]]:
        await self._maybe_delay(scenarios.SLOW_PORTFOLIO)

        if self.scenario.has(scenarios.ERROR_PORTFOLIO):
            raise RuntimeError("Simulated Coinbase outage while fetching accounts")

        if self.scenario.has(scenarios.EMPTY_PORTFOLIO):
            return []

        # Return copies so a caller mutating the result cannot corrupt fixtures.
        return [dict(holding) for holding in fixtures.PORTFOLIO]

    async def get_crypto_price(self, product_id: str) -> Dict[str, Any]:
        await self._maybe_delay(scenarios.SLOW_PRICES)

        if self.scenario.has(scenarios.ERROR_PRICES):
            # The real service swallows upstream failures and returns a 200 with
            # an ``error`` key, so the fake reproduces that exact contract.
            logging.info("Simulated price failure for %s", product_id)
            return {
                "error": (
                    f"Unable to fetch price for {product_id}. "
                    "Please check if the trading pair is supported."
                )
            }

        return fixtures.price_for(product_id)

    async def get_historical_data(self, product_id: str) -> List[Dict[str, Any]]:
        await self._maybe_delay(scenarios.SLOW_HISTORICAL)

        if self.scenario.has(scenarios.ERROR_HISTORICAL):
            raise RuntimeError(
                f"Simulated Coinbase outage while fetching candles for {product_id}"
            )

        return fixtures.historical_for(product_id)
