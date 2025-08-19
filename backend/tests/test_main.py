import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

# Test for /api/user/balance endpoint
def test_get_user_balance():
    response = client.get("/api/user/balance", headers={"Authorization": "Bearer bipay_token_user_123"})
    assert response.status_code == 200
    assert "balance" in response.json()

# Test for /api/user/transactions endpoint
def test_get_user_transactions():
    response = client.get("/api/user/transactions?page=1&limit=10", headers={"Authorization": "Bearer bipay_token_user_123"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)

# Test for /api/payments/authorize endpoint
def test_authorize_payment():
    payload = {
        "amount": 100.0,
        "recipientId": "user_456",
        "biometricToken": "simulated_token"
    }
    response = client.post("/api/payments/authorize", json=payload, headers={"Authorization": "Bearer bipay_token_user_123"})
    assert response.status_code == 200
    assert response.json()["success"] is True

# Test for /api/merchant/summary endpoint
def test_get_merchant_summary():
    response = client.get("/api/merchant/summary")
    assert response.status_code == 200
    assert "totalDailySales" in response.json()
    assert "totalTransactions" in response.json()

# Test for /api/merchant/transactions endpoint
def test_get_merchant_transactions():
    response = client.get("/api/merchant/transactions?page=1&limit=10")
    assert response.status_code == 200
    assert "data" in response.json()
    assert "pagination" in response.json()

# Test for /api/merchant/analytics/sales-over-time endpoint
def test_get_sales_over_time():
    response = client.get("/api/merchant/analytics/sales-over-time?period=weekly")
    assert response.status_code == 200
    assert "labels" in response.json()
    assert "data" in response.json()
