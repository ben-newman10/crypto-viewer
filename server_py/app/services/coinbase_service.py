"""
Coinbase service module for interacting with the Coinbase Advanced Trade API.
Handles authentication, data fetching, and formatting of cryptocurrency data.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import functools
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

    #: Status codes worth a second attempt. Anything else (401/403/404) is a
    #: permanent answer, and retrying only multiplies the latency of an error.
    RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
    RETRY_ATTEMPTS = 3
    RETRY_BASE_DELAY = 0.3
    #: Coinbase reports crypto amounts to 8 decimal places.
    AMOUNT_PLACES = Decimal("0.00000001")

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

    async def _call(self, fn, *args, **kwargs) -> Any:
        """
        Run a synchronous SDK call off the event loop.

        The Coinbase SDK is built on `requests` and blocks. The frontend polls
        every 30 seconds and fans out one price request per holding, so calling
        it inline would stall every other request for the duration.
        """
        return await asyncio.to_thread(functools.partial(fn, *args, **kwargs))

    def _is_retryable(self, error: Exception) -> bool:
        """
        Decide whether an error is worth another attempt.

        A missing status means the request never got an answer (connection reset,
        timeout), which is retryable. An explicit status is retryable only if
        Coinbase is signalling a transient condition.
        """
        status = getattr(getattr(error, "response", None), "status_code", None)
        if status is None:
            return True
        return status in self.RETRYABLE_STATUS

    async def _retrying(self, fn, *args, **kwargs) -> Any:
        """Call `fn` via `_call`, retrying transient failures with backoff."""
        last_error: Exception | None = None

        for attempt in range(self.RETRY_ATTEMPTS):
            try:
                return await self._call(fn, *args, **kwargs)
            except Exception as error:
                last_error = error
                if not self._is_retryable(error):
                    raise
                if attempt < self.RETRY_ATTEMPTS - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    logging.warning(
                        f"{getattr(fn, '__name__', 'request')} failed "
                        f"({error}); retrying in {delay}s"
                    )
                    if delay:
                        await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]

    async def _spot_positions(self) -> List[Dict[str, Any]]:
        """
        Fetch spot positions across every portfolio.

        This is the source of truth for balances because the `/accounts`
        endpoint omits staked funds entirely: a staked ETH holding reports both
        `available_balance` and `hold` as zero there, while the portfolio
        breakdown reports it as a position with
        `account_type == 'ACCOUNT_TYPE_STAKED_FUNDS'`.

        Raises:
            Exception: if the portfolio list is unavailable, or if no single
                portfolio breakdown could be fetched. Callers use this to
                distinguish failure from an account that genuinely holds
                nothing.
        """
        response = await self._retrying(self.client.get_portfolios)
        portfolios = self._response_dict(response).get("portfolios", []) or []
        uuids = [entry.get("uuid") for entry in portfolios if entry.get("uuid")]

        if not uuids:
            raise RuntimeError("Coinbase returned no portfolios")

        positions: List[Dict[str, Any]] = []
        failures = 0

        for uuid in uuids:
            try:
                breakdown = await self._retrying(
                    self.client.get_portfolio_breakdown, portfolio_uuid=uuid
                )
            except Exception as error:
                # One inaccessible portfolio (e.g. futures) must not hide the
                # holdings in the others.
                failures += 1
                logging.warning(f"Could not fetch breakdown for {uuid}: {error}")
                continue

            payload = self._response_dict(breakdown).get("breakdown", {}) or {}
            positions.extend(payload.get("spot_positions", []) or [])

        if failures == len(uuids):
            raise RuntimeError("No portfolio breakdown could be fetched")

        return positions

    @staticmethod
    def _response_dict(response: Any) -> Dict[str, Any]:
        """Prefer the SDK's own converter; fall back for plain dicts."""
        if isinstance(response, dict):
            return response
        if hasattr(response, "to_dict"):
            return response.to_dict()
        return {}

    @classmethod
    def _amount(cls, value: Any) -> Decimal:
        """Coerce an API amount to Decimal, treating anything unusable as zero."""
        if value is None or value == "":
            return Decimal(0)
        try:
            # Route floats through str() so we get the shortest representation
            # rather than the full binary expansion of e.g. 0.00032322.
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            logging.warning(f"Ignoring unparseable amount: {value!r}")
            return Decimal(0)

    @classmethod
    def _amount_str(cls, value: Decimal) -> str:
        """Format an amount to at most 8 dp, keeping at least 2 for readability."""
        quantized = value.quantize(cls.AMOUNT_PLACES)
        trimmed = quantized.normalize()
        exponent = trimmed.as_tuple().exponent
        if isinstance(exponent, int) and exponent > -2:
            trimmed = trimmed.quantize(Decimal("0.01"))
        return f"{trimmed:f}"

    def _aggregate(self, positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Collapse spot positions into one holding per currency.

        A single asset can arrive as several positions -- a spot wallet and a
        staked-funds entry, for instance -- so amounts are summed per symbol.
        `balance` is the total including staked funds; `available` is only what
        can actually be traded.
        """
        totals: Dict[str, Dict[str, Decimal]] = {}

        for position in positions:
            if not isinstance(position, dict):
                continue
            currency = str(position.get("asset") or "").upper()
            if not currency:
                continue

            # Cash positions carry their amount in the fiat field only.
            balance = self._amount(position.get("total_balance_crypto"))
            if balance == 0:
                balance = self._amount(position.get("total_balance_fiat"))

            available = self._amount(position.get("available_to_trade_crypto"))
            if available == 0:
                available = self._amount(position.get("available_to_trade_fiat"))

            entry = totals.setdefault(
                currency, {"balance": Decimal(0), "available": Decimal(0)}
            )
            entry["balance"] += balance
            entry["available"] += available

        portfolio = [
            {
                "currency": currency,
                "balance": self._amount_str(amounts["balance"]),
                "available": self._amount_str(amounts["available"]),
            }
            for currency, amounts in totals.items()
            if amounts["balance"] > 0
        ]

        logging.info(f"Portfolio contains {len(portfolio)} holdings")
        return portfolio

    async def _accounts_fallback(self) -> List[Dict[str, Any]]:
        """
        Legacy `/accounts` reading, used only if the breakdown path fails.

        Note this view cannot see staked funds -- that is the limitation which
        made the breakdown endpoint necessary -- but it is better than nothing
        when the breakdown endpoint is unavailable.
        """
        logging.info("Falling back to the accounts endpoint")
        response = await self._retrying(self.client.get_accounts)
        accounts = self._response_dict(response).get("accounts", []) or []

        portfolio: List[Dict[str, Any]] = []

        for account in accounts:
            account_type = account.get("type", "")
            available_balance = account.get("available_balance", {})
            ready = account.get("ready", False)

            if not isinstance(available_balance, dict):
                continue
            if account_type == "ACCOUNT_TYPE_CRYPTO" and not ready:
                continue
            if account_type not in ("ACCOUNT_TYPE_CRYPTO", "ACCOUNT_TYPE_FIAT"):
                continue

            currency = available_balance.get("currency", "")
            available = self._amount(available_balance.get("value"))
            hold = account.get("hold")
            # Funds on hold are still owned, so they belong in the total.
            held = self._amount(hold.get("value")) if isinstance(hold, dict) else Decimal(0)
            balance = available + held

            if not currency or balance <= 0:
                continue

            portfolio.append({
                "currency": currency,
                "balance": self._amount_str(balance),
                "available": self._amount_str(available),
            })

        return portfolio

    async def get_portfolio(self) -> List[Dict[str, Any]]:
        """
        Fetch and format the user's cryptocurrency portfolio from Coinbase.

        Balances come from the portfolio breakdown endpoint so that staked funds
        are included; `/accounts` is a fallback that cannot see them.

        Returns:
            List of dictionaries containing currency holdings:
            [
                {
                    "currency": str,     # Cryptocurrency symbol
                    "balance": str,      # Total balance, including staked funds
                    "available": str     # Balance available for trading
                },
                ...
            ]
            An empty list means the account holds nothing.

        Raises:
            Exception: if the portfolio could not be fetched. Errors propagate
                so the API answers 500 and the UI can offer a retry, rather
                than rendering a misleading "no holdings" state.
        """
        logging.info("Fetching portfolio data...")

        try:
            positions = await self._spot_positions()
        except Exception as error:
            logging.warning(
                f"Portfolio breakdown unavailable ({error}); trying accounts endpoint"
            )
            return await self._accounts_fallback()

        # An empty breakdown is a successful answer, not a reason to fall back:
        # falling back here would make "holds nothing" indistinguishable from
        # "request failed".
        return self._aggregate(positions)

    async def get_crypto_price(self, product_id: str) -> Dict[str, Any]:
        """
        Fetch the current price and 24-hour change for a cryptocurrency.
        
        Args:
            product_id: The trading pair identifier (e.g., 'BTC-GBP')
            
        Returns:
            Dictionary containing price information:
            {
                "price": str,           # Current price
                "time": str,            # Timestamp of the price
                "change_24h": float,    # 24-hour price change percentage
                "price_24h_ago": str    # Price 24 hours ago
            }
        """
        try:
            # Get current price
            logging.info(f"Fetching price for {product_id}...")
            
            # Get 24h historical data
            historical_data = await self.get_historical_data(product_id)
            if not historical_data:
                raise ValueError("No historical data available")
                
            # Get current market data
            market_data = self.client.get_market_trades(
                product_id=product_id,
                limit=1
            )

            # Convert market_data to a dictionary and validate
            market_data_dict = self._to_dict(market_data)
            trades = market_data_dict.get('trades', [])
            if not isinstance(trades, list) or len(trades) == 0:
                raise ValueError(f"No trades found in market data")

            # Get current price from latest trade
            latest_trade = trades[0]
            current_price = float(latest_trade["price"])
            
            # Get price from 24h ago
            price_24h_ago = float(historical_data[-1]["close"])
            
            # Calculate percentage change
            change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100

            return {
                "price": str(current_price),
                "time": latest_trade.get("time", datetime.now(timezone.utc).isoformat()),
                "change_24h": round(change_24h, 2),
                "price_24h_ago": str(price_24h_ago)
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

            end_time = datetime.now(timezone.utc)
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