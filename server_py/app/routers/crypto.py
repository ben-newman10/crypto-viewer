"""
Router module for cryptocurrency-related API endpoints.
Provides endpoints for portfolio data, current prices, and historical data.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from ..services.coinbase_service import CoinbaseService

router = APIRouter()
coinbase_service = CoinbaseService()

@router.get("/portfolio")
async def get_portfolio() -> List[Dict[str, Any]]:
    """
    Fetch the user's cryptocurrency portfolio.
    
    Returns:
        List of dictionaries containing cryptocurrency holdings
        Each holding includes currency symbol, total balance, and available balance
        
    Raises:
        HTTPException(500): If portfolio fetch fails
    """
    try:
        return await coinbase_service.get_portfolio()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio")

@router.get("/price/{product_id}")
async def get_price(product_id: str) -> Dict[str, Any]:
    """
    Fetch the current price for a cryptocurrency.
    
    Args:
        product_id: Trading pair identifier (e.g., 'BTC-GBP', 'ETH-GBP')
        
    Returns:
        Dictionary containing current price and timestamp
        
    Raises:
        HTTPException(500): If price fetch fails
    """
    try:
        return await coinbase_service.get_crypto_price(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch price for {product_id}")

@router.get("/historical/{product_id}")
async def get_historical(product_id: str) -> List[Dict[str, Any]]:
    """
    Fetch historical price data for a cryptocurrency.
    
    Args:
        product_id: Trading pair identifier (e.g., 'BTC-GBP', 'ETH-GBP')
        
    Returns:
        List of dictionaries containing historical price data points
        Each point includes timestamp, open, high, low, close prices, and volume
        
    Raises:
        HTTPException(500): If historical data fetch fails
    """
    try:
        return await coinbase_service.get_historical_data(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch historical data for {product_id}")