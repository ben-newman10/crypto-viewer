"""
Deterministic technical indicators.

Every number the model is allowed to talk about is computed here, in code, from
a plain list of closing prices. The language model is never asked to do
arithmetic on a raw price series: it receives finished values and reasons about
them.

All functions take closes ordered **oldest first** and return ``None`` when the
series is too short to compute the indicator honestly. A ``None`` is what later
becomes an explicitly ``unavailable`` field in the grounding context -- it is
never silently replaced with a partial or approximated value.
"""

from math import sqrt
from statistics import fmean, pstdev
from typing import List, Optional, Sequence

# Minimum sample sizes. These are the standard definitions; falling below them
# does not produce a "close enough" figure, it produces no figure at all.
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
SMA_SHORT = 50
SMA_LONG = 200
VOLATILITY_PERIOD = 30

# Candles per year for the daily series used by the context builder. Used to
# annualise the volatility figure; crypto trades every day, so 365 rather than
# the 252 trading days used for equities.
PERIODS_PER_YEAR = 365

# How many bars back the moving-average comparison looks when deciding whether
# a crossover is *recent* rather than a long-standing regime.
CROSS_LOOKBACK = 5


def sma(closes: Sequence[float], period: int) -> Optional[float]:
    """Simple moving average of the last ``period`` closes."""
    if period <= 0 or len(closes) < period:
        return None
    return fmean(closes[-period:])


def ema_series(closes: Sequence[float], period: int) -> List[float]:
    """
    Exponential moving average series, seeded with the SMA of the first window.

    The returned list is shorter than the input by ``period - 1`` entries: an
    EMA is undefined before its seed window is complete.
    """
    if period <= 0 or len(closes) < period:
        return []

    multiplier = 2 / (period + 1)
    seed = fmean(closes[:period])
    series = [seed]

    for close in closes[period:]:
        series.append((close - series[-1]) * multiplier + series[-1])

    return series


def rsi(closes: Sequence[float], period: int = RSI_PERIOD) -> Optional[float]:
    """
    Wilder's Relative Strength Index over the whole series.

    Returns a value in 0-100, or ``None`` when there are fewer than
    ``period + 1`` closes (one more than the period, because RSI is computed
    from changes rather than levels).
    """
    if len(closes) < period + 1:
        return None

    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]

    avg_gain = fmean(gains[:period])
    avg_loss = fmean(losses[:period])

    # Wilder smoothing over the remainder of the series.
    for index in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[index]) / period
        avg_loss = (avg_loss * (period - 1) + losses[index]) / period

    if avg_loss == 0:
        # No downside at all in the window: RSI is 100 by definition.
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


class MacdResult:
    """MACD line, signal line and histogram for the most recent bar."""

    __slots__ = ("line", "signal", "histogram")

    def __init__(self, line: float, signal: float, histogram: float) -> None:
        self.line = line
        self.signal = signal
        self.histogram = histogram


def macd(
    closes: Sequence[float],
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> Optional[MacdResult]:
    """
    Moving Average Convergence Divergence for the latest bar.

    Needs ``slow + signal - 1`` closes: the signal line is an EMA of the MACD
    line, which itself only begins once the slow EMA has a full seed window.
    """
    if len(closes) < slow + signal - 1:
        return None

    fast_ema = ema_series(closes, fast)
    slow_ema = ema_series(closes, slow)
    if not fast_ema or not slow_ema:
        return None

    # The two EMA series start at different offsets; align them on their tails.
    overlap = min(len(fast_ema), len(slow_ema))
    macd_line = [fast_ema[-overlap + i] - slow_ema[-overlap + i] for i in range(overlap)]

    signal_series = ema_series(macd_line, signal)
    if not signal_series:
        return None

    line = macd_line[-1]
    signal_value = signal_series[-1]
    return MacdResult(line=line, signal=signal_value, histogram=line - signal_value)


def ma_cross_state(
    closes: Sequence[float],
    short_period: int = SMA_SHORT,
    long_period: int = SMA_LONG,
    lookback: int = CROSS_LOOKBACK,
) -> Optional[str]:
    """
    Classify the short/long moving-average relationship.

    Returns one of:

    ``golden_cross``
        The short MA crossed *above* the long MA within the last ``lookback``
        bars.
    ``death_cross``
        The short MA crossed *below* the long MA within the last ``lookback``
        bars.
    ``short_above_long``
        The short MA is above the long MA, but the crossover is older than the
        lookback window.
    ``short_below_long``
        The short MA is below the long MA, crossover older than the lookback.

    ``None`` when there is not enough history for both averages plus the
    lookback comparison -- a cross cannot be claimed without the earlier bar to
    compare against.
    """
    if len(closes) < long_period + lookback:
        return None

    short_now = sma(closes, short_period)
    long_now = sma(closes, long_period)
    short_then = sma(closes[:-lookback], short_period)
    long_then = sma(closes[:-lookback], long_period)

    if None in (short_now, long_now, short_then, long_then):
        return None

    if short_now > long_now:
        return "golden_cross" if short_then <= long_then else "short_above_long"
    if short_now < long_now:
        return "death_cross" if short_then >= long_then else "short_below_long"
    return "short_above_long"


def annualised_volatility(
    closes: Sequence[float],
    period: int = VOLATILITY_PERIOD,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> Optional[float]:
    """
    Annualised volatility as a percentage, from the last ``period`` returns.

    Computed as the population standard deviation of simple returns over the
    window, scaled by ``sqrt(periods_per_year)``.
    """
    if len(closes) < period + 1:
        return None

    window = closes[-(period + 1):]
    returns = [
        (window[i] - window[i - 1]) / window[i - 1]
        for i in range(1, len(window))
        if window[i - 1] != 0
    ]
    if len(returns) < 2:
        return None

    return pstdev(returns) * sqrt(periods_per_year) * 100


def period_high(closes: Sequence[float]) -> Optional[float]:
    """Highest close in the supplied series."""
    return max(closes) if closes else None


def distance_from_high_pct(closes: Sequence[float]) -> Optional[float]:
    """
    How far the latest close sits below the highest close in the series, as a
    negative percentage (0 means the series is at its high).

    This is a *period* high over whatever history was supplied -- it is not an
    all-time high, and the grounding context labels it accordingly.
    """
    high = period_high(closes)
    if high is None or high == 0:
        return None
    return (closes[-1] - high) / high * 100
