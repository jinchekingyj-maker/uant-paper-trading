from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from quant_trader.config import Settings
from quant_trader.db import AccountModel, Base, PositionModel
from quant_trader.domain import Market, SecurityType, Side
from quant_trader.portfolio import apply_fill
from quant_trader.risk import RiskManager
from quant_trader.schemas import OrderCreate


def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def order(side, quantity):
    return SimpleNamespace(
        account_id="paper", market="US", symbol="ABC", security_type="STOCK", side=side.value, quantity=Decimal(quantity)
    )


def test_weighted_average_cost_and_realized_pnl():
    db = session()
    db.add(AccountModel(id="paper", cash=Decimal("10000")))
    db.commit()
    apply_fill(db, order(Side.BUY, "10"), Decimal("100"))
    apply_fill(db, order(Side.BUY, "10"), Decimal("120"))
    position = db.query(PositionModel).one()
    assert position.quantity == 20
    assert position.average_cost == 110
    apply_fill(db, order(Side.SELL, "5"), Decimal("130"))
    account = db.get(AccountModel, "paper")
    assert account.realized_pnl == 100
    assert position.quantity == 15


def test_risk_rejects_oversized_and_short_orders():
    db = session()
    db.add(AccountModel(id="paper", cash=Decimal("10000")))
    db.commit()
    manager = RiskManager(
        Settings(max_order_notional=Decimal("1000"), max_position_ratio=Decimal("1"), max_gross_exposure_ratio=Decimal("1"))
    )
    buy = OrderCreate(
        account_id="paper", market=Market.US, symbol="ABC", security_type=SecurityType.STOCK,
        side=Side.BUY, quantity=Decimal("20")
    )
    assert not manager.check(db, buy, Decimal("100")).accepted
    sell = buy.model_copy(update={"side": Side.SELL, "quantity": Decimal("1")})
    assert manager.check(db, sell, Decimal("100")).reason == "short selling is not allowed"

