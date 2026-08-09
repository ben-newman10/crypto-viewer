"""
Tests for the real CoinbaseService portfolio path.

The rest of the suite exercises the fake client, which by construction cannot
catch bugs in the real service's response handling. These tests drive
``CoinbaseService`` itself with stubbed SDK responses recorded from the live
Coinbase API, so the aggregation, fallback and retry logic is covered without
credentials or outbound requests.

Regression under test: a wholly staked holding (ETH) is absent from the
``/accounts`` endpoint -- it reports ``available_balance`` and ``hold`` of zero --
and surfaces only via ``get_portfolio_breakdown``'s ``spot_positions``.
"""

from typing import Any, Dict, List

import pytest
from requests.exceptions import HTTPError

from app.services import coinbase_service as coinbase_service_module
from app.services.coinbase_service import CoinbaseService


# ---------------------------------------------------------------------------
# Recorded payloads
# ---------------------------------------------------------------------------

PORTFOLIO_UUID = "9067e772-4738-537d-a37f-c570b3ee585e"
SECOND_UUID = "1111e772-4738-537d-a37f-c570b3ee5111"

# Trimmed from a live get_portfolio_breakdown response. ETH is entirely staked:
# note account_type and available_to_trade_crypto == 0.
ETH_STAKED_POSITION: Dict[str, Any] = {
    "asset": "ETH",
    "total_balance_fiat": 321.3379,
    "total_balance_crypto": 0.22541407,
    "available_to_trade_crypto": 0,
    "available_to_trade_fiat": 0,
    "is_cash": False,
    "account_type": "ACCOUNT_TYPE_STAKED_FUNDS",
}

BTC_POSITION: Dict[str, Any] = {
    "asset": "BTC",
    "total_balance_fiat": 15.625247,
    "total_balance_crypto": 0.00032322,
    "available_to_trade_crypto": 0.00032322,
    "available_to_trade_fiat": 15.625247,
    "is_cash": False,
}

# Zero-value cash positions the real account returns; these must not be listed.
GBP_CASH_POSITION: Dict[str, Any] = {
    "asset": "GBP",
    "total_balance_fiat": 0,
    "total_balance_crypto": 0,
    "available_to_trade_crypto": 0,
    "is_cash": True,
}

EUR_CASH_POSITION: Dict[str, Any] = {
    "asset": "EUR",
    "total_balance_fiat": 0,
    "total_balance_crypto": 0,
    "available_to_trade_crypto": 0,
    "is_cash": True,
}

LIVE_POSITIONS: List[Dict[str, Any]] = [
    GBP_CASH_POSITION,
    ETH_STAKED_POSITION,
    BTC_POSITION,
    EUR_CASH_POSITION,
]

# The /accounts view of the same account: ETH reads zero on both fields, which is
# precisely why the old implementation dropped it.
LIVE_ACCOUNTS: Dict[str, Any] = {
    "accounts": [
        {
            "name": "ETH Wallet",
            "type": "ACCOUNT_TYPE_CRYPTO",
            "ready": True,
            "available_balance": {"currency": "ETH", "value": "0"},
            "hold": {"currency": "ETH", "value": "0"},
        },
        {
            "name": "ETH2 Wallet",
            "type": "ACCOUNT_TYPE_CRYPTO",
            "ready": False,
            "available_balance": {"currency": "ETH2", "value": "0"},
            "hold": {"currency": "ETH2", "value": "0"},
        },
        {
            "name": "BTC Wallet",
            "type": "ACCOUNT_TYPE_CRYPTO",
            "ready": True,
            "available_balance": {"currency": "BTC", "value": "0.00032322"},
            "hold": {"currency": "BTC", "value": "0"},
        },
        {
            "name": "GBP Wallet",
            "type": "ACCOUNT_TYPE_FIAT",
            "ready": True,
            "available_balance": {"currency": "GBP", "value": "0"},
            "hold": {"currency": "GBP", "value": "0"},
        },
    ]
}


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class StubResponse:
    """Mimics the SDK response objects, which expose ``to_dict()``."""

    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def to_dict(self) -> Dict[str, Any]:
        return self._payload


def http_error(status_code: int) -> HTTPError:
    """Build an HTTPError carrying a status code, as the SDK raises."""

    class _Response:
        pass

    response = _Response()
    response.status_code = status_code
    error = HTTPError(f"{status_code} Server Error")
    error.response = response
    return error


class StubClient:
    """
    Stand-in for coinbase.rest.RESTClient.

    ``breakdowns`` maps portfolio uuid -> payload or exception. A list value is
    consumed one entry per call, which lets a test model "fails once, then
    succeeds". Exceptions are raised rather than returned.
    """

    def __init__(self, portfolios=None, breakdowns=None, accounts=None):
        self._portfolios = portfolios
        self._breakdowns = breakdowns or {}
        self._accounts = accounts
        self.breakdown_calls: List[str] = []
        self.accounts_calls = 0

    def get_portfolios(self, *args, **kwargs):
        if isinstance(self._portfolios, Exception):
            raise self._portfolios
        return StubResponse(self._portfolios)

    def get_portfolio_breakdown(self, portfolio_uuid: str, **kwargs):
        self.breakdown_calls.append(portfolio_uuid)
        outcome = self._breakdowns.get(portfolio_uuid)
        if isinstance(outcome, list):
            outcome = outcome.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is None:
            raise AssertionError(f"unexpected breakdown request for {portfolio_uuid}")
        return StubResponse(outcome)

    def get_accounts(self, *args, **kwargs):
        self.accounts_calls += 1
        if isinstance(self._accounts, Exception):
            raise self._accounts
        if self._accounts is None:
            raise AssertionError("unexpected get_accounts call")
        return StubResponse(self._accounts)


def portfolios_payload(*uuids: str) -> Dict[str, Any]:
    return {
        "portfolios": [
            {"name": "Default", "uuid": uuid, "type": "DEFAULT", "deleted": False}
            for uuid in uuids
        ]
    }


def breakdown_payload(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"breakdown": {"spot_positions": positions}}


@pytest.fixture
def make_service(monkeypatch):
    """
    Build a real CoinbaseService wired to a stub client.

    RESTClient is replaced before construction so no key parsing or network
    setup happens, and the retry backoff is zeroed to keep the suite fast.
    """
    monkeypatch.setenv("COINBASE_API_KEY", "test-key")
    monkeypatch.setenv("COINBASE_API_SECRET", "test-secret")
    monkeypatch.setattr(coinbase_service_module, "RESTClient", lambda **kwargs: object())

    def _make(client: StubClient) -> CoinbaseService:
        service = CoinbaseService()
        service.client = client
        service.RETRY_BASE_DELAY = 0
        return service

    return _make


def by_currency(portfolio: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    return {holding["currency"]: holding for holding in portfolio}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_staked_eth_is_included(make_service):
    """The regression: fully staked ETH must appear at its full balance."""
    service = make_service(
        StubClient(
            portfolios=portfolios_payload(PORTFOLIO_UUID),
            breakdowns={PORTFOLIO_UUID: breakdown_payload(LIVE_POSITIONS)},
        )
    )

    holdings = by_currency(await service.get_portfolio())

    assert "ETH" in holdings, "staked ETH must not be dropped"
    assert holdings["ETH"]["balance"] == "0.22541407"
    # Staked funds cannot be traded, so available is legitimately zero.
    assert float(holdings["ETH"]["available"]) == 0


async def test_zero_value_positions_are_excluded(make_service):
    """Zero cash balances and the empty ETH2 remnant stay hidden."""
    service = make_service(
        StubClient(
            portfolios=portfolios_payload(PORTFOLIO_UUID),
            breakdowns={PORTFOLIO_UUID: breakdown_payload(LIVE_POSITIONS)},
        )
    )

    holdings = by_currency(await service.get_portfolio())

    assert set(holdings) == {"ETH", "BTC"}


async def test_small_balance_has_no_float_artefacts(make_service):
    """Formatting must not turn 0.00032322 into 0.0003232200000001."""
    service = make_service(
        StubClient(
            portfolios=portfolios_payload(PORTFOLIO_UUID),
            breakdowns={PORTFOLIO_UUID: breakdown_payload(LIVE_POSITIONS)},
        )
    )

    holdings = by_currency(await service.get_portfolio())

    assert holdings["BTC"]["balance"] == "0.00032322"
    assert holdings["BTC"]["available"] == "0.00032322"


async def test_multiple_portfolios_are_aggregated(make_service):
    service = make_service(
        StubClient(
            portfolios=portfolios_payload(PORTFOLIO_UUID, SECOND_UUID),
            breakdowns={
                PORTFOLIO_UUID: breakdown_payload([BTC_POSITION]),
                SECOND_UUID: breakdown_payload([ETH_STAKED_POSITION]),
            },
        )
    )

    holdings = by_currency(await service.get_portfolio())

    assert set(holdings) == {"BTC", "ETH"}


async def test_one_failing_portfolio_does_not_lose_the_others(make_service):
    service = make_service(
        StubClient(
            portfolios=portfolios_payload(PORTFOLIO_UUID, SECOND_UUID),
            breakdowns={
                PORTFOLIO_UUID: breakdown_payload([ETH_STAKED_POSITION]),
                SECOND_UUID: http_error(403),
            },
        )
    )

    holdings = by_currency(await service.get_portfolio())

    assert "ETH" in holdings


async def test_transient_502_is_retried(make_service):
    """A 502 was observed from this endpoint in practice; retry must recover."""
    client = StubClient(
        portfolios=portfolios_payload(PORTFOLIO_UUID),
        breakdowns={
            PORTFOLIO_UUID: [
                http_error(502),
                breakdown_payload(LIVE_POSITIONS),
            ]
        },
    )
    service = make_service(client)

    holdings = by_currency(await service.get_portfolio())

    assert "ETH" in holdings
    assert len(client.breakdown_calls) == 2


async def test_auth_failure_is_not_retried(make_service):
    """Retrying a rejected credential only multiplies the latency."""
    client = StubClient(
        portfolios=portfolios_payload(PORTFOLIO_UUID),
        breakdowns={PORTFOLIO_UUID: http_error(401)},
        accounts=LIVE_ACCOUNTS,
    )
    service = make_service(client)

    await service.get_portfolio()

    assert len(client.breakdown_calls) == 1


async def test_falls_back_to_accounts_when_breakdown_unavailable(make_service):
    """If the breakdown path fails outright, the old endpoint still answers."""
    client = StubClient(
        portfolios=http_error(500),
        accounts=LIVE_ACCOUNTS,
    )
    service = make_service(client)

    holdings = by_currency(await service.get_portfolio())

    assert client.accounts_calls >= 1
    # /accounts cannot see staked funds, so ETH is absent here -- that is the
    # documented limitation of the fallback, not a regression.
    assert holdings["BTC"]["balance"] == "0.00032322"
    assert "ETH" not in holdings


async def test_accounts_fallback_counts_held_funds(make_service):
    """The fallback must sum hold into balance rather than discarding it."""
    accounts = {
        "accounts": [
            {
                "name": "SOL Wallet",
                "type": "ACCOUNT_TYPE_CRYPTO",
                "ready": True,
                "available_balance": {"currency": "SOL", "value": "1.5"},
                "hold": {"currency": "SOL", "value": "2.5"},
            }
        ]
    }
    service = make_service(StubClient(portfolios=http_error(500), accounts=accounts))

    holdings = by_currency(await service.get_portfolio())

    assert float(holdings["SOL"]["balance"]) == 4.0
    assert float(holdings["SOL"]["available"]) == 1.5


async def test_total_failure_raises(make_service):
    """A credential or network failure must not masquerade as an empty portfolio."""
    service = make_service(
        StubClient(portfolios=http_error(500), accounts=http_error(500))
    )

    with pytest.raises(Exception):
        await service.get_portfolio()


async def test_empty_breakdown_returns_empty_without_fallback(make_service):
    """A genuinely empty portfolio is a success, not a reason to fall back."""
    client = StubClient(
        portfolios=portfolios_payload(PORTFOLIO_UUID),
        breakdowns={PORTFOLIO_UUID: breakdown_payload([])},
        accounts=None,  # any get_accounts call raises AssertionError
    )
    service = make_service(client)

    assert await service.get_portfolio() == []
    assert client.accounts_calls == 0


async def test_wallet_and_staked_positions_for_one_asset_are_summed(make_service):
    """A partially staked asset arrives as two positions for the same symbol."""
    wallet_eth = {
        "asset": "ETH",
        "total_balance_crypto": 1.5,
        "available_to_trade_crypto": 1.5,
        "is_cash": False,
    }
    service = make_service(
        StubClient(
            portfolios=portfolios_payload(PORTFOLIO_UUID),
            breakdowns={
                PORTFOLIO_UUID: breakdown_payload([wallet_eth, ETH_STAKED_POSITION])
            },
        )
    )

    holdings = by_currency(await service.get_portfolio())

    assert len(holdings) == 1
    assert float(holdings["ETH"]["balance"]) == pytest.approx(1.72541407)
    assert float(holdings["ETH"]["available"]) == pytest.approx(1.5)
