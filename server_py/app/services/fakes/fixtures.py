"""
Deterministic fixture data used by the fake Coinbase and OpenAI clients.

Everything here is static (or derived from a fixed seed) so that E2E
assertions and screenshots are stable across runs.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

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
# AI recommendations
# ---------------------------------------------------------------------------

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
