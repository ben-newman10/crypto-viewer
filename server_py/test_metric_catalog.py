"""
The metric catalogue is the single source of a metric's name and meaning.

These tests exist to stop two specific regressions:

* a metric shipping to a reader with no plain-English definition, and
* the same field being labelled two different ways depending on which code
  path built it -- which is exactly what had already happened to
  ``distance_from_period_high_pct`` before the catalogue existed.
"""

import pytest

from app.schemas.grounding import SIGNAL_CATEGORIES, CATEGORY_LABELS
from app.schemas.metric_catalog import CATALOG, spec_for, suffix_of
from app.services.context_builder import INDICATOR_FIELDS

#: Terms a definition must not lean on unexplained -- the whole point of the
#: field is to be readable without a trading background. "RSI" is allowed only
#: where the surrounding sentence defines it.
JARGON = ["overbought", "oversold", "bullish", "bearish"]


def test_every_entry_has_a_plain_definition():
    for suffix, spec in CATALOG.items():
        assert spec.plain.strip(), f"{suffix} has no plain-English definition"
        assert spec.label.strip(), f"{suffix} has no label"


def test_definitions_explain_their_own_jargon():
    """A term of art may appear, but only in a sentence that says what it means."""
    for suffix, spec in CATALOG.items():
        for term in JARGON:
            if term in spec.plain.lower():
                assert "mean" in spec.plain.lower() or "described as" in spec.plain.lower(), (
                    f"{suffix} uses {term!r} without explaining it"
                )


def test_definitions_do_not_give_advice():
    """Definitions describe a measure. Telling the reader what to do is not their job."""
    for suffix, spec in CATALOG.items():
        lowered = spec.plain.lower()
        for phrase in ["you should", "we recommend", "worth buying", "worth selling"]:
            assert phrase not in lowered, f"{suffix} gives advice: {phrase!r}"


def test_every_category_used_has_a_reader_facing_label():
    for suffix, spec in CATALOG.items():
        assert spec.category in CATEGORY_LABELS, (
            f"{suffix} uses category {spec.category!r} with no display label"
        )


def test_every_indicator_field_is_in_the_catalogue():
    """The candle-failure branch builds these by name alone, so all must resolve."""
    for field in INDICATOR_FIELDS:
        assert spec_for(f"BTC.{field}")


def test_indicator_fields_cover_the_scored_categories():
    """Sanity check on the fixture above: the indicators span trend/momentum/volatility."""
    categories = {spec_for(f"BTC.{field}").category for field in INDICATOR_FIELDS}
    assert {"trend", "momentum", "volatility"} <= categories
    assert categories <= set(SIGNAL_CATEGORIES)


def test_the_same_suffix_resolves_whatever_the_symbol():
    assert spec_for("BTC.rsi_14") is spec_for("ETH.rsi_14")


def test_suffix_of_takes_everything_after_the_first_dot():
    assert suffix_of("BTC.rsi_14") == "rsi_14"
    assert suffix_of("portfolio.total_value") == "total_value"
    # A bare name is its own key rather than an empty lookup.
    assert suffix_of("total_value") == "total_value"


def test_an_unknown_field_fails_loudly():
    """
    Better a crash in the pipeline than a figure reaching a reader with no
    explanation attached, which is what a generic fallback label would allow.
    """
    with pytest.raises(KeyError) as error:
        spec_for("BTC.exchange_netflow_7d")
    assert "metric catalogue" in str(error.value)
