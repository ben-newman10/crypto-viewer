import pytest
from app.services.ai_service import AIService

@pytest.fixture
def ai_service():
    return AIService()

@pytest.mark.asyncio
async def test_get_recommendations(ai_service):
    portfolio = []  # Mock portfolio data
    market_data = []  # Mock market data
    recommendations = await ai_service.get_recommendations(portfolio, market_data)
    assert isinstance(recommendations, str)