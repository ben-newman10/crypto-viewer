import pytest
from fastapi.testclient import TestClient
from app.main import app

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