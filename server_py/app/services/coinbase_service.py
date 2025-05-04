from datetime import datetime, timedelta
import os
from typing import List, Dict, Any
import json
from dotenv import load_dotenv
from coinbase.rest import RESTClient
import httpx
import logging

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

    def _format_product_id(self, base_currency: str, quote_currency: str = "GBP") -> str:
        """Format the product ID as BASE-QUOTE."""
        if "-" in base_currency:
            # If base_currency already includes a quote currency, return it as is
            return base_currency
        return f"{base_currency}-{quote_currency}"

    async def get_portfolio(self) -> List[Dict[str, Any]]:
        try:
            logging.info("Fetching portfolio data...")
            response = self.client.get_accounts()
            logging.debug(f"Raw response type: {type(response)}")
            
            portfolio = []
            response_dict = self._to_dict(response)
            accounts = response_dict.get('accounts', [])
            logging.info(f"Found {len(accounts)} accounts")
            
            for account in accounts:
                account_type = account.get('type', '')
                available_balance = account.get('available_balance', {})
                ready = account.get('ready', False)
                
                logging.debug(f"Processing {account.get('name')} - Type: {account_type}, Ready: {ready}")
                
                if isinstance(available_balance, dict):
                    currency = available_balance.get('currency', '')
                    value = available_balance.get('value', '0')
                    
                    logging.debug(f"Balance for {currency}: {value}")
                    
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
                        logging.debug(f"Added {currency} to portfolio")
            
            logging.info(f"Final portfolio: {portfolio}")
            return portfolio
            
        except Exception as e:
            logging.error(f"Error fetching portfolio: {str(e)}", exc_info=True)
            return []

    async def get_crypto_price(self, base_currency: str) -> Dict[str, Any]:
        try:
            # Always format product ID as BASE-GBP
            product_id = self._format_product_id(base_currency, "GBP")

            logging.info(f"Fetching price for {product_id}...")

            # Validate if the product ID exists
            url = f"https://api.exchange.coinbase.com/products/{product_id}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)

                logging.debug(f"Response: {response.status_code}, Content: {response.text}")


                if response.status_code == 404:
                    raise ValueError(f"Trading pair {product_id} is not supported.")

            # Get current market data
            market_data = self.client.get_market_trades(
                product_id=product_id,
                limit=1
            )

            logging.debug(f"Raw market data: {market_data}")

            # Convert market_data to a dictionary
            market_data_dict = self._to_dict(market_data)
            logging.debug(f"Converted market data: {market_data_dict}")

            # Validate the structure of market_data
            trades = market_data_dict.get('trades', [])
            if not isinstance(trades, list) or len(trades) == 0:
                raise ValueError(f"No trades found in market data: {market_data_dict}")

            # Extract the latest trade
            latest_trade = trades[0]  # Get the first trade
            if not isinstance(latest_trade, dict) or 'price' not in latest_trade:
                raise ValueError(f"Invalid trade data: {latest_trade}")

            # Return the price and time
            return {
                "price": str(latest_trade["price"]),
                "time": latest_trade.get("time", datetime.utcnow().isoformat())
            }

        except ValueError as ve:
            logging.error(f"ValueError: {ve}")
            return {"error": str(ve)}
        except Exception as e:
            # Handle unsupported trading pairs or other errors
            logging.error(f"Error fetching price for {product_id}: {e}", exc_info=True)
            return {"error": f"Unable to fetch price for {base_currency}. Please check if the trading pair is supported."}

    async def get_historical_data(self, base_currency: str) -> List[Dict[str, Any]]:
        try:
            # Format product ID as BASE-GBP
            product_id = self._format_product_id(base_currency)
            logging.info(f"Fetching historical data for {product_id}...")

            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=1)
            granularity = 3600  # ONE_HOUR in seconds

            url = f"https://api.exchange.coinbase.com/products/{product_id}/candles"
            params = {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "granularity": granularity
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                candles = response.json()

            logging.debug(f"Received candles data: {candles}")

            return [
                {
                    "time": datetime.fromtimestamp(candle[0]).isoformat(),
                    "low": str(candle[1]),
                    "high": str(candle[2]),
                    "open": str(candle[3]),
                    "close": str(candle[4]),
                    "volume": str(candle[5])
                }
                for candle in candles
            ]

        except Exception as e:
            logging.error(f"Error fetching historical data for {product_id}: {e}", exc_info=True)
            raise