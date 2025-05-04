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
            print("Fetching portfolio data...")
            response = self.client.get_accounts()
            print(f"Raw response type: {type(response)}")
            
            portfolio = []
            response_dict = self._to_dict(response)
            accounts = response_dict.get('accounts', [])
            print(f"Found {len(accounts)} accounts")
            
            for account in accounts:
                account_type = account.get('type', '')
                available_balance = account.get('available_balance', {})
                ready = account.get('ready', False)
                
                print(f"Processing {account.get('name')} - Type: {account_type}, Ready: {ready}")
                
                if isinstance(available_balance, dict):
                    currency = available_balance.get('currency', '')
                    value = available_balance.get('value', '0')
                    
                    print(f"Balance for {currency}: {value}")
                    
                    # Only include if:
                    # 1. For crypto: account is ready AND has non-zero balance
                    # 2. For fiat: has non-zero balance
                    if (account_type == 'ACCOUNT_TYPE_CRYPTO' and ready and float(value) > 0) or \
                       (account_type == 'ACCOUNT_TYPE_FIAT' and float(value) > 0):
                        portfolio.append({
                            "currency": currency,
                            "balance": value,
                            "available": value
                        })
                        print(f"Added {currency} to portfolio")
            
            print(f"Final portfolio: {portfolio}")
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