from datetime import datetime, timedelta
import os
from typing import List, Dict, Any
import json
from jose import jwt
from coinbase.rest import RESTClient
from dotenv import load_dotenv

class CoinbaseService:
    def __init__(self):
        # Ensure environment variables are loaded
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
            response_dict = self._to_dict(response)
            print("Raw API Response:", json.dumps(response_dict, indent=2))  # Debug log
            
            # Handle different response formats
            if isinstance(response_dict, dict):
                if "data" in response_dict:
                    accounts = response_dict["data"]
                else:
                    accounts = [response_dict]
            elif isinstance(response_dict, list):
                accounts = response_dict
            else:
                raise ValueError(f"Unexpected response type: {type(response_dict)}")

            # More robust balance checking
            portfolio = []
            for account in accounts:
                try:
                    balance = account.get("balance", {})
                    value = float(balance.get("amount", 0))
                    
                    if value > 0:
                        portfolio.append({
                            "currency": account.get("currency", ""),
                            "balance": value,
                            "available": value
                        })
                except (ValueError, TypeError) as e:
                    print(f"Error processing account {account.get('currency', 'unknown')}: {e}")
                    continue

            return portfolio

        except Exception as e:
            print(f"Error fetching portfolio: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            print(f"Full error details: {getattr(e, '__dict__', {})}")
            return []

    async def get_crypto_price(self, product_id: str) -> Dict[str, Any]:
        try:
            response = self.client.get_product_ticker(product_id=product_id)
            return {
                "price": response.get("price"),
                "time": response.get("time")
            }
        except Exception as e:
            print(f"Error fetching price for {product_id}: {e}")
            raise

    async def get_historical_data(self, product_id: str) -> List[Dict[str, Any]]:
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=1)
            
            response = self.client.get_product_candles(
                product_id=product_id,
                start=start_time.isoformat(),
                end=end_time.isoformat(),
                granularity="ONE_HOUR"
            )
            
            return [
                {
                    "time": candle["start"],
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "volume": candle["volume"]
                }
                for candle in response.get("candles", [])
            ]
        except Exception as e:
            print(f"Error fetching historical data for {product_id}: {e}")
            raise