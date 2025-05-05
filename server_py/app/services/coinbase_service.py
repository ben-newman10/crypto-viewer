"""
Coinbase service module for interacting with the Coinbase Advanced Trade API.
Handles authentication, data fetching, and formatting of cryptocurrency data.
"""

from datetime import datetime, timedelta
import os
from typing import List, Dict, Any
import json
from dotenv import load_dotenv
from coinbase.rest import RESTClient
import httpx
import logging

class CoinbaseService:
    """
    Service class for interacting with Coinbase Advanced Trade API.
    Handles portfolio data, price information, and historical data retrieval.
    """

    def __init__(self):
        """
        Initialize the Coinbase service with API credentials from environment variables.
        Sets up the REST client for API communication.
        
        Raises:
            ValueError: If API credentials are missing or invalid
        """
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

    def _to_dict(self, obj: Any) -> Dict[str, Any]:
        """
        Convert API response objects to dictionaries for easier handling.
        Handles special Coinbase API response types by converting them to basic Python types.
        
        Args:
            obj: Response object from Coinbase API
            
        Returns:
            Dict containing the response data
        """
        try:
            if hasattr(obj, '__dict__'):
                # If object has a __dict__, convert its attributes to a dictionary
                return {k: self._to_dict(v) for k, v in obj.__dict__.items() 
                       if not k.startswith('_')}
            elif isinstance(obj, (list, tuple)):
                # Handle lists and tuples by converting their elements
                return [self._to_dict(item) for item in obj]
            elif isinstance(obj, dict):
                # Handle dictionaries by converting their values
                return {k: self._to_dict(v) for k, v in obj.items()}
            elif isinstance(obj, (str, int, float, bool, type(None))):
                # Basic types can be returned as-is
                return obj
            else:
                # For any other type, try to convert to string
                return str(obj)
        except Exception as e:
            logging.error(f"Error converting object to dict: {e}")
            return {}

    def _format_product_id(self, base_currency: str, quote_currency: str = "GBP") -> str:
        """
        Format a trading pair ID according to Coinbase specifications.
        
        Args:
            base_currency: The cryptocurrency symbol (e.g., 'BTC')
            quote_currency: The currency to price against (default: 'GBP')
            
        Returns:
            Formatted product ID (e.g., 'BTC-GBP')
        """
        return f"{base_currency.upper()}-{quote_currency.upper()}"

    async def get_portfolio(self) -> List[Dict[str, Any]]:
        """
        Fetch and format the user's cryptocurrency portfolio from Coinbase.
        
        Returns:
            List of dictionaries containing currency holdings:
            [
                {
                    "currency": str,     # Cryptocurrency symbol
                    "balance": str,      # Total balance
                    "available": str     # Available balance for trading
                },
                ...
            ]
        """
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
                    
                    # Include account if:
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

    async def get_crypto_price(self, product_id: str) -> Dict[str, Any]:
        """
        Fetch the current price for a cryptocurrency.
        
        Args:
            product_id: The trading pair identifier (e.g., 'BTC-GBP')
            
        Returns:
            Dictionary containing price information:
            {
                "price": str,           # Current price
                "time": str             # Timestamp of the price
            }
            
        Raises:
            ValueError: If the trading pair is not supported
        """
        try:
            # Use the product ID as-is since it's already formatted
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

            # Convert market_data to a dictionary and validate structure
            market_data_dict = self._to_dict(market_data)
            trades = market_data_dict.get('trades', [])
            if not isinstance(trades, list) or len(trades) == 0:
                raise ValueError(f"No trades found in market data: {market_data_dict}")

            # Extract the latest trade
            latest_trade = trades[0]
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
            logging.error(f"Error fetching price for {product_id}: {e}", exc_info=True)
            return {"error": f"Unable to fetch price for {product_id}. Please check if the trading pair is supported."}

    async def get_historical_data(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Fetch historical price data for a cryptocurrency.
        
        Args:
            product_id: The trading pair identifier (e.g., 'BTC-GBP')
            
        Returns:
            List of dictionaries containing historical price data:
            [
                {
                    "time": str,        # ISO format timestamp
                    "low": str,         # Lowest price in the period
                    "high": str,         # Highest price in the period
                    "open": str,        # Opening price
                    "close": str,        # Closing price
                    "volume": str       # Trading volume
                },
                ...
            ]
            
        Raises:
            Exception: If there is an error fetching the historical data
        """
        try:
            # Use the product ID as-is since it's already formatted
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