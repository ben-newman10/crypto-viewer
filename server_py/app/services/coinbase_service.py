from datetime import datetime, timedelta
import os
from typing import List, Dict, Any
import json
from dotenv import load_dotenv
from coinbase.rest import RESTClient

class CoinbaseService:
    def __init__(self):
        load_dotenv()
        
        api_key = os.getenv("COINBASE_API_KEY")
        api_secret = os.getenv("COINBASE_API_SECRET")
        
        if not api_key or not api_secret:
            raise ValueError(
                "Missing Coinbase API credentials. Please ensure COINBASE_API_KEY and "
                "COINBASE_API_SECRET are set in your .env file."
            )
        
        try:
            self.client = RESTClient(api_key=api_key, api_secret=api_secret)
        except Exception as e:
            raise ValueError(f"Failed to initialize Coinbase client: {str(e)}")

    def _to_dict(self, obj: Any) -> Dict:
        """Convert Coinbase response objects to dictionaries."""
        if hasattr(obj, '__dict__'):
            return {k: self._to_dict(v) for k, v in obj.__dict__.items() 
                   if not k.startswith('_')}
        elif isinstance(obj, list):
            return [self._to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        else:
            return obj

    async def get_portfolio(self) -> List[Dict[str, Any]]:
        try:
            response = self.client.get_accounts()
            if isinstance(response, str):
                response_data = json.loads(response)
            else:
                response_data = response
            
            portfolio = []
            if isinstance(response_data, dict):
                accounts = response_data.get("accounts", [])
                for account in accounts:
                    if isinstance(account, dict):
                        # Extract account information
                        account_type = account.get("type", "")
                        available_balance = account.get("available_balance", {})
                        
                        if isinstance(available_balance, dict):
                            currency = available_balance.get("currency", "")
                            value = available_balance.get("value", "0")
                            
                            # Include account if it's a crypto account or has a non-zero balance
                            if (account_type == "ACCOUNT_TYPE_CRYPTO" and account.get("ready", False)) or float(value) > 0:
                                portfolio.append({
                                    "currency": currency,
                                    "balance": value,
                                    "available": value
                                })
            
            return portfolio

        except Exception as e:
            print(f"Error fetching portfolio: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            print(f"Full error details: {getattr(e, '__dict__', {})}")
            return []

    async def get_crypto_price(self, product_id: str) -> Dict[str, Any]:
        try:
            # Get current market data
            market_data = self.client.get_market_trades(
                product_id=product_id,
                limit=1
            )
            
            if market_data and len(market_data) > 0:
                latest_trade = market_data[0]
                return {
                    "price": str(latest_trade["price"]),
                    "time": datetime.utcnow().isoformat()
                }
            else:
                raise ValueError(f"No price data available for {product_id}")
                
        except Exception as e:
            print(f"Error fetching price for {product_id}: {e}")
            raise

    async def get_historical_data(self, product_id: str) -> List[Dict[str, Any]]:
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=1)
            
            candles = self.client.get_market_candles(
                product_id=product_id,
                start=start_time.isoformat(),
                end=end_time.isoformat(),
                granularity="ONE_HOUR"
            )
            
            return [
                {
                    "time": datetime.fromtimestamp(candle["start"]).isoformat(),
                    "open": str(candle["open"]),
                    "high": str(candle["high"]),
                    "low": str(candle["low"]),
                    "close": str(candle["close"]),
                    "volume": str(candle["volume"])
                }
                for candle in candles
            ]
            
        except Exception as e:
            print(f"Error fetching historical data for {product_id}: {e}")
            raise