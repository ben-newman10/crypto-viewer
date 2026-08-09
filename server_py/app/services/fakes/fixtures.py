"""
Deterministic fixture data used by the fake Coinbase and OpenAI clients.

Everything here is static (or derived from a fixed seed) so that E2E
assertions and screenshots are stable across runs.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

# A realistic mixed portfolio: three crypto holdings plus a fiat cash balance.
# The fiat entry exists on purpose -- the real Coinbase account listing includes
# it, and it exercises the frontend's "cash, not a tradeable pair" branch.
#
# ETH is deliberately fully staked (available 0, balance non-zero). Staked funds
# are absent from the /accounts endpoint entirely and only surface via
# get_portfolio_breakdown, so this shape guards the regression where a wholly
# staked holding vanished from the portfolio. `balance` includes staked funds.
PORTFOLIO: List[Dict[str, str]] = [
    {"currency": "BTC", "balance": "0.45230000", "available": "0.45230000"},
    {"currency": "ETH", "balance": "3.21450000", "available": "0.00000000"},
    {"currency": "SOL", "balance": "42.50000000", "available": "42.50000000"},
    {"currency": "GBP", "balance": "1250.75", "available": "1250.75"},
]

# Current price and 24h movement per product id, mirroring the shape returned by
# CoinbaseService.get_crypto_price().
PRICES: Dict[str, Dict[str, Any]] = {
    "BTC-GBP": {
        "price": "52341.87",
        "change_24h": 2.34,
        "price_24h_ago": "51144.53",
    },
    "ETH-GBP": {
        "price": "2456.12",
        "change_24h": -1.87,
        "price_24h_ago": "2502.93",
    },
    "SOL-GBP": {
        "price": "118.44",
        "change_24h": 5.62,
        "price_24h_ago": "112.13",
    },
}
# Note: there is deliberately no GBP-GBP entry. Coinbase has no such trading
# pair, so the fake mirrors reality: the frontend treats fiat as cash valued 1:1
# and never requests a price for it.

# Fixed reference timestamp so that generated candles never shift between runs.
REFERENCE_TIME = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

# Hand-picked multipliers giving each asset a recognisable 24h shape without
# relying on a random number generator.
_CANDLE_SHAPE: List[float] = [
    1.000, 0.994, 0.991, 0.996, 1.002, 1.007, 1.004, 0.998,
    0.993, 0.989, 0.992, 0.999, 1.006, 1.011, 1.008, 1.003,
    0.997, 0.995, 1.001, 1.009, 1.014, 1.010, 1.005, 1.000,
]


def price_for(product_id: str) -> Dict[str, Any]:
    """Return the fixture price payload for a product id, with a timestamp."""
    base = PRICES.get(product_id.upper())
    if base is None:
        return {
            "error": (
                f"Unable to fetch price for {product_id}. "
                "Please check if the trading pair is supported."
            )
        }
    return {
        "price": base["price"],
        "time": REFERENCE_TIME.isoformat(),
        "change_24h": base["change_24h"],
        "price_24h_ago": base["price_24h_ago"],
    }


def historical_for(product_id: str) -> List[Dict[str, str]]:
    """
    Build 24 hourly candles for a product id.

    Candles are ordered newest-first to match the live Coinbase candles
    endpoint, which the real service relies on when it reads ``[-1]`` as the
    price 24 hours ago.
    """
    base = PRICES.get(product_id.upper())
    if base is None:
        raise ValueError(f"No historical data available for {product_id}")

    latest = float(base["price"])
    candles: List[Dict[str, str]] = []

    for hours_ago, shape in enumerate(_CANDLE_SHAPE):
        close = latest * shape
        open_ = latest * _CANDLE_SHAPE[max(hours_ago - 1, 0)]
        timestamp = REFERENCE_TIME - timedelta(hours=hours_ago)
        candles.append(
            {
                "time": timestamp.isoformat(),
                "low": f"{min(open_, close) * 0.997:.2f}",
                "high": f"{max(open_, close) * 1.003:.2f}",
                "open": f"{open_:.2f}",
                "close": f"{close:.2f}",
                "volume": f"{120.5 + hours_ago * 3.25:.2f}",
            }
        )

    return candles


# ---------------------------------------------------------------------------
# Long-run daily candles
# ---------------------------------------------------------------------------
# The recommendation pipeline needs several hundred daily closes to compute a
# 200-day moving average. These are generated from a closed-form shape function
# rather than a random walk so that every indicator value -- and therefore every
# assertion and screenshot in the E2E suite -- is identical on every run.

#: Daily candles the fake serves, matching the real service's request size.
DAILY_CANDLE_COUNT = 300

#: Per-asset shape parameters, chosen so the three holdings sit in genuinely
#: different technical situations: BTC in an established uptrend, ETH roughly
#: range-bound, SOL in a downtrend. That gives the UI (and the tests) a mix of
#: crossover states and momentum readings rather than three of the same.
_DAILY_SHAPE: Dict[str, Dict[str, float]] = {
    #: ``drift`` is the log-change from the oldest candle to the newest, so a
    #: positive value means the series rose over the window.
    "BTC-GBP": {"drift": 0.62, "amplitude": 0.055, "period": 47.0, "phase": 0.0},
    "ETH-GBP": {"drift": 0.08, "amplitude": 0.085, "period": 61.0, "phase": 1.1},
    "SOL-GBP": {"drift": -0.28, "amplitude": 0.115, "period": 39.0, "phase": 2.3},
}


def _daily_close(latest: float, index: int, count: int, shape: Dict[str, float]) -> float:
    """
    Closing price ``index`` bars into a ``count``-bar series ending at ``latest``.

    Both the trend and the oscillation terms are normalised to 1 at the final
    bar, so the series always ends exactly on the fixture's current price and
    the candle data agrees with the price endpoint.
    """
    last = count - 1
    position = (index - last) / last  # -1 at the oldest bar, 0 at the newest

    trend = math.exp(shape["drift"] * position)

    def wave(at: int) -> float:
        # Three terms: a slow cycle, a slower one that stops the series from
        # repeating cleanly, and a fast one that supplies day-to-day movement.
        # Without the fast term the realised-volatility figure comes out near
        # zero, which would make the volatility signal category meaningless in
        # every test and screenshot.
        angle = 2 * math.pi * at / shape["period"] + shape["phase"]
        return (
            math.sin(angle)
            + 0.4 * math.sin(angle * 0.37)
            + 0.55 * math.sin(angle * 7.7 + 0.9)
        )

    oscillation = 1 + shape["amplitude"] * (wave(index) - wave(last))

    return latest * trend * oscillation


def daily_candles_for(product_id: str, count: int = DAILY_CANDLE_COUNT) -> List[Dict[str, str]]:
    """
    Build a deterministic daily candle series, newest first.

    Matches the ordering of the live Coinbase candles endpoint, which the
    context builder reverses before computing indicators.

    The full series is always generated and then truncated from the newest end,
    so a shortened request returns exactly the bars a full request would have
    returned -- a "less history" scenario really is the same data with the old
    bars removed, not a differently-shaped series.
    """
    key = product_id.upper()
    base = PRICES.get(key)
    shape = _DAILY_SHAPE.get(key)
    if base is None or shape is None:
        raise ValueError(f"No daily candle data available for {product_id}")

    latest = float(base["price"])
    total = DAILY_CANDLE_COUNT
    closes = [_daily_close(latest, index, total, shape) for index in range(total)]

    candles: List[Dict[str, str]] = []
    for index in range(total - 1, -1, -1):  # newest first
        close = closes[index]
        open_ = closes[index - 1] if index > 0 else close
        timestamp = REFERENCE_TIME - timedelta(days=(total - 1 - index))
        candles.append(
            {
                "time": timestamp.isoformat(),
                "low": f"{min(open_, close) * 0.988:.2f}",
                "high": f"{max(open_, close) * 1.012:.2f}",
                "open": f"{open_:.2f}",
                "close": f"{close:.2f}",
                "volume": f"{1840.5 + (index % 23) * 61.4:.2f}",
            }
        )

    return candles[: max(1, min(count, total))]


# ---------------------------------------------------------------------------
# Supplementary market context
# ---------------------------------------------------------------------------
# Stands in for CoinGecko (market cap, circulating supply, all-time high) and
# alternative.me (Fear & Greed Index).

MARKET_STATS: Dict[str, Dict[str, Optional[float]]] = {
    "BTC": {
        "market_cap": 1_031_400_000_000.0,
        "circulating_supply": 19_712_000.0,
        "ath": 57_800.0,
        "ath_change_pct": -9.44,
    },
    "ETH": {
        "market_cap": 295_600_000_000.0,
        "circulating_supply": 120_310_000.0,
        "ath": 3_910.0,
        "ath_change_pct": -37.18,
    },
    "SOL": {
        "market_cap": 55_900_000_000.0,
        "circulating_supply": 471_900_000.0,
        "ath": 210.5,
        "ath_change_pct": -43.73,
    },
}

FEAR_GREED_VALUE = 61.0
FEAR_GREED_CLASSIFICATION = "Greed"


# ---------------------------------------------------------------------------
# AI recommendations
# ---------------------------------------------------------------------------
# The direction and self-reported confidence the fake model returns per asset.
# Fixed per symbol so the E2E suite can assert on a specific badge. The
# supporting facts are *not* fixed: the fake reads them out of the grounding
# context it is given, which is what makes the groundedness check meaningful
# end to end rather than a check against another fixture.

FAKE_CALLS: Dict[str, Dict[str, str]] = {
    "BTC": {"recommendation": "hold", "confidence": "high"},
    "ETH": {"recommendation": "buy", "confidence": "medium"},
    "SOL": {"recommendation": "sell", "confidence": "low"},
}

FAKE_SUMMARY = (
    "The portfolio is concentrated in three large-cap assets alongside a cash "
    "balance. The available technical signals point in different directions "
    "across the three holdings, so each is assessed on its own evidence below."
)


RECOMMENDATIONS_MARKDOWN = """## Portfolio Overview

Your portfolio is concentrated in three major assets with a healthy cash
reserve. Total crypto exposure looks balanced, though **BTC** dominates by
value.

### Per-holding recommendations

- **BTC — Hold.** Momentum is positive (+2.34% over 24h) and the position is
  already your largest by value. No action needed.
- **ETH — Accumulate.** The 24h dip of 1.87% is within normal volatility and
  network activity remains strong. Consider a small addition on further
  weakness.
- **SOL — Trim.** Up 5.62% in 24 hours after an extended run. Taking partial
  profits would reduce concentration risk.

### Risk assessment

Overall risk is **moderate**. The cash balance provides useful dry powder, but
the portfolio has no exposure outside large-cap assets.

### Market trend analysis

Broad market sentiment is constructive with rising volumes across majors.
Watch for volatility around upcoming macro announcements.

*This is illustrative analysis, not financial advice.*
"""

# Returned when the upstream model call fails but the service degrades
# gracefully rather than raising -- mirrors AIService's own fallback string.
RECOMMENDATIONS_UNAVAILABLE = (
    "Unable to generate recommendations at this time. Please try again later."
)
