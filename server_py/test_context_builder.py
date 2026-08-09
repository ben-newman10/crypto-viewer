"""
Tests for the grounding context.

The behaviour under test is mostly about honesty: that a metric which cannot be
computed says so instead of disappearing, that a failed source lowers the
confidence ceiling, and that the candle series is read in the right direction
(getting that backwards would invert every trend signal while still producing
perfectly plausible numbers).
"""

import pytest

from app.services.context_builder import ContextBuilder, _closes_oldest_first
from app.services.fakes import FakeCoinbaseService, FakeMarketContextService, Scenario
from app.services.fakes import scenarios


async def build(flags=None):
    scenario = Scenario.parse(flags)
    return await ContextBuilder(
        FakeCoinbaseService(scenario), FakeMarketContextService(scenario)
    ).build()


def field(context, name):
    return context.metric_index()[name]


# --- shape ------------------------------------------------------------------


async def test_every_crypto_holding_gets_a_context_and_fiat_does_not():
    context = await build()
    assert [asset.symbol for asset in context.assets] == ["BTC", "ETH", "SOL"]
    # GBP is cash, not a tradeable pair; it appears as a portfolio field only.
    assert field(context, "portfolio.cash_value").value == pytest.approx(1250.75)


async def test_candles_are_read_oldest_first():
    """
    Coinbase returns candles newest first. Reversing them is the single most
    consequential line in the builder: read the wrong way round, an uptrend
    reads as a downtrend and every indicator is confidently wrong.
    """
    candles = [{"close": "3"}, {"close": "2"}, {"close": "1"}]
    assert _closes_oldest_first(candles) == [1.0, 2.0, 3.0]


async def test_the_fixture_uptrend_reads_as_an_uptrend():
    context = await build()
    # BTC's fixture series rises over the window, so the 50-day average must
    # sit above the 200-day one.
    assert field(context, "BTC.sma_50").value > field(context, "BTC.sma_200").value
    assert field(context, "BTC.ma_cross_state").text == "short_above_long"

    # SOL's declines, so the relationship is the other way round.
    assert field(context, "SOL.sma_50").value < field(context, "SOL.sma_200").value
    assert field(context, "SOL.ma_cross_state").text == "short_below_long"


async def test_portfolio_weights_sum_to_a_hundred_percent_with_cash():
    context = await build()
    weights = [
        field(context, f"{asset.symbol}.portfolio_weight_pct").value
        for asset in context.assets
    ]
    weights.append(field(context, "portfolio.cash_weight_pct").value)
    assert sum(weights) == pytest.approx(100.0)


async def test_the_price_field_agrees_with_the_newest_candle():
    context = await build()
    # The fixture series is normalised to end on the quoted price, so a drift
    # between the two would mean the builder is pairing the wrong series with
    # the wrong asset.
    assert field(context, "BTC.price").value == pytest.approx(
        field(context, "BTC.period_high").value, rel=0.05
    )


# --- graceful degradation ---------------------------------------------------


async def test_full_data_gives_complete_coverage_and_a_high_ceiling():
    context = await build()
    for asset in context.assets:
        assert asset.completeness.ratio == 1.0
        assert asset.completeness.categories_missing == []
        assert asset.confidence_ceiling == "high"


async def test_short_history_marks_the_trend_fields_unavailable_rather_than_omitting_them():
    context = await build(scenarios.SHORT_HISTORY)

    for name in ("BTC.sma_50", "BTC.sma_200", "BTC.ma_cross_state"):
        metric = field(context, name)
        # Present, explicitly unavailable, and carrying the reason -- the model
        # has to be able to see the gap in order to react to it.
        assert metric.status == "unavailable"
        assert metric.note and "candles" in metric.note

    # Indicators with a shorter window are still computed from what is there.
    assert field(context, "BTC.rsi_14").status == "available"
    assert field(context, "BTC.macd_line").status == "available"

    assert "trend" in context.asset("BTC").completeness.categories_missing


async def test_a_failed_market_source_costs_two_categories_and_lowers_the_ceiling():
    context = await build(scenarios.ERROR_MARKET_CONTEXT)

    assert field(context, "market.fear_greed_index").status == "unavailable"
    assert field(context, "BTC.market_cap").status == "unavailable"
    assert context.sources["coingecko"] == "unavailable"

    asset = context.asset("BTC")
    assert set(asset.completeness.categories_missing) == {"sentiment", "market_structure"}
    assert asset.confidence_ceiling == "medium"


async def test_thin_data_from_every_direction_caps_confidence_at_low():
    context = await build(scenarios.PARTIAL_DATA)
    for asset in context.assets:
        assert asset.confidence_ceiling == "low"
        assert asset.completeness.ratio < 0.5


async def test_a_price_failure_does_not_take_the_candle_derived_fields_with_it():
    context = await build(scenarios.ERROR_PRICES)

    assert field(context, "BTC.price").status == "unavailable"
    assert field(context, "BTC.change_24h_pct").status == "unavailable"
    # The indicators come from the candle series, which is unaffected.
    assert field(context, "BTC.rsi_14").status == "available"
    assert field(context, "BTC.sma_200").status == "available"


async def test_a_candle_failure_does_not_take_the_price_with_it():
    context = await build(scenarios.ERROR_HISTORICAL)

    assert field(context, "BTC.price").status == "available"
    assert field(context, "BTC.change_24h_pct").status == "available"
    assert field(context, "BTC.rsi_14").status == "unavailable"
    assert context.asset("BTC").confidence_ceiling in {"low", "medium"}


async def test_an_empty_portfolio_produces_no_assets():
    context = await build(scenarios.EMPTY_PORTFOLIO)
    assert context.assets == []


async def test_without_a_market_service_the_sources_report_it_as_disabled():
    context = await ContextBuilder(FakeCoinbaseService(), None).build()
    assert context.sources["coingecko"] == "disabled"
    assert field(context, "market.fear_greed_index").status == "unavailable"


# --- citability -------------------------------------------------------------


@pytest.mark.parametrize(
    "flags",
    [
        None,
        scenarios.SHORT_HISTORY,
        scenarios.ERROR_MARKET_CONTEXT,
        scenarios.ERROR_PRICES,
        scenarios.ERROR_HISTORICAL,
        scenarios.PARTIAL_DATA,
    ],
)
async def test_every_metric_has_a_unique_citable_field_name(flags):
    # Run across the degradation scenarios too: a field emitted from two code
    # paths would let a failure branch silently overwrite a good value.
    context = await build(flags)
    names = [metric.field for metric in context.shared_metrics]
    for asset in context.assets:
        names.extend(metric.field for metric in asset.metrics)

    assert len(names) == len(set(names)), "duplicate field names make a citation ambiguous"
    assert len(context.metric_index()) == len(names)


async def test_available_metrics_render_a_value_and_unavailable_ones_say_so():
    context = await build(scenarios.SHORT_HISTORY)
    assert field(context, "BTC.sma_200").rendered() == "unavailable"
    assert field(context, "BTC.price").rendered() == "52341.87"
