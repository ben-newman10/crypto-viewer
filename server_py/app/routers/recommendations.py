"""
API endpoints for grounded, confidence-rated recommendations.

The router is deliberately thin: it wires up the injected services and hands
off to ``services/recommendation_service.py``, which owns the grounding,
verification, disclaimer injection and logging. Both the Coinbase and OpenAI
clients arrive via FastAPI dependencies so tests can substitute fakes and never
call a third-party API.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_ai_service, get_coinbase_service, get_market_context_service
from ..schemas.recommendation import RecommendationResponse
from ..services import recommendation_service

router = APIRouter()


async def _generate(coinbase_service, ai_service, market_context_service) -> RecommendationResponse:
    """
    Shared handler.

    A failure that reaches here is an unexpected one -- a Coinbase outage, a
    bug -- and becomes a 500. A model that is merely unconfigured or
    unreachable is *not* an error: it comes back as a 200 with
    ``status="unavailable"``, because the portfolio data is still good and the
    UI should say so rather than blanking the panel.
    """
    try:
        return await recommendation_service.generate(
            coinbase_service=coinbase_service,
            ai_service=ai_service,
            market_context_service=market_context_service,
        )
    except Exception as error:
        logging.error(f"Error generating recommendations: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")


@router.get("/", response_model=RecommendationResponse)
async def get_recommendations(
    coinbase_service=Depends(get_coinbase_service),
    ai_service=Depends(get_ai_service),
    market_context_service=Depends(get_market_context_service),
) -> RecommendationResponse:
    """
    Grounded buy/sell/hold calls for every holding in the portfolio.

    Each call carries a confidence rating tied to the documented rubric, the
    supporting facts it was built from (every one verified against the
    grounding data server-side), and a server-injected disclaimer.

    Raises:
        HTTPException(500): If portfolio or market data could not be gathered.
    """
    return await _generate(coinbase_service, ai_service, market_context_service)


@router.get("/analysis", response_model=RecommendationResponse)
async def get_analysis(
    coinbase_service=Depends(get_coinbase_service),
    ai_service=Depends(get_ai_service),
    market_context_service=Depends(get_market_context_service),
) -> RecommendationResponse:
    """
    Alias of the root endpoint, kept for existing callers.

    The two used to differ only in how much market data they gathered before
    building the prompt. Now that the grounding context is built the same way
    for every request, there is nothing left for them to differ on.
    """
    return await _generate(coinbase_service, ai_service, market_context_service)
