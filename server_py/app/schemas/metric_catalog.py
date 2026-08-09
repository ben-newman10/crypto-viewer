"""
The one place a metric's name, category, unit and plain-English meaning live.

Before this module those four things were positional arguments repeated at every
``_available()`` call in ``context_builder.py`` -- and every indicator was
written out twice, once in the candle-failure branch and once in the happy path.
They had already drifted apart: ``distance_from_period_high_pct`` was
"Distance from 300-day high" in one branch and "Distance from {bars}-day high"
in the other, for the same field.

``plain`` is the novice definition. It answers "what even is this?" for a reader
who has never traded, and it is deliberately written here in code rather than
asked of the model: a definition is a fixed fact about a metric, not an
observation about today's market, so it must not vary run to run or be capable
of being got wrong. It is also deliberately *not* rendered into the prompt --
the model does not need it, so it costs nothing in tokens and cannot be
contradicted by the model's own prose.

A ``plain`` string describes what the metric measures and how to read its scale.
It never says what to do about it: that is the recommendation's job, under the
grounding rules, with the disclaimer attached.
"""

from typing import Dict

from pydantic import BaseModel, Field

from .grounding import (
    CATEGORY_MARKET_STRUCTURE,
    CATEGORY_MOMENTUM,
    CATEGORY_POSITION,
    CATEGORY_REFERENCE,
    CATEGORY_SENTIMENT,
    CATEGORY_TREND,
    CATEGORY_VOLATILITY,
)


class MetricSpec(BaseModel):
    """Everything about a metric that does not depend on the day's data."""

    label: str = Field(..., description="Accurate short name, shown in the UI.")
    category: str = Field(..., description="Signal category, for completeness scoring.")
    unit: str = Field("", description="Literal unit, e.g. '%'. Empty for a bare count.")
    #: The unit is the portfolio's quote currency, which is configurable, so it
    #: is substituted per run rather than baked in here.
    quote_unit: bool = False
    plain: str = Field(
        ...,
        description="What this measures, in words a first-time reader can follow.",
    )


#: Keyed on the part of the field after the first dot, so ``BTC.rsi_14``,
#: ``ETH.rsi_14`` and ``portfolio.total_value`` all resolve through one table.
CATALOG: Dict[str, MetricSpec] = {
    # -- momentum ----------------------------------------------------------
    "rsi_14": MetricSpec(
        label="RSI (14)",
        category=CATEGORY_MOMENTUM,
        plain=(
            "Whether a coin has been bought hard or sold hard over the last couple of "
            "weeks, boiled down to a score from 0 to 100. Around 50 means buying and "
            "selling pressure have been roughly even. Above 70 is often described as "
            "'overbought' — buyers have pushed a long way in one go — and below 30 as "
            "'oversold', the same idea in reverse."
        ),
    ),
    "macd_line": MetricSpec(
        label="MACD line",
        category=CATEGORY_MOMENTUM,
        plain=(
            "Compares a short-term average price with a longer-term one to show which "
            "way the price has been pulling recently. Above zero means the recent "
            "average is the higher of the two."
        ),
    ),
    "macd_signal": MetricSpec(
        label="MACD signal",
        category=CATEGORY_MOMENTUM,
        plain=(
            "A smoothed version of the MACD line, used as the thing to compare it "
            "against. On its own it says little; the gap between the two is the point."
        ),
    ),
    "macd_histogram": MetricSpec(
        label="MACD histogram",
        category=CATEGORY_MOMENTUM,
        plain=(
            "The gap between the MACD line and its signal line. A positive number "
            "means the recent trend is picking up speed; a negative one means it is "
            "losing speed. The further from zero, the stronger that effect."
        ),
    ),
    "change_24h_pct": MetricSpec(
        label="24h change",
        category=CATEGORY_MOMENTUM,
        unit="%",
        plain=(
            "How much the price has moved in the last day, as a percentage. A single "
            "day says very little about a longer trend."
        ),
    ),
    # -- trend -------------------------------------------------------------
    "sma_50": MetricSpec(
        label="50-day moving average",
        category=CATEGORY_TREND,
        quote_unit=True,
        plain=(
            "The average closing price over the last 50 days. Averaging smooths out "
            "day-to-day noise, so comparing today's price with it gives a rough sense "
            "of whether the price is currently high or low for this period."
        ),
    ),
    "sma_200": MetricSpec(
        label="200-day moving average",
        category=CATEGORY_TREND,
        quote_unit=True,
        plain=(
            "The average closing price over the last 200 days — the same idea as the "
            "50-day average, but over a much longer window, so it moves slowly and "
            "reflects the longer-run picture."
        ),
    ),
    "ma_cross_state": MetricSpec(
        label="50/200 crossover state",
        category=CATEGORY_TREND,
        plain=(
            "Whether the 50-day average price sits above or below the 200-day one. "
            "Above is conventionally read as strength, below as weakness. 'Golden "
            "cross' and 'death cross' mean the two have only just crossed over, which "
            "traders watch more closely than a gap that has been there for months."
        ),
    ),
    # -- volatility --------------------------------------------------------
    "volatility_30d_annualised_pct": MetricSpec(
        label="30-day annualised volatility",
        category=CATEGORY_VOLATILITY,
        unit="%",
        plain=(
            "How much this price has been jumping around over the last month, scaled "
            "up to a yearly figure so it can be compared with other assets. A higher "
            "number means bigger swings — in both directions, not just down."
        ),
    ),
    "distance_from_period_high_pct": MetricSpec(
        label="Distance from the recent high",
        category=CATEGORY_VOLATILITY,
        unit="%",
        plain=(
            "How far below its best closing price of recent months the coin is now. "
            "This is the high for the period the app has data for, not the highest "
            "price ever."
        ),
    ),
    # -- sentiment ---------------------------------------------------------
    "fear_greed_index": MetricSpec(
        label="Fear & Greed Index",
        category=CATEGORY_SENTIMENT,
        plain=(
            "A published gauge of the mood across the whole crypto market, from 0 to "
            "100. Low numbers mean investors are broadly nervous, high numbers mean "
            "they are broadly enthusiastic. It describes the market as a whole, not "
            "this coin in particular."
        ),
    ),
    "fear_greed_classification": MetricSpec(
        label="Fear & Greed classification",
        category=CATEGORY_SENTIMENT,
        plain=(
            "The same market-mood gauge expressed as a word, from 'extreme fear' "
            "through to 'extreme greed'."
        ),
    ),
    # -- market structure --------------------------------------------------
    "market_cap": MetricSpec(
        label="Market cap",
        category=CATEGORY_MARKET_STRUCTURE,
        quote_unit=True,
        plain=(
            "What every coin in circulation would be worth in total at today's price. "
            "It is the usual way of talking about how big a crypto asset is."
        ),
    ),
    "circulating_supply": MetricSpec(
        label="Circulating supply",
        category=CATEGORY_MARKET_STRUCTURE,
        plain="How many coins currently exist and are available to be traded.",
    ),
    "ath_change_pct": MetricSpec(
        label="Distance from all-time high",
        category=CATEGORY_MARKET_STRUCTURE,
        unit="%",
        plain=(
            "How far below its best price ever the coin is now. Unlike the recent "
            "high, this looks back over the coin's whole history."
        ),
    ),
    # -- this holding ------------------------------------------------------
    "price": MetricSpec(
        label="Current price",
        category=CATEGORY_REFERENCE,
        quote_unit=True,
        plain="What one coin is worth right now, as reported by Coinbase.",
    ),
    "balance": MetricSpec(
        label="Units held",
        category=CATEGORY_POSITION,
        plain=(
            "How much of this coin you hold, counting anything staked as well as what "
            "is free to trade."
        ),
    ),
    "holding_value": MetricSpec(
        label="Value of holding",
        category=CATEGORY_POSITION,
        quote_unit=True,
        plain="What your holding of this coin is worth: how much you hold, at today's price.",
    ),
    "portfolio_weight_pct": MetricSpec(
        label="Share of portfolio",
        category=CATEGORY_POSITION,
        unit="%",
        plain=(
            "How much of your total portfolio sits in this one coin. A high share "
            "means your overall result depends heavily on this single asset."
        ),
    ),
    "period_high": MetricSpec(
        label="Highest close in the period",
        category=CATEGORY_REFERENCE,
        quote_unit=True,
        plain=(
            "The best closing price over the stretch of history the app pulled in — "
            "the figure the 'distance from the recent high' is measured against."
        ),
    ),
    "candles_available": MetricSpec(
        label="Daily candles used",
        category=CATEGORY_REFERENCE,
        plain=(
            "How many days of price history the app actually got hold of. It matters "
            "because the longer measures need a certain amount of history before they "
            "can be worked out at all."
        ),
    ),
    # -- portfolio-wide ----------------------------------------------------
    "total_value": MetricSpec(
        label="Portfolio value",
        category=CATEGORY_POSITION,
        quote_unit=True,
        plain="Everything you hold added up: your coins at today's prices, plus any cash.",
    ),
    "cash_value": MetricSpec(
        label="Cash balance",
        category=CATEGORY_POSITION,
        quote_unit=True,
        plain="How much of your balance is ordinary money rather than crypto.",
    ),
    "cash_weight_pct": MetricSpec(
        label="Cash as share of portfolio",
        category=CATEGORY_POSITION,
        unit="%",
        plain=(
            "What proportion of your portfolio is held as cash rather than crypto. "
            "Cash does not move with the crypto market."
        ),
    ),
    "asset_count": MetricSpec(
        label="Number of crypto holdings",
        category=CATEGORY_POSITION,
        plain=(
            "How many different coins you hold. Holding very few means the portfolio "
            "rises and falls with a small number of assets."
        ),
    ),
}


def suffix_of(field: str) -> str:
    """The catalogue key for a field: everything after the first dot."""
    _, _, suffix = field.partition(".")
    return suffix or field


def spec_for(field: str) -> MetricSpec:
    """
    The spec for a grounding field.

    Raises rather than falling back to a generic label, so that adding a metric
    without also writing its plain-English definition fails loudly in the tests
    instead of quietly shipping an unexplained figure to a reader.
    """
    suffix = suffix_of(field)
    try:
        return CATALOG[suffix]
    except KeyError:
        raise KeyError(
            f"no metric catalogue entry for {field!r} (looked up {suffix!r}); "
            "add one to CATALOG including its plain-English definition"
        ) from None
