"""
Tests for candidate screening.

The screener decides what the pipeline *looks at*, which makes it the one place
a coin can be silently dropped before any grounding rule applies. So these tests
care less about which coins come out and more about two properties: that nothing
disappears without a recorded reason, and that the same universe always yields
the same shortlist.
"""

import pytest

from app.services import discovery
from app.services.discovery import Candidate, Exclusion, screen
from app.services.fakes import fixtures
from app.services.market_context_service import _universe_row

HELD = {"BTC", "ETH", "SOL"}


def universe():
    return [_universe_row(row) for row in fixtures.universe_rows()]


def tradeable():
    return set(fixtures.TRADEABLE_BASES["GBP"])


def reason_for(excluded, symbol):
    for item in excluded:
        if item.symbol == symbol:
            return item.reason
    return None


# --- accounting -------------------------------------------------------------


def test_every_coin_is_either_shortlisted_or_excluded_with_a_reason():
    """
    The screener's output has to add up. A coin that is neither recommended nor
    accounted for is one the reader can never find out about.
    """
    rows = universe()
    candidates, excluded = screen(rows, tradeable(), HELD)

    seen = {candidate.symbol for candidate in candidates} | {
        item.symbol for item in excluded
    }
    assert seen == {row.symbol for row in rows}
    assert len(candidates) + len(excluded) == len(rows)
    assert all(item.reason for item in excluded)


def test_the_shortlist_never_contains_a_coin_you_already_hold():
    candidates, excluded = screen(universe(), tradeable(), HELD)
    assert not {candidate.symbol for candidate in candidates} & HELD
    for symbol in HELD:
        assert reason_for(excluded, symbol) == "already_held"


def test_the_shortlist_is_capped():
    candidates, _ = screen(universe(), tradeable(), HELD, limit=2)
    assert len(candidates) == 2

    none_at_all, excluded = screen(universe(), tradeable(), HELD, limit=0)
    assert none_at_all == []
    assert len(excluded) == len(universe())


def test_the_same_universe_always_produces_the_same_shortlist():
    """
    The panel refetches every fifteen minutes. A screener that reshuffled on
    identical data would churn the UI and make the audit log unreadable.
    """
    first, _ = screen(universe(), tradeable(), HELD)
    second, _ = screen(universe(), tradeable(), HELD)
    assert [candidate.symbol for candidate in first] == [
        candidate.symbol for candidate in second
    ]


# --- exclusions -------------------------------------------------------------


def test_a_coin_the_exchange_will_not_trade_is_excluded():
    """Actionability is the point: a suggestion you cannot act on is noise."""
    _, excluded = screen(universe(), tradeable() - {"ADA"}, HELD)
    assert reason_for(excluded, "ADA") == "not_tradeable"


def test_stablecoins_are_excluded():
    _, excluded = screen(universe(), tradeable(), HELD)
    assert reason_for(excluded, "USDC") == "stablecoin"
    assert reason_for(excluded, "USDT") == "stablecoin"


def test_a_wrapper_around_something_you_hold_is_not_diversification():
    _, excluded = screen(universe(), tradeable() | {"WSTETH"}, HELD)
    item = next(item for item in excluded if item.symbol == "WSTETH")
    assert item.reason == "duplicate_exposure"
    assert "ETH" in item.detail


def test_a_coin_below_the_rank_floor_is_excluded_with_its_rank():
    _, excluded = screen(universe(), tradeable(), HELD)
    item = next(item for item in excluded if item.symbol == "CHZ")
    assert item.reason == "below_rank_floor"
    assert "211" in item.detail


def test_a_thinly_traded_coin_is_excluded():
    rows = universe()
    for row in rows:
        if row.symbol == "ADA":
            row.total_volume = 1_000.0
    _, excluded = screen(rows, tradeable(), HELD)
    assert reason_for(excluded, "ADA") == "thin_liquidity"


def test_an_unranked_coin_is_excluded_rather_than_assumed_large():
    rows = universe()
    for row in rows:
        if row.symbol == "ADA":
            row.market_cap_rank = None
    _, excluded = screen(rows, tradeable(), HELD)
    assert reason_for(excluded, "ADA") == "unranked"


def test_only_the_higher_ranked_claimant_of_a_ticker_is_considered():
    """
    Tickers are not unique on CoinGecko. Assessing the wrong coin under a
    familiar ticker is worse than assessing none, so the lower-ranked claimant
    is never reached.
    """
    rows = universe()
    impostor = _universe_row(
        {
            "id": "cardano-impostor",
            "symbol": "ada",
            "market_cap_rank": 240,
            "total_volume": 900_000_000.0,
            "ath_change_percentage": -10.0,
        }
    )
    candidates, _ = screen(rows + [impostor], tradeable(), HELD)
    ada = [candidate for candidate in candidates if candidate.symbol == "ADA"]
    assert len(ada) <= 1
    if ada:
        assert ada[0].gecko_id == "cardano"


# --- stratification ---------------------------------------------------------


def test_the_shortlist_spans_more_than_one_angle():
    """
    One reason filling every slot would mean a single week's momentum decided
    the whole list. The strata exist to stop that.
    """
    candidates, _ = screen(universe(), tradeable(), HELD)
    assert len(candidates) > 1
    assert len({candidate.reason for candidate in candidates}) > 1


def test_every_candidate_reports_a_reason_with_a_reader_facing_label():
    candidates, excluded = screen(universe(), tradeable(), HELD)

    for candidate in candidates:
        assert candidate.reason in discovery.SCREEN_REASON_LABELS
        assert discovery.screen_reason_label(candidate.reason)

    for item in excluded:
        assert item.reason in discovery.EXCLUSION_REASON_LABELS
        assert discovery.exclusion_reason_label(item.reason)


def test_a_label_is_never_the_bare_machine_value():
    """
    These strings are shown to a reader who has never traded. "thin_liquidity"
    on a card would be a leaked internal name.
    """
    for reason, label in discovery.EXCLUSION_REASON_LABELS.items():
        assert label != reason
        assert "_" not in label
    for reason, label in discovery.SCREEN_REASON_LABELS.items():
        assert label != reason
        assert "_" not in label


# --- degradation ------------------------------------------------------------


def test_an_empty_universe_yields_no_candidates_and_no_crash():
    candidates, excluded = screen([], tradeable(), HELD)
    assert candidates == []
    assert excluded == []


def test_no_tradeable_pairs_yields_no_candidates():
    """
    What happens when the product listing is unreachable: everything is
    unbuyable as far as we can tell, so nothing is suggested.
    """
    candidates, excluded = screen(universe(), set(), HELD)
    assert candidates == []
    assert excluded
    assert reason_for(excluded, "ADA") == "not_tradeable"


def test_holding_nothing_still_produces_candidates():
    """The empty-portfolio case is the one this feature helps most."""
    candidates, _ = screen(universe(), tradeable(), set())
    assert candidates
    assert "BTC" in {candidate.symbol for candidate in candidates}


@pytest.mark.parametrize("symbol", ["BTC", "ETH", "SOL", "DOGE", "ADA", "LINK"])
def test_a_real_coin_is_never_mistaken_for_a_stablecoin(symbol):
    """
    Guards the rule this module deliberately does *not* use. Detecting a
    stablecoin by "its price barely moved" classifies BTC as pegged on a quiet
    week -- the fixture BTC row is exactly such a week (-0.5/-0.8/-0.4).
    """
    assert symbol not in discovery.STABLECOINS

    _, excluded = screen(universe(), tradeable(), set())
    assert reason_for(excluded, symbol) != "stablecoin"


# --- typing -----------------------------------------------------------------


def test_the_models_reject_an_unknown_reason():
    """The vocabularies are closed, so the UI's label maps can be exhaustive."""
    with pytest.raises(Exception):
        Candidate(symbol="ADA", gecko_id="cardano", market_cap_rank=17, reason="vibes")
    with pytest.raises(Exception):
        Exclusion(symbol="ADA", reason="did_not_fancy_it")
