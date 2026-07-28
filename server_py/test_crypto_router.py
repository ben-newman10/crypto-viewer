import pytest
from fastapi.testclient import TestClient
from app.config import SCENARIO_COOKIE
from app.main import app
from app.services.fakes import scenarios

client = TestClient(app)

def test_get_portfolio():
    response = client.get("/api/crypto/portfolio")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_price():
    response = client.get("/api/crypto/price/BTC-GBP")
    assert response.status_code == 200
    assert "price" in response.json()

def test_get_historical():
    response = client.get("/api/crypto/historical/BTC-GBP")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_root_reports_test_mode():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["test_mode"] is True

def test_portfolio_error_scenario_returns_500():
    response = client.get(
        "/api/crypto/portfolio",
        cookies={SCENARIO_COOKIE: scenarios.ERROR_PORTFOLIO},
    )
    assert response.status_code == 500

def test_empty_portfolio_scenario_returns_empty_list():
    response = client.get(
        "/api/crypto/portfolio",
        cookies={SCENARIO_COOKIE: scenarios.EMPTY_PORTFOLIO},
    )
    assert response.status_code == 200
    assert response.json() == []

def test_price_error_scenario_returns_error_payload():
    response = client.get(
        "/api/crypto/price/BTC-GBP",
        cookies={SCENARIO_COOKIE: scenarios.ERROR_PRICES},
    )
    assert response.status_code == 200
    assert "error" in response.json()

def test_historical_error_scenario_returns_500():
    response = client.get(
        "/api/crypto/historical/BTC-GBP",
        cookies={SCENARIO_COOKIE: scenarios.ERROR_HISTORICAL},
    )
    assert response.status_code == 500
