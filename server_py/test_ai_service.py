"""
Tests for the AI recommendation service seam.

The fake OpenAI-backed service is used throughout so no API key is needed and
no request leaves the process.
"""

import pytest

from app.services.fakes import FakeAIService, Scenario
from app.services.fakes import scenarios


@pytest.fixture
def ai_service():
    return FakeAIService()


async def test_get_recommendations(ai_service):
    portfolio = []  # Mock portfolio data
    market_data = []  # Mock market data
    recommendations = await ai_service.get_recommendations(portfolio, market_data)
    assert isinstance(recommendations, str)
    assert recommendations.strip()


async def test_error_scenario_raises():
    service = FakeAIService(Scenario.parse(scenarios.ERROR_AI))
    with pytest.raises(RuntimeError):
        await service.get_recommendations([], [])


async def test_degraded_scenario_returns_fallback_text():
    service = FakeAIService(Scenario.parse(scenarios.DEGRADED_AI))
    result = await service.get_recommendations([], [])
    assert "Unable to generate recommendations" in result
