from decimal import Decimal


def bar(day, close=100):
    return {
        "market": "US",
        "symbol": "ABC",
        "trading_date": day,
        "open": close,
        "high": close + 2,
        "low": close - 2,
        "close": close,
        "volume": 1000,
    }


def test_health_and_paper_trade_flow(client):
    assert client.get("/health").json() == {"status": "ok", "mode": "paper"}
    assert client.post("/market-data/bars", json=bar("2024-01-02")).status_code == 200
    response = client.post(
        "/orders",
        json={
            "account_id": "paper",
            "market": "US",
            "symbol": "ABC",
            "security_type": "STOCK",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "10",
        },
    )
    assert response.status_code == 201
    order_id = response.json()["id"]
    assert response.json()["status"] == "PENDING"
    assert client.post("/market-data/bars", json=bar("2024-01-03", 105)).json()["fills"] == 1
    assert client.get(f"/orders/{order_id}").json()["status"] == "FILLED"
    assert client.get("/positions").json()[0]["quantity"] == "10.000000"
    assert Decimal(client.get("/account").json()["equity"]) == Decimal("100000")


def test_cancel_and_validation(client):
    response = client.post(
        "/orders",
        json={
            "market": "US",
            "symbol": "ABC",
            "side": "BUY",
            "order_type": "LIMIT",
            "quantity": "1",
            "limit_price": "90",
        },
    )
    order_id = response.json()["id"]
    assert client.post(f"/orders/{order_id}/cancel").json()["status"] == "CANCELLED"
    assert client.post("/orders", json={"market": "US"}).status_code == 422


def test_backtest_endpoint(client, monkeypatch):
    from quant_trader.backtest import load_bars
    from quant_trader.schemas import BacktestRequest

    async def sample_bars(symbol, market, start_date=None, end_date=None):
        return load_bars(BacktestRequest(symbol=symbol, market=market, fast_window=2, slow_window=3))

    monkeypatch.setattr("quant_trader.api.fetch_daily_bars", sample_bars)
    response = client.post(
        "/backtests",
        json={"market": "US", "symbol": "DEMO", "fast_window": 2, "slow_window": 3},
    )
    assert response.status_code == 200
    assert response.json()["fills"]
