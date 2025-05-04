from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from ..services.coinbase_service import CoinbaseService

router = APIRouter()
coinbase_service = CoinbaseService()

@router.get("/portfolio")
async def get_portfolio() -> List[Dict[str, Any]]:
    try:
        return await coinbase_service.get_portfolio()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio")

@router.get("/price/{product_id}")
async def get_price(product_id: str) -> Dict[str, Any]:
    try:
        return await coinbase_service.get_crypto_price(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch price for {product_id}")

@router.get("/historical/{product_id}")
async def get_historical(product_id: str) -> List[Dict[str, Any]]:
    try:
        return await coinbase_service.get_historical_data(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch historical data for {product_id}")