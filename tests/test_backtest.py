from decimal import Decimal

import pytest

from quant_trader.backtest import run_backtest
from quant_trader.domain import Market
from quant_trader.schemas import BacktestRequest


@pytest.mark.asyncio
async def test_backtest_is_deterministic_and_fills_after_signal_day():
    request = BacktestRequest(
        market=Market.US, symbol="DEMO", initial_cash=Decimal("100000"), fast_window=2, slow_window=3
    )
    first = await run_backtest(request)
    second = await run_backtest(request)
    assert first["final_equity"] == second["final_equity"]
    assert first["fills"]
    assert first["equity_curve"][0]["equity"] == Decimal("100000")


@pytest.mark.asyncio
async def test_backtest_rejects_missing_csv():
    with pytest.raises(ValueError, match="not found"):
        await run_backtest(BacktestRequest(csv_path="/definitely/missing.csv"))

