"""
End-to-end tests for the recommendations endpoint and the pipeline behind it.

These go through the real FastAPI app with fake third-party clients, so they
cover the whole path: grounding context, structured model call, server-side
verification, confidence clamping, disclaimer injection and logging.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import DISCLAIMER, SCENARIO_COOKIE
from app.main import app
from app.services.fakes import scenarios

client = TestClient(app)


def get(flags=None, path="/api/recommendations/"):
    cookies = {SCENARIO_COOKIE: flags} if flags else None
    return client.get(path, cookies=cookies)


def by_symbol(body, symbol):
    return next(item for item in body["recommendations"] if item["symbol"] == symbol)


# --- shape ------------------------------------------------------------------


def test_the_endpoint_returns_one_structured_call_per_holding():
    response = get()
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ok"
    assert [item["symbol"] for item in body["recommendations"]] == ["BTC", "ETH", "SOL"]

    for item in body["recommendations"]:
        assert item["recommendation"] in {"buy", "sell", "hold"}
        assert item["confidence"] in {"low", "medium", "high"}
        assert item["confidence_rationale"]
        assert item["supporting_facts"]
        assert item["risks_or_caveats"]


def test_the_analysis_alias_serves_the_same_contract():
    root = get().json()
    alias = get(path="/api/recommendations/analysis").json()
    assert [item["symbol"] for item in alias["recommendations"]] == [
        item["symbol"] for item in root["recommendations"]
    ]
    assert alias["disclaimer"] == root["disclaimer"]


def test_every_supporting_fact_names_a_real_field_and_quotes_its_real_value():
    body = get().json()
    index = {
        metric["field"]: metric
        for metric in body["context"]["shared_metrics"]
        + [m for asset in body["context"]["assets"] for m in asset["metrics"]]
    }

    for item in body["recommendations"]:
        for fact in item["supporting_facts"]:
            assert fact["metric"] in index, "a fact cited a field that is not in the context"
            assert index[fact["metric"]]["status"] == "available"


# --- the disclaimer ---------------------------------------------------------


def test_the_disclaimer_is_present_and_comes_from_the_server_not_the_model():
    body = get().json()
    assert body["disclaimer"] == DISCLAIMER
    assert "not financial advice" in body["disclaimer"]


@pytest.mark.parametrize(
    "flags",
    [None, scenarios.EMPTY_PORTFOLIO, scenarios.DEGRADED_AI, scenarios.PARTIAL_DATA],
)
def test_the_disclaimer_survives_every_non_error_path(flags):
    body = get(flags).json()
    assert body["disclaimer"] == DISCLAIMER


# --- confidence -------------------------------------------------------------


def test_full_grounding_data_lets_the_models_confidence_stand():
    btc = by_symbol(get().json(), "BTC")
    assert btc["confidence_ceiling"] == "high"
    assert btc["confidence"] == btc["model_confidence"] == "high"
    assert btc["data_completeness"] == 1.0
    assert btc["categories_missing"] == []


def test_a_missing_market_source_caps_confidence_at_medium():
    btc = by_symbol(get(scenarios.ERROR_MARKET_CONTEXT).json(), "BTC")
    assert btc["model_confidence"] == "high"
    # The model still said "high"; the data does not support it.
    assert btc["confidence"] == "medium"
    assert btc["confidence_ceiling"] == "medium"
    assert set(btc["categories_missing"]) == {"sentiment", "market_structure"}


def test_thin_data_forces_every_call_down_to_low():
    body = get(scenarios.PARTIAL_DATA).json()
    for item in body["recommendations"]:
        assert item["confidence"] == "low"
        assert item["data_completeness"] < 0.5
        assert item["ceiling_reason"]


def test_the_ceiling_never_raises_a_low_self_rating():
    sol = by_symbol(get().json(), "SOL")
    assert sol["confidence_ceiling"] == "high"
    assert sol["model_confidence"] == "low"
    assert sol["confidence"] == "low"


# --- groundedness -----------------------------------------------------------


def test_a_clean_run_reports_verified_with_no_violations():
    report = get().json()["groundedness"]
    assert report["status"] == "verified"
    assert report["violations"] == []
    assert report["facts_checked"] > 0
    assert report["retried"] is False


def test_a_fabricated_value_is_corrected_retried_and_penalised():
    body = get(scenarios.UNGROUNDED_AI).json()
    report = body["groundedness"]

    assert report["status"] == "corrected"
    assert report["retried"] is True, "a failed check must trigger one retry"
    assert report["confidence_downgraded"] is True
    assert report["facts_corrected"] > 0
    assert report["facts_dropped"] > 0

    kinds = {violation["kind"] for violation in report["violations"]}
    assert "value_mismatch" in kinds
    assert "unknown_metric" in kinds


def test_a_corrected_payload_never_ships_the_fabricated_number():
    """
    The served value is always the measured one. A mismatch is recorded in
    `model_stated_value` for the audit trail, but it is not what the UI renders.
    """
    clean = {
        fact["metric"]: fact["value"]
        for item in get().json()["recommendations"]
        for fact in item["supporting_facts"]
    }

    body = get(scenarios.UNGROUNDED_AI).json()
    corrected = 0

    for item in body["recommendations"]:
        for fact in item["supporting_facts"]:
            assert fact["metric"] in clean
            # Same value the un-tampered run served, whatever the model wrote.
            assert fact["value"] == clean[fact["metric"]]
            if not fact["verified"]:
                assert fact["model_stated_value"] is not None
                assert fact["model_stated_value"] != fact["value"]
                corrected += 1

    assert corrected == len(body["recommendations"]), "expected one correction per asset"


def test_the_invented_field_is_dropped_rather_than_shown_unverified():
    body = get(scenarios.UNGROUNDED_AI).json()
    cited = {
        fact["metric"] for item in body["recommendations"] for fact in item["supporting_facts"]
    }
    assert not any(name.endswith(".exchange_netflow_7d") for name in cited)


def test_a_downgraded_call_explains_why():
    btc = by_symbol(get(scenarios.UNGROUNDED_AI).json(), "BTC")
    assert btc["confidence"] == "medium"  # high, downgraded one step

    note = btc["verification_note"]
    assert note
    # Says both halves of what happened -- the model misquoted a figure, and
    # that is why this call is rated lower -- without pinning the exact phrasing.
    assert "did not match" in note
    assert "lowered" in note


# --- failure modes ----------------------------------------------------------


def test_an_empty_portfolio_reports_that_there_is_nothing_to_analyse():
    body = get(scenarios.EMPTY_PORTFOLIO).json()
    assert body["status"] == "empty"
    assert "No cryptocurrency holdings" in body["message"]
    assert body["recommendations"] == []


def test_an_unconfigured_model_degrades_to_a_200_with_an_explanation():
    """
    The portfolio data is still good, so this is not a server error: the panel
    should say the analysis is unavailable, not disappear.
    """
    response = get(scenarios.DEGRADED_AI)
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "unavailable"
    assert "Unable to generate recommendations" in body["message"]
    assert body["recommendations"] == []


def test_an_unexpected_model_failure_is_a_500():
    assert get(scenarios.ERROR_AI).status_code == 500


def test_a_portfolio_outage_is_a_500():
    assert get(scenarios.ERROR_PORTFOLIO).status_code == 500


def test_a_candle_outage_still_produces_calls_at_reduced_confidence():
    """Missing indicators are a confidence problem, not an outage."""
    response = get(scenarios.ERROR_HISTORICAL)
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    for item in body["recommendations"]:
        assert item["confidence"] == "low"


# --- the audit log ----------------------------------------------------------


def test_each_run_appends_the_context_output_and_check_result(recommendation_log_file):
    get()
    assert recommendation_log_file.exists()

    entry = json.loads(recommendation_log_file.read_text().splitlines()[0])
    assert set(entry) >= {"grounding_context", "model_output", "groundedness", "calls"}
    assert entry["grounding_context"]["assets"][0]["symbol"] == "BTC"
    assert entry["model_output"]["recommendations"]

    call = entry["calls"][0]
    # The price at call time is what makes calibration possible later: the
    # stated confidence can then be checked against what the price did.
    assert call["price_at_call"] == pytest.approx(52341.87)
    assert call["confidence"] in {"low", "medium", "high"}
    assert call["model_confidence"] in {"low", "medium", "high"}


def test_the_log_records_a_failed_check_alongside_the_output_that_failed_it(
    recommendation_log_file,
):
    get(scenarios.UNGROUNDED_AI)
    entry = json.loads(recommendation_log_file.read_text().splitlines()[0])

    assert entry["groundedness"]["status"] == "corrected"
    assert entry["groundedness"]["violations"]


def test_repeated_runs_append_rather_than_overwrite(recommendation_log_file):
    get()
    get()
    assert len(recommendation_log_file.read_text().strip().splitlines()) == 2
