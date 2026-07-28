import pytest
from fastapi.testclient import TestClient
from app.config import SCENARIO_COOKIE
from app.main import app
from app.services.fakes import scenarios

client = TestClient(app)

def test_get_recommendations():
    response = client.get("/api/recommendations/")
    assert response.status_code == 200
    assert "recommendations" in response.json()

def test_get_analysis():
    response = client.get("/api/recommendations/analysis")
    assert response.status_code == 200
    assert "recommendations" in response.json()

def test_ai_error_scenario_returns_500():
    response = client.get(
        "/api/recommendations/",
        cookies={SCENARIO_COOKIE: scenarios.ERROR_AI},
    )
    assert response.status_code == 500

def test_empty_portfolio_scenario_reports_no_holdings():
    response = client.get(
        "/api/recommendations/",
        cookies={SCENARIO_COOKIE: scenarios.EMPTY_PORTFOLIO},
    )
    assert response.status_code == 200
    assert "No cryptocurrency holdings" in response.json()["recommendations"]
