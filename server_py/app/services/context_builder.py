"""
Builds the grounding context handed to the model.

This is where raw Coinbase data becomes named, typed, citable fields. Two
things matter more than anything else here:

* **Indicators are computed, never asked for.** RSI, MACD, moving averages,
  volatility and drawdown all come from ``services/indicators.py``. The model
  receives finished values.
* **Failures become fields.** A pair whose candles fail to load, an asset with
  no CoinGecko id, a sentiment endpoint that times out -- each produces a
  metric with ``status="unavailable"`` and a reason, not a missing key. The
  confidence ceiling is derived from those gaps, so a silent omission would
  quietly *raise* the confidence of a call it should have lowered.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from ..schemas.grounding import (
    AssetContext,
    Metric,
    RecommendationContext,
    confidence_ceiling,
    summarise_completeness,
)
from ..schemas.metric_catalog import spec_for
from . import indicators

#: Balances held as cash rather than as a tradeable pair. Mirrors the
#: frontend's ``isFiat`` so the two agree on what counts as a position.
FIAT_CURRENCIES = {"GBP", "USD", "EUR"}

#: Daily candles requested per asset. 300 is the Coinbase endpoint's maximum
#: and the minimum that supports a 200-period moving average with a lookback.
CANDLE_GRANULARITY_SECONDS = 86400
CANDLE_LIMIT = 300


def _available(
    field: str,
    value: Optional[float] = None,
    text: Optional[str] = None,
    note: Optional[str] = None,
    quote_currency: str = "",
) -> Metric:
    """
    A metric that was computed, or an unavailable one when the value is None.

    Name, category and unit come from the metric catalogue rather than the call
    site, so the same field cannot end up labelled two different ways depending
    on which branch built it.
    """
    spec = spec_for(field)
    unit = quote_currency if spec.quote_unit else spec.unit

    if value is None and text is None:
        return Metric(
            field=field,
            label=spec.label,
            category=spec.category,
            status="unavailable",
            unit=unit,
            note=note or "not available for this asset",
            plain=spec.plain,
        )
    return Metric(
        field=field,
        label=spec.label,
        category=spec.category,
        status="available",
        value=None if value is None else round(value, 6),
        text=text,
        unit=unit,
        note=note,
        plain=spec.plain,
    )


def _unavailable(field: str, reason: str, quote_currency: str = "") -> Metric:
    spec = spec_for(field)
    return Metric(
        field=field,
        label=spec.label,
        category=spec.category,
        status="unavailable",
        unit=quote_currency if spec.quote_unit else spec.unit,
        note=reason,
        plain=spec.plain,
    )


def _closes_oldest_first(candles: Sequence[Dict[str, Any]]) -> List[float]:
    """
    Extract closing prices in oldest-first order.

    Coinbase returns candles newest-first; every indicator in this codebase
    expects the opposite, and getting that backwards silently inverts every
    trend signal, so the conversion happens exactly once, here.
    """
    closes: List[float] = []
    for candle in reversed(list(candles)):
        try:
            closes.append(float(candle["close"]))
        except (KeyError, TypeError, ValueError):
            continue
    return closes


#: Every technical field, in the order they are emitted. Used by the
#: candle-failure branch so it cannot fall out of step with the happy path.
INDICATOR_FIELDS: List[str] = [
    "rsi_14",
    "macd_line",
    "macd_signal",
    "macd_histogram",
    "sma_50",
    "sma_200",
    "ma_cross_state",
    "volatility_30d_annualised_pct",
    "distance_from_period_high_pct",
]


def _indicator_metrics(
    symbol: str,
    closes: List[float],
    reason: Optional[str],
    quote_currency: str = "",
) -> List[Metric]:
    """
    Every technical metric for one asset.

    ``reason`` is set when the candle fetch failed outright, in which case each
    field is emitted as unavailable with that reason attached.

    The 24h change is deliberately *not* here: it comes from the price
    endpoint, so it survives a candle failure and must not be overwritten by
    one.
    """
    if reason is not None:
        return [
            _unavailable(f"{symbol}.{field}", reason, quote_currency)
            for field in INDICATOR_FIELDS
        ]

    bars = len(closes)
    short = f"only {bars} daily candles available"

    macd_result = indicators.macd(closes)
    sma_50 = indicators.sma(closes, indicators.SMA_SHORT)
    sma_200 = indicators.sma(closes, indicators.SMA_LONG)
    cross = indicators.ma_cross_state(closes)
    rsi_value = indicators.rsi(closes)
    volatility = indicators.annualised_volatility(closes)
    drawdown = indicators.distance_from_high_pct(closes)

    metrics: List[Metric] = []

    metrics.append(
        _available(
            f"{symbol}.rsi_14",
            value=rsi_value,
            note=(
                "Wilder RSI over daily closes; above 70 is conventionally overbought, "
                "below 30 oversold"
                if rsi_value is not None
                else f"needs {indicators.RSI_PERIOD + 1} daily closes, {short}"
            ),
        )
    )

    macd_note = (
        "MACD(12,26,9) on daily closes"
        if macd_result is not None
        else f"needs {indicators.MACD_SLOW + indicators.MACD_SIGNAL - 1} daily closes, {short}"
    )
    metrics.append(
        _available(
            f"{symbol}.macd_line",
            value=macd_result.line if macd_result else None,
            note=macd_note,
        )
    )
    metrics.append(
        _available(
            f"{symbol}.macd_signal",
            value=macd_result.signal if macd_result else None,
            note=macd_note,
        )
    )
    metrics.append(
        _available(
            f"{symbol}.macd_histogram",
            value=macd_result.histogram if macd_result else None,
            note=(
                "MACD line minus signal line; positive means bullish momentum"
                if macd_result
                else macd_note
            ),
        )
    )

    metrics.append(
        _available(
            f"{symbol}.sma_50",
            value=sma_50,
            quote_currency=quote_currency,
            note=None if sma_50 is not None else f"needs 50 daily closes, {short}",
        )
    )
    metrics.append(
        _available(
            f"{symbol}.sma_200",
            value=sma_200,
            quote_currency=quote_currency,
            note=None if sma_200 is not None else f"needs 200 daily closes, {short}",
        )
    )
    metrics.append(
        _available(
            f"{symbol}.ma_cross_state",
            text=cross,
            note=(
                "golden_cross / death_cross mean the 50-day crossed the 200-day within "
                "the last 5 days; short_above_long / short_below_long mean the crossover "
                "is older than that"
                if cross is not None
                else f"needs {indicators.SMA_LONG + indicators.CROSS_LOOKBACK} daily closes, {short}"
            ),
        )
    )

    metrics.append(
        _available(
            f"{symbol}.volatility_30d_annualised_pct",
            value=volatility,
            note=(
                "standard deviation of the last 30 daily returns, annualised"
                if volatility is not None
                else f"needs 31 daily closes, {short}"
            ),
        )
    )
    metrics.append(
        _available(
            f"{symbol}.distance_from_period_high_pct",
            value=drawdown,
            note=(
                f"against the highest close in the {bars} daily candles held; this is a "
                "period high, not an all-time high"
                if drawdown is not None
                else "no usable candles"
            ),
        )
    )

    return metrics


class ContextBuilder:
    """Assembles a :class:`RecommendationContext` from the available sources."""

    def __init__(self, coinbase_service, market_context_service=None) -> None:
        self.coinbase = coinbase_service
        self.market = market_context_service

    async def build(self, quote_currency: str = "GBP") -> RecommendationContext:
        portfolio = await self.coinbase.get_portfolio()

        holdings = [
            holding
            for holding in portfolio
            if str(holding.get("currency", "")).upper() not in FIAT_CURRENCIES
        ]
        cash = [
            holding
            for holding in portfolio
            if str(holding.get("currency", "")).upper() in FIAT_CURRENCIES
        ]

        sources: Dict[str, str] = {"coinbase": "ok"}

        # Per-asset market data, gathered concurrently: one slow pair should not
        # serialise the whole context build.
        per_asset = await asyncio.gather(
            *(
                self._fetch_asset(str(holding["currency"]).upper(), quote_currency)
                for holding in holdings
            )
        )

        symbols = [str(holding["currency"]).upper() for holding in holdings]
        stats, fear_greed = await self._fetch_market_context(symbols, quote_currency, sources)

        # Portfolio weights need every holding's value, so they are computed
        # after the price fetches have all returned.
        cash_value = sum(_to_float(holding.get("balance")) or 0.0 for holding in cash)
        asset_values: Dict[str, Optional[float]] = {}
        for holding, fetched in zip(holdings, per_asset):
            symbol = str(holding["currency"]).upper()
            balance = _to_float(holding.get("balance"))
            price = fetched["price"]
            asset_values[symbol] = (
                balance * price if balance is not None and price is not None else None
            )

        total_value = cash_value + sum(value for value in asset_values.values() if value)

        shared_metrics = self._shared_metrics(
            total_value=total_value,
            cash_value=cash_value,
            asset_count=len(holdings),
            fear_greed=fear_greed,
            quote_currency=quote_currency,
        )

        assets: List[AssetContext] = []
        for holding, fetched in zip(holdings, per_asset):
            symbol = str(holding["currency"]).upper()
            assets.append(
                self._asset_context(
                    symbol=symbol,
                    product_id=fetched["product_id"],
                    holding=holding,
                    fetched=fetched,
                    value=asset_values.get(symbol),
                    total_value=total_value,
                    stats=stats.get(symbol),
                    shared_metrics=shared_metrics,
                    quote_currency=quote_currency,
                )
            )

        return RecommendationContext(
            generated_at=datetime.now(timezone.utc).isoformat(),
            quote_currency=quote_currency,
            assets=assets,
            shared_metrics=shared_metrics,
            sources=sources,
        )

    # -- fetching -----------------------------------------------------------

    async def _fetch_asset(self, symbol: str, quote_currency: str) -> Dict[str, Any]:
        """Price and candles for one asset, with failures captured rather than raised."""
        product_id = f"{symbol}-{quote_currency}"
        result: Dict[str, Any] = {
            "product_id": product_id,
            "price": None,
            "change_24h": None,
            "price_error": None,
            "closes": [],
            "candle_error": None,
        }

        try:
            price_payload = await self.coinbase.get_crypto_price(product_id)
            if isinstance(price_payload, dict) and "error" in price_payload:
                # The price endpoint answers 200 with an `error` key on failure.
                result["price_error"] = str(price_payload["error"])
            else:
                result["price"] = _to_float(price_payload.get("price"))
                result["change_24h"] = _to_float(price_payload.get("change_24h"))
        except Exception as error:  # noqa: BLE001
            logging.warning("Price unavailable for %s: %s", product_id, error)
            result["price_error"] = f"price lookup failed for {product_id}"

        try:
            candles = await self.coinbase.get_candles(
                product_id,
                granularity=CANDLE_GRANULARITY_SECONDS,
                limit=CANDLE_LIMIT,
            )
            result["closes"] = _closes_oldest_first(candles)
            if not result["closes"]:
                result["candle_error"] = f"no candles returned for {product_id}"
        except Exception as error:  # noqa: BLE001
            logging.warning("Candles unavailable for %s: %s", product_id, error)
            result["candle_error"] = f"candle history unavailable for {product_id}"

        return result

    async def _fetch_market_context(
        self,
        symbols: List[str],
        quote_currency: str,
        sources: Dict[str, str],
    ):
        """Supplementary market data; absent sources are recorded, not raised."""
        if self.market is None:
            sources["coingecko"] = "disabled"
            sources["fear_greed"] = "disabled"
            return {}, None

        try:
            stats = await self.market.get_asset_stats(symbols, quote_currency)
        except Exception as error:  # noqa: BLE001
            logging.warning("Market stats unavailable: %s", error)
            stats = {}
        sources["coingecko"] = "ok" if stats else "unavailable"

        try:
            fear_greed = await self.market.get_fear_greed()
        except Exception as error:  # noqa: BLE001
            logging.warning("Fear & Greed unavailable: %s", error)
            fear_greed = None
        sources["fear_greed"] = "ok" if fear_greed else "unavailable"

        return stats, fear_greed

    # -- assembly -----------------------------------------------------------

    def _shared_metrics(
        self,
        total_value: float,
        cash_value: float,
        asset_count: int,
        fear_greed,
        quote_currency: str,
    ) -> List[Metric]:
        cash_weight = (cash_value / total_value * 100) if total_value else None

        metrics = [
            _available(
                "portfolio.total_value",
                value=total_value,
                quote_currency=quote_currency,
                note="crypto holdings valued at the current price, plus cash",
            ),
            _available(
                "portfolio.cash_value",
                value=cash_value,
                quote_currency=quote_currency,
            ),
            _available("portfolio.cash_weight_pct", value=cash_weight),
            _available("portfolio.asset_count", value=float(asset_count)),
        ]

        if fear_greed is not None:
            metrics.append(
                _available(
                    "market.fear_greed_index",
                    value=fear_greed.value,
                    note="alternative.me, 0 = extreme fear, 100 = extreme greed",
                )
            )
            metrics.append(
                _available(
                    "market.fear_greed_classification",
                    text=fear_greed.classification,
                )
            )
        else:
            reason = "sentiment source did not respond"
            metrics.append(_unavailable("market.fear_greed_index", reason))
            metrics.append(_unavailable("market.fear_greed_classification", reason))

        return metrics

    def _asset_context(
        self,
        symbol: str,
        product_id: str,
        holding: Dict[str, Any],
        fetched: Dict[str, Any],
        value: Optional[float],
        total_value: float,
        stats,
        shared_metrics: List[Metric],
        quote_currency: str,
    ) -> AssetContext:
        balance = _to_float(holding.get("balance"))
        closes: List[float] = fetched["closes"]
        price_error: Optional[str] = fetched["price_error"]
        candle_error: Optional[str] = fetched["candle_error"]

        metrics: List[Metric] = [
            _available(
                f"{symbol}.price",
                value=fetched["price"],
                quote_currency=quote_currency,
                note=price_error,
            ),
            _available(f"{symbol}.balance", value=balance),
            _available(
                f"{symbol}.holding_value",
                value=value,
                quote_currency=quote_currency,
                note=None if value is not None else "needs both a balance and a price",
            ),
            _available(
                f"{symbol}.portfolio_weight_pct",
                value=(value / total_value * 100) if (value and total_value) else None,
            ),
            _available(
                f"{symbol}.candles_available",
                value=float(len(closes)),
                note=f"a {CANDLE_LIMIT}-candle daily series was requested",
            ),
        ]

        # 24h change comes from the price endpoint rather than the candle
        # series, so it survives a candle failure and vice versa.
        metrics.append(
            _available(
                f"{symbol}.change_24h_pct",
                value=fetched["change_24h"],
                note=price_error,
            )
        )

        metrics.extend(_indicator_metrics(symbol, closes, candle_error, quote_currency))

        period_high = indicators.period_high(closes)
        metrics.append(
            _available(
                f"{symbol}.period_high",
                value=period_high,
                quote_currency=quote_currency,
                note=candle_error or f"the highest daily close in the {len(closes)} days held",
            )
        )

        metrics.extend(self._market_structure_metrics(symbol, stats, quote_currency))

        # Sentiment is market-wide but bears on every asset's confidence, so the
        # shared metrics are folded into this asset's completeness score.
        completeness = summarise_completeness(metrics + shared_metrics)
        ceiling, reason = confidence_ceiling(completeness)

        return AssetContext(
            symbol=symbol,
            product_id=product_id,
            metrics=metrics,
            completeness=completeness,
            confidence_ceiling=ceiling,
            ceiling_reason=reason,
        )

    def _market_structure_metrics(self, symbol: str, stats, quote_currency: str) -> List[Metric]:
        if stats is None:
            reason = "no market-structure data for this asset"
            return [
                _unavailable(f"{symbol}.market_cap", reason, quote_currency),
                _unavailable(f"{symbol}.circulating_supply", reason),
                _unavailable(f"{symbol}.ath_change_pct", reason),
            ]

        return [
            _available(
                f"{symbol}.market_cap",
                value=stats.market_cap,
                quote_currency=quote_currency,
                note="CoinGecko",
            ),
            _available(
                f"{symbol}.circulating_supply",
                value=stats.circulating_supply,
                note="CoinGecko",
            ),
            _available(
                f"{symbol}.ath_change_pct",
                value=stats.ath_change_pct,
                note="CoinGecko; against the all-time high in the quote currency",
            ),
        ]


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed else None
