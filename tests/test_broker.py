from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from quant_trader.broker import PaperBroker
from quant_trader.config import Settings
from quant_trader.db import AccountModel, Base
from quant_trader.domain import Bar, Market, OrderStatus, OrderType, SecurityType, Side
from quant_trader.risk import RiskManager
from quant_trader.schemas import OrderCreate


@pytest.mark.asyncio
async def test_market_order_fills_on_next_bar_open():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    db.add(AccountModel(id="paper", cash=Decimal("10000")))
    db.commit()
    config = Settings(max_order_notional=Decimal("10000"), max_position_ratio=Decimal("1"), max_gross_exposure_ratio=Decimal("1"))
    broker = PaperBroker(db, RiskManager(config))
    request = OrderCreate(
        account_id="paper", market=Market.US, symbol="ABC", security_type=SecurityType.STOCK,
        side=Side.BUY, order_type=OrderType.MARKET, quantity=Decimal("10")
    )
    submitted = date(2024, 1, 2)
    order = await broker.submit_order(request, Decimal("100"), submitted)
    same_day = Bar(Market.US, "ABC", submitted, Decimal("101"), Decimal("102"), Decimal("99"), Decimal("100"), 10)
    assert await broker.process_bar(same_day) == []
    next_day = Bar(Market.US, "ABC", date(2024, 1, 3), Decimal("105"), Decimal("106"), Decimal("104"), Decimal("105"), 10)
    fills = await broker.process_bar(next_day)
    assert fills[0].price == 105
    assert order.status == OrderStatus.FILLED.value

