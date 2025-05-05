# This module defines the API endpoint for generating cryptocurrency recommendations.
# It fetches portfolio data, market data, and AI-based recommendations.

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging
from app.services.coinbase_service import CoinbaseService
from app.services.ai_service import AIService

router = APIRouter()
coinbase_service = CoinbaseService()
ai_service = AIService()

@router.get("/")
async def get_recommendations() -> Dict[str, str]:
    """
    Fetches cryptocurrency recommendations.

    Returns:
        A dictionary containing AI-generated recommendations based on the user's portfolio and market data.

    Raises:
        HTTPException: If there is an error in generating recommendations.
    """
    try:
        # Get portfolio data from the Coinbase service.
        portfolio = await coinbase_service.get_portfolio()
        if not portfolio:
            return {"recommendations": "No cryptocurrency holdings found in your portfolio."}

        # Initialize a list to store market data for each asset in the portfolio.
        market_data = []

        for holding in portfolio:
            try:
                # Format the product ID for fetching market data
                product_id = f"{holding['currency']}-GBP"
                # Fetch historical data for the asset
                data = await coinbase_service.get_historical_data(product_id)
                # Append the fetched data to the market_data list
                market_data.append({
                    "currency": holding["currency"],
                    "data": data
                })
            except Exception as e:
                logging.error(f"Error fetching data for {holding['currency']}: {e}")
                continue

        if not market_data:
            return {"recommendations": "Unable to fetch market data for your holdings."}

        # Get AI-based recommendations using the portfolio and market data.
        recommendations = await ai_service.get_recommendations(portfolio, market_data)

        # Return the recommendations as a JSON response.
        return {"recommendations": recommendations}

    except Exception as e:
        logging.error(f"Error generating recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")

@router.get("/analysis")
async def get_analysis() -> Dict[str, Any]:
    """
    Fetches detailed cryptocurrency analysis and recommendations.

    Returns:
        A dictionary containing AI-generated recommendations based on the user's portfolio,
        current prices, and historical market data.

    Raises:
        HTTPException: If there is an error in generating recommendations.
    """
    try:
        # Get portfolio data from the Coinbase service.
        portfolio = await coinbase_service.get_portfolio()
        if not portfolio:
            return {"recommendations": "No cryptocurrency holdings found in your portfolio."}

        # Initialize a list to store market data for each asset in the portfolio.
        market_data = []

        for account in portfolio:
            try:
                # Format the product ID for fetching market data (e.g., BTC-GBP)
                product_id = f"{account['currency']}-GBP"
                # Fetch current price and historical data for the asset
                price_data = await coinbase_service.get_crypto_price(product_id)
                historical_data = await coinbase_service.get_historical_data(product_id)

                # Append the fetched data to the market_data list
                market_data.append({
                    "currency": account["currency"],
                    "current_price": price_data,
                    "historical_data": historical_data
                })
            except Exception as e:
                logging.error(f"Error fetching market data for {product_id}: {e}")
                continue

        if not market_data:
            return {"recommendations": "Unable to fetch market data for your holdings."}

        # Get AI-based recommendations using the portfolio and market data.
        recommendations = await ai_service.get_recommendations(portfolio, market_data)

        # Return the recommendations as a JSON response.
        return {"recommendations": recommendations}

    except Exception as e:
        logging.error(f"Error generating recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")