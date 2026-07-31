"""
FastAPI dependency providers for the application's services.

Routers depend on these providers rather than constructing services at import
time. That keeps module import side-effect free (the app can start without
Coinbase/OpenAI credentials) and gives tests a single seam at which the real
outbound clients are replaced with fakes.
"""

import logging
from typing import Optional

from fastapi import Request

from .config import SCENARIO_COOKIE, external_market_data_enabled, is_test_mode
from .services.fakes import (
    FakeAIService,
    FakeCoinbaseService,
    FakeMarketContextService,
    Scenario,
)

# Real services are expensive to construct (they build authenticated clients),
# so they are created once on first use and reused afterwards.
_coinbase_service: Optional[object] = None
_ai_service: Optional[object] = None
_market_context_service: Optional[object] = None


def _real_coinbase_service():
    global _coinbase_service
    if _coinbase_service is None:
        from .services.coinbase_service import CoinbaseService

        _coinbase_service = CoinbaseService()
    return _coinbase_service


def _real_ai_service():
    global _ai_service
    if _ai_service is None:
        from .services.ai_service import AIService

        _ai_service = AIService()
    return _ai_service


def _real_market_context_service():
    global _market_context_service
    if _market_context_service is None:
        from .services.market_context_service import MarketContextService

        _market_context_service = MarketContextService(enabled=external_market_data_enabled())
    return _market_context_service


def _scenario_from(request: Request) -> Scenario:
    return Scenario.parse(request.cookies.get(SCENARIO_COOKIE))


def get_coinbase_service(request: Request):
    """Provide a Coinbase service: the real client, or a fake in test mode."""
    if is_test_mode():
        return FakeCoinbaseService(_scenario_from(request))
    return _real_coinbase_service()


def get_ai_service(request: Request):
    """Provide an AI service: the real OpenAI client, or a fake in test mode."""
    if is_test_mode():
        return FakeAIService(_scenario_from(request))
    return _real_ai_service()


def get_market_context_service(request: Request):
    """
    Provide the supplementary market-data service (CoinGecko, Fear & Greed).

    Separate from the Coinbase seam because it is genuinely optional: when it
    is unavailable the pipeline still answers, with the affected fields marked
    unavailable and confidence capped accordingly.
    """
    if is_test_mode():
        return FakeMarketContextService(_scenario_from(request))
    return _real_market_context_service()


def reset_service_cache() -> None:
    """Drop cached real services. Used by tests that toggle configuration."""
    global _coinbase_service, _ai_service, _market_context_service
    _coinbase_service = None
    _ai_service = None
    _market_context_service = None
    logging.debug("Service cache reset")
