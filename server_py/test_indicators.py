"""
Tests for the deterministic indicator layer.

Values are checked against hand-computable cases rather than against the
implementation's own output, and every indicator is checked for the behaviour
that matters most here: returning ``None`` on a series too short to support it,
rather than a plausible-looking approximation.
"""

import math

import pytest

from app.services import indicators


def _linear(count: int, start: float = 100.0, step: float = 1.0):
    return [start + step * index for index in range(count)]


# --- moving averages --------------------------------------------------------


def test_sma_is_the_mean_of_the_final_window():
    assert indicators.sma([1, 2, 3, 4, 5], 3) == pytest.approx(4.0)


def test_sma_returns_none_when_the_series_is_too_short():
    assert indicators.sma([1, 2], 3) is None


def test_ema_series_is_seeded_with_the_sma_of_the_first_window():
    series = indicators.ema_series([2, 4, 6, 8], 2)
    # Seed is mean(2, 4) = 3; then 6 and 8 are folded in with k = 2/3.
    assert series[0] == pytest.approx(3.0)
    assert series[1] == pytest.approx(3 + (6 - 3) * (2 / 3))
    assert len(series) == 3


def test_ema_series_is_empty_when_the_series_is_too_short():
    assert indicators.ema_series([1, 2], 5) == []


# --- RSI --------------------------------------------------------------------


def test_rsi_is_100_for_a_series_that_only_rises():
    assert indicators.rsi(_linear(40)) == pytest.approx(100.0)


def test_rsi_is_zero_for_a_series_that_only_falls():
    assert indicators.rsi(_linear(40, start=200.0, step=-1.0)) == pytest.approx(0.0)


def test_rsi_sits_mid_range_for_alternating_moves():
    closes = [100.0]
    for index in range(40):
        closes.append(closes[-1] + (1.0 if index % 2 == 0 else -1.0))
    assert 40 < indicators.rsi(closes) < 60


def test_rsi_needs_one_more_close_than_its_period():
    assert indicators.rsi([100.0] * indicators.RSI_PERIOD) is None
    assert indicators.rsi(_linear(indicators.RSI_PERIOD + 1)) is not None


# --- MACD -------------------------------------------------------------------


def test_macd_histogram_is_the_line_minus_the_signal():
    result = indicators.macd(_linear(80))
    assert result is not None
    assert result.histogram == pytest.approx(result.line - result.signal)


def test_macd_line_is_positive_in_an_uptrend_and_negative_in_a_downtrend():
    rising = indicators.macd(_linear(80))
    falling = indicators.macd(_linear(80, start=200.0, step=-1.0))
    assert rising.line > 0
    assert falling.line < 0


def test_macd_needs_the_full_slow_plus_signal_window():
    minimum = indicators.MACD_SLOW + indicators.MACD_SIGNAL - 1
    assert indicators.macd(_linear(minimum - 1)) is None
    assert indicators.macd(_linear(minimum)) is not None


# --- crossover state --------------------------------------------------------


def test_a_sustained_uptrend_reads_as_short_above_long_not_a_fresh_cross():
    assert indicators.ma_cross_state(_linear(400)) == "short_above_long"


def test_a_sustained_downtrend_reads_as_short_below_long():
    assert indicators.ma_cross_state(_linear(400, start=600.0, step=-1.0)) == "short_below_long"


def test_a_reversal_is_reported_as_a_fresh_cross_only_while_it_is_fresh():
    """
    A long decline followed by a sharp rally eventually flips the 50-day above
    the 200-day. That flip must read as ``golden_cross`` on the bars right
    after it happens and as ``short_above_long`` once it is older than the
    lookback window -- the distinction is the whole point of the field.
    """
    base = _linear(260, start=400.0, step=-1.0)
    rally = [base[-1] + 40 * step for step in range(1, 90)]

    states = [
        indicators.ma_cross_state(base + rally[:length]) for length in range(1, len(rally))
    ]

    assert "golden_cross" in states, "the crossover was never reported as fresh"

    first_cross = states.index("golden_cross")
    # Fresh for the lookback window, then downgraded to a standing regime.
    assert states[first_cross + indicators.CROSS_LOOKBACK] == "short_above_long"
    # And before the cross, the short average was still below the long one.
    assert states[first_cross - 1] == "short_below_long"


def test_crossover_state_needs_history_for_both_averages_plus_the_lookback():
    assert indicators.ma_cross_state(_linear(indicators.SMA_LONG)) is None
    assert (
        indicators.ma_cross_state(_linear(indicators.SMA_LONG + indicators.CROSS_LOOKBACK))
        is not None
    )


# --- volatility and drawdown ------------------------------------------------


def test_a_flat_series_has_zero_volatility():
    assert indicators.annualised_volatility([100.0] * 60) == pytest.approx(0.0)


def test_volatility_is_annualised_from_the_return_standard_deviation():
    # Alternating +10% / -10% moves have a known return standard deviation.
    closes = [100.0]
    for index in range(40):
        closes.append(closes[-1] * (1.1 if index % 2 == 0 else 0.9))

    result = indicators.annualised_volatility(closes)
    assert result is not None
    # Roughly 10% per period, annualised over 365 periods.
    assert result == pytest.approx(0.1 * math.sqrt(365) * 100, rel=0.05)


def test_volatility_needs_one_more_close_than_its_window():
    assert indicators.annualised_volatility([100.0] * indicators.VOLATILITY_PERIOD) is None


def test_distance_from_high_is_zero_at_the_high_and_negative_below_it():
    assert indicators.distance_from_high_pct([50.0, 80.0, 100.0]) == pytest.approx(0.0)
    assert indicators.distance_from_high_pct([100.0, 80.0]) == pytest.approx(-20.0)


def test_period_high_is_none_for_an_empty_series():
    assert indicators.period_high([]) is None
    assert indicators.distance_from_high_pct([]) is None
