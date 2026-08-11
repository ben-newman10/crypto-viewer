"""
Tests for the real MarketContextService.

The rest of the suite runs against the fake, which by construction cannot catch
a bug in how the live CoinGecko response is read. These drive the real service
with stubbed HTTP so the parsing, the id resolution and -- most importantly --
the degradation are covered without an outbound request.

The governing rule for this module is that nothing here is load-bearing: every
failure has to become "unavailable", never an exception. A raised error would
take down a recommendation that the portfolio data alone could have answered.
"""

from typing import Any, Dict, List

import pytest

from app.services import market_context_service as market_module
from app.services.market_context_service import MarketContextService

# Trimmed from a live /coins/markets?vs_currency=gbp&order=market_cap_desc page.
# SNX is here on purpose: its CoinGecko id is "havven", which no amount of
# guessing from the ticker would produce.
UNIVERSE_PAYLOAD: List[Dict[str, Any]] = [
    {
        "id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "market_cap_rank": 1,
        "market_cap": 1_031_400_000_000.0, "total_volume": 21_000_000_000.0,
        "price_change_percentage_24h_in_currency": -0.5,
        "price_change_percentage_7d_in_currency": -0.8,
        "price_change_percentage_30d_in_currency": -0.4,
        "ath_change_percentage": -49.7, "circulating_supply": 19_712_000.0,
    },
    {
        "id": "bitcoin-cash", "symbol": "bch", "name": "Bitcoin Cash",
        "market_cap_rank": 22, "market_cap": 11_800_000_000.0,
        "total_volume": 400_000_000.0,
        "price_change_percentage_24h_in_currency": 0.5,
        "price_change_percentage_7d_in_currency": 0.2,
        "price_change_percentage_30d_in_currency": -12.4,
        "ath_change_percentage": -94.4, "circulating_supply": 19_800_000.0,
    },
    {
        "id": "havven", "symbol": "snx", "name": "Synthetix Network",
        "market_cap_rank": 228, "market_cap": 300_000_000.0,
        "total_volume": 8_000_000.0,
        "price_change_percentage_24h_in_currency": -2.8,
        "price_change_percentage_7d_in_currency": -3.8,
        "price_change_percentage_30d_in_currency": -14.8,
        "ath_change_percentage": -99.3, "circulating_supply": 340_000_000.0,
    },
]


class StubHttpResponse:
    def __init__(self, payload: Any, ok: bool = True) -> None:
        self._payload = payload
        self._ok = ok

    def raise_for_status(self) -> None:
        if not self._ok:
            raise RuntimeError("simulated upstream failure")

    def json(self) -> Any:
        return self._payload


@pytest.fixture
def stub_http(monkeypatch):
    """Point httpx at a canned response and record the calls made."""

    def _install(payload: Any = None, ok: bool = True, error: Exception = None):
        calls: List[Dict[str, Any]] = []

        class StubAsyncClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info: Any) -> bool:
                return False

            async def get(self, url: str, params: Any = None) -> StubHttpResponse:
                calls.append({"url": url, "params": params or {}})
                if error is not None:
                    raise error
                return StubHttpResponse(payload, ok)

        monkeypatch.setattr(market_module.httpx, "AsyncClient", StubAsyncClient)
        return calls

    return _install


# --- reading the ranked page ------------------------------------------------


async def test_the_ranked_page_is_read_into_rows(stub_http):
    stub_http(UNIVERSE_PAYLOAD)
    rows = await MarketContextService().get_ranked_universe("GBP")

    assert [row.symbol for row in rows] == ["BTC", "BCH", "SNX"]

    btc = rows[0]
    assert btc.gecko_id == "bitcoin"
    assert btc.market_cap_rank == 1
    assert btc.change_7d_pct == -0.8
    assert btc.ath_change_pct == -49.7


async def test_the_request_asks_for_the_quote_currency_and_every_horizon(stub_http):
    calls = stub_http(UNIVERSE_PAYLOAD)
    await MarketContextService().get_ranked_universe("GBP", limit=42)

    params = calls[0]["params"]
    assert params["vs_currency"] == "gbp"
    assert params["order"] == "market_cap_desc"
    assert params["per_page"] == "42"
    # The screener reads all three; a missing horizon silently costs a stratum.
    assert params["price_change_percentage"] == "24h,7d,30d"


async def test_percentages_come_from_the_in_currency_fields(stub_http):
    """
    The bare `price_change_percentage_24h` is USD-denominated whatever
    `vs_currency` says. Reading it would quietly mix currencies.
    """
    stub_http(
        [
            {
                "id": "bitcoin", "symbol": "btc", "market_cap_rank": 1,
                "price_change_percentage_24h": 99.0,
                "price_change_percentage_24h_in_currency": -0.5,
            }
        ]
    )
    rows = await MarketContextService().get_ranked_universe("GBP")
    assert rows[0].change_24h_pct == -0.5


async def test_a_row_missing_fields_still_parses(stub_http):
    stub_http([{"id": "mystery", "symbol": "mys"}])
    rows = await MarketContextService().get_ranked_universe("GBP")

    assert rows[0].symbol == "MYS"
    assert rows[0].market_cap_rank is None
    assert rows[0].ath_change_pct is None


async def test_the_universe_is_cached(stub_http):
    calls = stub_http(UNIVERSE_PAYLOAD)
    service = MarketContextService()

    await service.get_ranked_universe("GBP")
    await service.get_ranked_universe("GBP")

    assert len(calls) == 1


# --- degradation ------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"error": RuntimeError("connection reset")},
        {"payload": UNIVERSE_PAYLOAD, "ok": False},
        {"payload": {"status": {"error_code": 429}}},
        {"payload": None},
    ],
    ids=["network", "http-error", "rate-limited", "null-body"],
)
async def test_every_universe_failure_degrades_to_empty(stub_http, kwargs):
    stub_http(**kwargs)
    assert await MarketContextService().get_ranked_universe("GBP") == []


async def test_a_disabled_service_makes_no_request(stub_http):
    calls = stub_http(UNIVERSE_PAYLOAD)
    service = MarketContextService(enabled=False)

    assert await service.get_ranked_universe("GBP") == []
    assert calls == []


# --- resolving tickers to ids -----------------------------------------------


async def test_the_curated_map_wins_over_the_universe(stub_http):
    """
    A hand-checked id cannot be wrong; a ticker match can. Where both have an
    answer the curated one is used.
    """
    stub_http([{"id": "not-bitcoin-at-all", "symbol": "btc", "market_cap_rank": 1}])
    resolved = await MarketContextService().resolve_ids(["BTC"])

    assert resolved["BTC"] == "bitcoin"


async def test_a_symbol_outside_the_curated_map_resolves_from_the_universe(stub_http):
    """
    The gap this closes: BCH and SNX are absent from the curated map, so before
    dynamic resolution a holding in either reported market cap as unavailable.
    """
    stub_http(UNIVERSE_PAYLOAD)
    resolved = await MarketContextService().resolve_ids(["BCH", "SNX"])

    assert resolved["BCH"] == "bitcoin-cash"
    # Nothing about the ticker suggests this id.
    assert resolved["SNX"] == "havven"


async def test_an_ambiguous_ticker_resolves_to_nothing(stub_http):
    """
    Two coins claiming one ticker is the case the curated map's comment warns
    about: picking either could return a different asset's market cap.
    """
    stub_http(
        [
            {"id": "real-thing", "symbol": "dup", "market_cap_rank": 30},
            {"id": "impostor", "symbol": "dup", "market_cap_rank": 240},
        ]
    )
    assert "DUP" not in await MarketContextService().resolve_ids(["DUP"])


async def test_an_unknown_symbol_is_absent_rather_than_guessed(stub_http):
    stub_http(UNIVERSE_PAYLOAD)
    assert await MarketContextService().resolve_ids(["NOPE"]) == {}


async def test_resolution_needs_no_request_when_the_curated_map_covers_it(stub_http):
    calls = stub_http(UNIVERSE_PAYLOAD)
    resolved = await MarketContextService().resolve_ids(["BTC", "ETH"])

    assert resolved == {"BTC": "bitcoin", "ETH": "ethereum"}
    assert calls == [], "the curated map should short-circuit the lookup"


async def test_stats_still_work_when_the_universe_is_unreachable(stub_http):
    """
    Resolution falling back must not take the curated symbols down with it.
    """
    stub_http(error=RuntimeError("connection reset"))
    assert await MarketContextService().resolve_ids(["BTC", "BCH"]) == {"BTC": "bitcoin"}
