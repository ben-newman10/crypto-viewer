"""
Tests for the Coinbase service seam.

Under test mode the dependency provider yields the fake client, so these tests
verify the fake honours the same contract the real service exposes -- without
requiring API credentials or any outbound request.
"""

import pytest

from app.services.fakes import FakeCoinbaseService, Scenario
from app.services.fakes import scenarios


@pytest.fixture
def coinbase_service():
    return FakeCoinbaseService()


async def test_get_portfolio(coinbase_service):
    portfolio = await coinbase_service.get_portfolio()
    assert isinstance(portfolio, list)
    assert portfolio, "fixture portfolio should not be empty"
    for holding in portfolio:
        assert {"currency", "balance", "available"} <= holding.keys()


async def test_get_crypto_price(coinbase_service):
    price = await coinbase_service.get_crypto_price("BTC-GBP")
    assert "price" in price
    assert "change_24h" in price
    assert float(price["price"]) > 0


async def test_get_crypto_price_unknown_pair_returns_error(coinbase_service):
    price = await coinbase_service.get_crypto_price("DOGE-GBP")
    assert "error" in price


async def test_get_historical_data(coinbase_service):
    candles = await coinbase_service.get_historical_data("ETH-GBP")
    assert len(candles) == 24
    for candle in candles:
        assert {"time", "low", "high", "open", "close", "volume"} <= candle.keys()


async def test_empty_portfolio_scenario():
    service = FakeCoinbaseService(Scenario.parse(scenarios.EMPTY_PORTFOLIO))
    assert await service.get_portfolio() == []


async def test_error_portfolio_scenario_raises():
    service = FakeCoinbaseService(Scenario.parse(scenarios.ERROR_PORTFOLIO))
    with pytest.raises(RuntimeError):
        await service.get_portfolio()


async def test_error_prices_scenario_returns_error_payload():
    service = FakeCoinbaseService(Scenario.parse(scenarios.ERROR_PRICES))
    result = await service.get_crypto_price("BTC-GBP")
    assert "error" in result
