import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_recommendations():
    response = client.get("/api/recommendations/")
    assert response.status_code == 200
    assert "recommendations" in response.json()

def test_get_analysis():
    response = client.get("/api/recommendations/analysis")
    assert response.status_code == 200
    assert "recommendations" in response.json()