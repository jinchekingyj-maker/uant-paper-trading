from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from .broker import PaperBroker
from .config import Settings
from .db import AccountModel, Base, FillModel, OrderModel, PositionModel
from .domain import Bar, Market, SecurityType
from .portfolio import account_values, find_position
from .risk import RiskManager
from .schemas import BacktestRequest, OrderCreate
from .strategy import create_strategy


def load_bars(request: BacktestRequest) -> list[Bar]:
    path = Path(request.csv_path) if request.csv_path else Path(__file__).parent / "data" / "sample_bars.csv"
    if not path.is_file():
        raise ValueError(f"CSV file not found: {path}")
    frame = pd.read_csv(path)
    required = {"date", "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        raise ValueError(f"CSV requires columns: {sorted(required)}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame.sort_values("date")
    return [
        Bar(
            market=request.market,
            symbol=request.symbol.upper(),
            trading_date=row.date,
            open=Decimal(str(row.open)),
            high=Decimal(str(row.high)),
            low=Decimal(str(row.low)),
            close=Decimal(str(row.close)),
            volume=int(row.volume),
        )
        for row in frame.itertuples()
    ]


async def run_backtest(request: BacktestRequest, bars: list[Bar] | None = None) -> dict:
    bars = bars or load_bars(request)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    risk_settings = Settings(
        initial_cash=request.initial_cash,
        max_order_notional=request.initial_cash,
        max_position_ratio=Decimal("1"),
        max_gross_exposure_ratio=Decimal("1"),
    )
    strategy = create_strategy(request.strategy, request.fast_window, request.slow_window)
    with Session() as session:
        session.add(AccountModel(id="backtest", cash=request.initial_cash))
        session.commit()
        broker = PaperBroker(session, RiskManager(risk_settings))
        history: list[Bar] = []
        curve: list[dict] = []
        for bar in bars:
            await broker.process_bar(bar)
            history.append(bar)
            position = find_position(session, "backtest", bar.market.value, bar.symbol)
            quantity = Decimal(position.quantity) if position else Decimal("0")
            for intent in strategy.on_bar(history, quantity):
                order = OrderCreate(
                    account_id="backtest",
                    market=intent.market,
                    symbol=intent.symbol,
                    security_type=SecurityType.STOCK,
                    side=intent.side,
                    order_type=intent.order_type,
                    quantity=intent.quantity,
                    limit_price=intent.limit_price,
                )
                await broker.submit_order(order, bar.close, submitted_on=bar.trading_date)
            values = account_values(session, "backtest")
            curve.append({"date": bar.trading_date.isoformat(), "equity": values["equity"]})

        equities = pd.Series([float(point["equity"]) for point in curve])
        returns = equities.pct_change().dropna()
        total_return = Decimal(str(equities.iloc[-1] / float(request.initial_cash) - 1)) if len(equities) else Decimal("0")
        drawdown = equities / equities.cummax() - 1 if len(equities) else pd.Series(dtype=float)
        sharpe = float(returns.mean() / returns.std() * (252**0.5)) if len(returns) > 1 and returns.std() else 0.0
        fills = session.scalars(select(FillModel).order_by(FillModel.id)).all()
        orders = {o.id: o for o in session.scalars(select(OrderModel)).all()}
        return {
            "symbol": request.symbol.upper(),
            "strategy": strategy.name.value,
            "strategy_description": strategy.description,
            "initial_cash": request.initial_cash,
            "final_equity": Decimal(str(equities.iloc[-1])) if len(equities) else request.initial_cash,
            "total_return": total_return,
            "max_drawdown": Decimal(str(drawdown.min())) if len(drawdown) else Decimal("0"),
            "sharpe_ratio": sharpe,
            "equity_curve": curve,
            "fills": [
                {
                    "order_id": fill.order_id,
                    "side": orders[fill.order_id].side,
                    "price": Decimal(fill.price),
                    "quantity": Decimal(fill.quantity),
                    "filled_at": fill.filled_at,
                }
                for fill in fills
            ],
        }
