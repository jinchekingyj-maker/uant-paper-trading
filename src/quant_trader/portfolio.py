from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import AccountModel, PositionModel
from .domain import Side


def find_position(session: Session, account_id: str, market: str, symbol: str) -> PositionModel | None:
    return session.scalar(
        select(PositionModel).where(
            PositionModel.account_id == account_id,
            PositionModel.market == market,
            PositionModel.symbol == symbol,
        )
    )


def apply_fill(session: Session, order, price: Decimal) -> None:
    account = session.get(AccountModel, order.account_id)
    position = find_position(session, order.account_id, order.market, order.symbol)
    quantity = Decimal(order.quantity)
    price = Decimal(price)
    if order.side == Side.BUY.value:
        old_quantity = Decimal(position.quantity) if position else Decimal("0")
        old_cost = Decimal(position.average_cost) if position else Decimal("0")
        new_quantity = old_quantity + quantity
        average_cost = (old_quantity * old_cost + quantity * price) / new_quantity
        if position is None:
            position = PositionModel(
                account_id=order.account_id,
                market=order.market,
                symbol=order.symbol,
                security_type=order.security_type,
                quantity=new_quantity,
                average_cost=average_cost,
                last_price=price,
            )
            session.add(position)
        else:
            position.quantity = new_quantity
            position.average_cost = average_cost
            position.last_price = price
        account.cash = Decimal(account.cash) - quantity * price
    else:
        if position is None or Decimal(position.quantity) < quantity:
            raise ValueError("insufficient position")
        account.cash = Decimal(account.cash) + quantity * price
        account.realized_pnl = Decimal(account.realized_pnl) + quantity * (price - Decimal(position.average_cost))
        position.quantity = Decimal(position.quantity) - quantity
        position.last_price = price
        if position.quantity == 0:
            session.delete(position)


def mark_to_market(session: Session, market: str, symbol: str, price: Decimal) -> None:
    positions = session.scalars(
        select(PositionModel).where(PositionModel.market == market, PositionModel.symbol == symbol)
    ).all()
    for position in positions:
        position.last_price = price


def account_values(session: Session, account_id: str) -> dict[str, Decimal]:
    account = session.get(AccountModel, account_id)
    if account is None:
        raise LookupError("account not found")
    positions = session.scalars(select(PositionModel).where(PositionModel.account_id == account_id)).all()
    market_value = sum((Decimal(p.quantity) * Decimal(p.last_price) for p in positions), Decimal("0"))
    unrealized = sum(
        (Decimal(p.quantity) * (Decimal(p.last_price) - Decimal(p.average_cost)) for p in positions),
        Decimal("0"),
    )
    return {
        "cash": Decimal(account.cash),
        "realized_pnl": Decimal(account.realized_pnl),
        "market_value": market_value,
        "unrealized_pnl": unrealized,
        "equity": Decimal(account.cash) + market_value,
    }

