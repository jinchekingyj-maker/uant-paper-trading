from contextlib import asynccontextmanager
from decimal import Decimal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .backtest import run_backtest
from .broker import PaperBroker
from .config import settings
from .db import LatestPriceModel, OrderModel, PositionModel, get_session, init_db
from .domain import Bar
from .portfolio import account_values
from .market_data import fetch_daily_bars
from .risk import RiskManager
from .schemas import (
    AccountRead,
    BacktestRequest,
    BarCreate,
    OrderCreate,
    OrderRead,
    PositionRead,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Quant Paper Trading API", version="0.1.0", lifespan=lifespan)


@app.get("/", include_in_schema=False)
def dashboard():
    from pathlib import Path

    return FileResponse(Path(__file__).parent / "static" / "index.html")


def broker(session: Session) -> PaperBroker:
    return PaperBroker(session, RiskManager(settings))


@app.get("/health")
def health():
    return {"status": "ok", "mode": "paper"}


@app.get("/account", response_model=AccountRead)
def get_account(account_id: str = Query(default=settings.default_account_id), session: Session = Depends(get_session)):
    try:
        values = account_values(session, account_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"id": account_id, **values}


@app.get("/positions", response_model=list[PositionRead])
def get_positions(account_id: str = Query(default=settings.default_account_id), session: Session = Depends(get_session)):
    positions = session.scalars(select(PositionModel).where(PositionModel.account_id == account_id)).all()
    return [
        {
            "market": p.market,
            "symbol": p.symbol,
            "security_type": p.security_type,
            "quantity": p.quantity,
            "average_cost": p.average_cost,
            "last_price": p.last_price,
            "market_value": Decimal(p.quantity) * Decimal(p.last_price),
            "unrealized_pnl": Decimal(p.quantity) * (Decimal(p.last_price) - Decimal(p.average_cost)),
        }
        for p in positions
    ]


@app.get("/orders", response_model=list[OrderRead])
def list_orders(account_id: str = Query(default=settings.default_account_id), session: Session = Depends(get_session)):
    return session.scalars(
        select(OrderModel).where(OrderModel.account_id == account_id).order_by(OrderModel.submitted_at.desc())
    ).all()


@app.get("/orders/{order_id}", response_model=OrderRead)
async def get_order(order_id: str, session: Session = Depends(get_session)):
    try:
        return await broker(session).get_order(order_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/orders", response_model=OrderRead, status_code=201)
async def create_order(request: OrderCreate, session: Session = Depends(get_session)):
    latest = session.get(LatestPriceModel, f"{request.market.value}:{request.symbol.upper()}")
    reference_price = request.limit_price
    if reference_price is None:
        if latest is None:
            raise HTTPException(422, "market order requires a known price; inject a bar or use a limit order")
        reference_price = Decimal(latest.price)
    return await broker(session).submit_order(
        request,
        reference_price,
        submitted_on=latest.trading_date if latest is not None else None,
    )


@app.post("/orders/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(order_id: str, session: Session = Depends(get_session)):
    try:
        return await broker(session).cancel_order(order_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/market-data/bars")
async def ingest_bar(request: BarCreate, session: Session = Depends(get_session)):
    bar = Bar(**request.model_dump())
    fills = await broker(session).process_bar(bar)
    return {"accepted": True, "fills": len(fills)}


@app.post("/backtests")
async def backtest(request: BacktestRequest):
    try:
        if request.csv_path:
            return await run_backtest(request)
        bars = await fetch_daily_bars(
            request.symbol, request.market, request.start_date, request.end_date
        )
        return await run_backtest(request, bars)
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(422, str(exc)) from exc
