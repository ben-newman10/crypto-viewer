import pytest
from app.services.coinbase_service import CoinbaseService

@pytest.fixture
def coinbase_service():
    return CoinbaseService()

@pytest.mark.asyncio
async def test_get_portfolio(coinbase_service):
    portfolio = await coinbase_service.get_portfolio()
    assert isinstance(portfolio, list)