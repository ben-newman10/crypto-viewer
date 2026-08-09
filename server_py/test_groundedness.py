"""
Tests for the server-side groundedness check.

This is the layer that decides whether a model's claim survives contact with
the data, so the cases below are deliberately adversarial: fabricated numbers,
invented field names, values asserted for fields the model was told were
unavailable.
"""

import pytest

from app.schemas.grounding import (
    AssetContext,
    Metric,
    RecommendationContext,
    clamp_confidence,
    confidence_ceiling,
    downgrade,
    summarise_completeness,
)
from app.schemas.recommendation import ModelPayload, ModelRecommendation, ModelSupportingFact
from app.services import groundedness


def _metric(field, category="momentum", value=None, text=None, status="available", unit=""):
    return Metric(
        field=field,
        label=field,
        category=category,
        status=status,
        value=value,
        text=text,
        unit=unit,
    )


def _context(metrics):
    completeness = summarise_completeness(metrics)
    ceiling, reason = confidence_ceiling(completeness)
    return RecommendationContext(
        generated_at="2025-06-01T12:00:00+00:00",
        assets=[
            AssetContext(
                symbol="BTC",
                product_id="BTC-GBP",
                metrics=metrics,
                completeness=completeness,
                confidence_ceiling=ceiling,
                ceiling_reason=reason,
            )
        ],
    )


def _payload(*facts):
    return ModelPayload(
        summary="summary",
        recommendations=[
            ModelRecommendation(
                symbol="BTC",
                recommendation="hold",
                confidence="high",
                confidence_rationale="because",
                supporting_facts=list(facts),
            )
        ],
    )


def _fact(metric, value):
    return ModelSupportingFact(metric=metric, value=value, interpretation="...")


# --- value parsing ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("52341.87", 52341.87),
        ("£52,341.87", 52341.87),
        ("+2.34%", 2.34),
        ("-37.18 %", -37.18),
        ("1.19e12", 1.19e12),
        ("0.000041", 0.000041),
    ],
)
def test_parse_number_reads_the_formats_a_model_tends_to_produce(raw, expected):
    assert groundedness.parse_number(raw) == pytest.approx(expected)


def test_parse_number_returns_none_when_there_is_no_number():
    assert groundedness.parse_number("roughly flat") is None


def test_tolerance_forgives_rounding_but_not_invention():
    assert groundedness.values_agree(52341.87, 52341.8712)
    assert groundedness.values_agree(62.63, 62.6289)
    assert not groundedness.values_agree(73278.6, 52341.87)


# --- the check itself -------------------------------------------------------


def test_a_faithfully_quoted_value_passes():
    context = _context([_metric("BTC.rsi_14", value=62.6289)])
    outcome = groundedness.check(_payload(_fact("BTC.rsi_14", "62.6289")), context)

    assert outcome.passed
    assert outcome.checked == 1
    assert len(outcome.facts["BTC"]) == 1
    assert outcome.facts["BTC"][0].verified is True


def test_a_fabricated_number_is_corrected_to_the_context_value():
    context = _context([_metric("BTC.rsi_14", value=62.6289)])
    outcome = groundedness.check(_payload(_fact("BTC.rsi_14", "88.4")), context)

    assert not outcome.passed
    assert outcome.corrected == 1
    (violation,) = outcome.violations
    assert violation.kind == "value_mismatch"

    fact = outcome.facts["BTC"][0]
    # The payload carries the measured value, not the model's version of it.
    assert fact.value == "62.6289"
    assert fact.verified is False
    assert fact.model_stated_value == "88.4"


def test_an_invented_field_is_dropped_entirely():
    context = _context([_metric("BTC.rsi_14", value=62.6289)])
    outcome = groundedness.check(_payload(_fact("BTC.exchange_netflow_7d", "-12400")), context)

    assert outcome.dropped == 1
    assert outcome.facts["BTC"] == []
    assert outcome.violations[0].kind == "unknown_metric"


def test_stating_a_value_for_an_unavailable_field_is_a_violation():
    context = _context([_metric("BTC.sma_200", category="trend", status="unavailable")])
    outcome = groundedness.check(_payload(_fact("BTC.sma_200", "39619.07")), context)

    assert outcome.dropped == 1
    assert outcome.facts["BTC"] == []
    assert outcome.violations[0].kind == "cited_unavailable_metric"


def test_reporting_an_unavailable_field_as_unavailable_is_not_a_violation():
    context = _context([_metric("BTC.sma_200", category="trend", status="unavailable")])
    outcome = groundedness.check(_payload(_fact("BTC.sma_200", "unavailable")), context)

    assert outcome.passed
    # Honest, but it is not evidence, so it does not become a supporting fact.
    assert outcome.facts["BTC"] == []


def test_a_categorical_value_must_match_exactly():
    context = _context([_metric("BTC.ma_cross_state", category="trend", text="short_above_long")])

    assert groundedness.check(_payload(_fact("BTC.ma_cross_state", "short_above_long")), context).passed

    outcome = groundedness.check(_payload(_fact("BTC.ma_cross_state", "golden_cross")), context)
    assert outcome.violations[0].kind == "text_mismatch"
    assert outcome.facts["BTC"][0].value == "short_above_long"


def test_prose_where_a_number_was_required_is_a_violation():
    context = _context([_metric("BTC.rsi_14", value=62.6289)])
    outcome = groundedness.check(_payload(_fact("BTC.rsi_14", "elevated but not extreme")), context)

    assert outcome.violations[0].kind == "unparsable_value"
    assert outcome.facts["BTC"][0].value == "62.6289"


def test_feedback_names_every_offending_citation():
    context = _context([_metric("BTC.rsi_14", value=62.6289)])
    outcome = groundedness.check(
        _payload(_fact("BTC.rsi_14", "88.4"), _fact("BTC.made_up", "1")),
        context,
    )

    feedback = groundedness.feedback_for(outcome)
    assert "BTC.rsi_14" in feedback
    assert "BTC.made_up" in feedback
    assert "62.6289" in feedback


def test_the_retry_wins_ties_and_loses_when_it_is_worse():
    context = _context([_metric("BTC.rsi_14", value=62.6289)])
    good = groundedness.check(_payload(_fact("BTC.rsi_14", "62.6289")), context)
    bad = groundedness.check(_payload(_fact("BTC.rsi_14", "88.4")), context)

    chosen, used_retry = groundedness.pick_better(bad, good)
    assert used_retry and chosen is good

    chosen, used_retry = groundedness.pick_better(good, bad)
    assert not used_retry and chosen is good


# --- the confidence rubric --------------------------------------------------


def test_full_data_across_the_categories_permits_high_confidence():
    completeness = summarise_completeness(
        [
            _metric("a", category="trend", value=1),
            _metric("b", category="momentum", value=1),
            _metric("c", category="volatility", value=1),
            _metric("d", category="sentiment", value=1),
            _metric("e", category="market_structure", value=1),
        ]
    )
    ceiling, reason = confidence_ceiling(completeness)
    assert ceiling == "high"
    assert "100%" in reason


def test_three_categories_but_thin_data_caps_confidence_at_medium():
    metrics = [
        _metric("a", category="trend", value=1),
        _metric("b", category="momentum", value=1),
        _metric("c", category="volatility", value=1),
        _metric("d", category="sentiment", status="unavailable"),
        _metric("e", category="market_structure", status="unavailable"),
    ]
    ceiling, _ = confidence_ceiling(summarise_completeness(metrics))
    assert ceiling == "medium"


def test_a_single_surviving_category_caps_confidence_at_low():
    metrics = [
        _metric("a", category="trend", value=1),
        _metric("b", category="momentum", status="unavailable"),
        _metric("c", category="volatility", status="unavailable"),
        _metric("d", category="sentiment", status="unavailable"),
        _metric("e", category="market_structure", status="unavailable"),
    ]
    ceiling, _ = confidence_ceiling(summarise_completeness(metrics))
    assert ceiling == "low"


def test_the_ceiling_only_ever_lowers_the_reported_confidence():
    assert clamp_confidence("high", "medium") == "medium"
    assert clamp_confidence("low", "high") == "low"
    assert clamp_confidence("medium", "medium") == "medium"


def test_an_unrecognised_confidence_value_fails_safe():
    assert clamp_confidence("very high", "high") == "low"


def test_downgrade_stops_at_low():
    assert downgrade("high") == "medium"
    assert downgrade("medium") == "low"
    assert downgrade("low") == "low"


def test_the_plain_definition_travels_with_a_verified_fact():
    """
    The definition is authored server-side and attached here, not taken from
    the model -- so it reaches the UI on every fact the model cites correctly.
    """
    metric = Metric(
        field="BTC.rsi_14",
        label="RSI (14)",
        category="momentum",
        value=54.5,
        plain="Whether a coin has been bought hard or sold hard lately.",
    )
    payload = ModelPayload(
        summary="",
        recommendations=[
            ModelRecommendation(
                symbol="BTC",
                recommendation="hold",
                confidence="low",
                confidence_rationale="",
                supporting_facts=[
                    ModelSupportingFact(
                        metric="BTC.rsi_14",
                        value="54.5",
                        interpretation="Momentum is middling.",
                    )
                ],
            )
        ],
    )

    outcome = groundedness.check(payload, _context([metric]))
    fact = outcome.facts["BTC"][0]
    assert fact.plain == metric.plain
    assert fact.verified is True


def test_a_corrected_fact_still_carries_its_definition():
    """
    A misquoted value is the case where a reader most needs to understand what
    the figure even is, so the explanation must survive the correction.
    """
    metric = Metric(
        field="BTC.rsi_14",
        label="RSI (14)",
        category="momentum",
        value=54.5,
        plain="Whether a coin has been bought hard or sold hard lately.",
    )
    payload = ModelPayload(
        summary="",
        recommendations=[
            ModelRecommendation(
                symbol="BTC",
                recommendation="hold",
                confidence="high",
                confidence_rationale="",
                supporting_facts=[
                    ModelSupportingFact(
                        metric="BTC.rsi_14",
                        value="81.0",  # not what the context holds
                        interpretation="Momentum looks stretched.",
                    )
                ],
            )
        ],
    )

    outcome = groundedness.check(payload, _context([metric]))
    fact = outcome.facts["BTC"][0]
    assert fact.verified is False
    assert fact.value == "54.5"  # the measured value, not the quoted one
    assert fact.plain == metric.plain
