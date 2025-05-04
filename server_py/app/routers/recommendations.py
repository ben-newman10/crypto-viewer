from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ..services.ai_service import AIService
from ..services.coinbase_service import CoinbaseService

router = APIRouter()
ai_service = AIService()
coinbase_service = CoinbaseService()

@router.get("/")
async def get_recommendations() -> Dict[str, str]:
    try:
        portfolio = await coinbase_service.get_portfolio()
        
        # Get market data for each cryptocurrency in the portfolio
        market_data = []
        for holding in portfolio:
            product_id = f"{holding['currency']}-GBP"
            data = await coinbase_service.get_historical_data(product_id)
            market_data.append({"currency": holding["currency"], "data": data})

        recommendations = await ai_service.get_recommendations(portfolio, market_data)
        return {"recommendations": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")

@router.get("/analysis")
async def get_analysis() -> Dict[str, Any]:
    try:
        # Get portfolio data
        portfolio = await coinbase_service.get_portfolio()
        
        # Get market data for each asset in portfolio
        market_data = []
        for account in portfolio:
            product_id = account.get("currency", "").upper() + "-GBP"
            try:
                price_data = await coinbase_service.get_crypto_price(product_id)
                historical_data = await coinbase_service.get_historical_data(product_id)
                market_data.append({
                    "currency": account.get("currency"),
                    "current_price": price_data,
                    "historical_data": historical_data
                })
            except Exception as e:
                print(f"Error fetching market data for {product_id}: {e}")
                continue
        
        # Get AI recommendations
        recommendations = await ai_service.get_recommendations(portfolio, market_data)
        return {"recommendations": recommendations}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")