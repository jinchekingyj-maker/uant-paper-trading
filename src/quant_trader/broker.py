from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import FillModel, LatestPriceModel, OrderModel, PositionModel
from .domain import Bar, OrderStatus, OrderType, Side, utcnow
from .portfolio import account_values, apply_fill, mark_to_market
from .risk import RiskManager


class BrokerAdapter(ABC):
    @abstractmethod
    async def submit_order(self, request, reference_price: Decimal, submitted_on: date | None = None): ...

    @abstractmethod
    async def cancel_order(self, order_id: str): ...

    @abstractmethod
    async def get_order(self, order_id: str): ...

    @abstractmethod
    async def get_positions(self, account_id: str): ...

    @abstractmethod
    async def get_account(self, account_id: str): ...

    @abstractmethod
    async def process_bar(self, bar: Bar): ...


class PaperBroker(BrokerAdapter):
    def __init__(self, session: Session, risk: RiskManager):
        self.session = session
        self.risk = risk

    async def submit_order(self, request, reference_price: Decimal, submitted_on: date | None = None):
        decision = self.risk.check(self.session, request, reference_price)
        order = OrderModel(
            id=str(uuid4()),
            account_id=request.account_id,
            market=request.market.value,
            symbol=request.symbol.upper(),
            security_type=request.security_type.value,
            side=request.side.value,
            order_type=request.order_type.value,
            quantity=request.quantity,
            limit_price=request.limit_price,
            status=OrderStatus.PENDING.value if decision.accepted else OrderStatus.REJECTED.value,
            rejection_reason=decision.reason,
            submitted_on=submitted_on,
        )
        self.session.add(order)
        self.session.commit()
        return order

    async def cancel_order(self, order_id: str):
        order = await self.get_order(order_id)
        if order.status != OrderStatus.PENDING.value:
            raise ValueError("only pending orders can be cancelled")
        order.status = OrderStatus.CANCELLED.value
        self.session.commit()
        return order

    async def get_order(self, order_id: str):
        order = self.session.get(OrderModel, order_id)
        if order is None:
            raise LookupError("order not found")
        return order

    async def get_positions(self, account_id: str):
        return self.session.scalars(select(PositionModel).where(PositionModel.account_id == account_id)).all()

    async def get_account(self, account_id: str):
        return account_values(self.session, account_id)

    async def process_bar(self, bar: Bar):
        key = f"{bar.market.value}:{bar.symbol.upper()}"
        latest = self.session.get(LatestPriceModel, key)
        if latest is None:
            self.session.add(
                LatestPriceModel(
                    key=key,
                    market=bar.market.value,
                    symbol=bar.symbol.upper(),
                    price=bar.close,
                    trading_date=bar.trading_date,
                )
            )
        else:
            latest.price = bar.close
            latest.trading_date = bar.trading_date
        mark_to_market(self.session, bar.market.value, bar.symbol.upper(), bar.close)
        orders = self.session.scalars(
            select(OrderModel).where(
                OrderModel.market == bar.market.value,
                OrderModel.symbol == bar.symbol.upper(),
                OrderModel.status == OrderStatus.PENDING.value,
            )
        ).all()
        filled = []
        for order in orders:
            if order.submitted_on is not None and bar.trading_date <= order.submitted_on:
                continue
            price = self._fill_price(order, bar)
            if price is None:
                continue
            apply_fill(self.session, order, price)
            order.status = OrderStatus.FILLED.value
            fill = FillModel(order_id=order.id, price=price, quantity=order.quantity, filled_at=utcnow())
            self.session.add(fill)
            filled.append(fill)
        self.session.commit()
        return filled

    @staticmethod
    def _fill_price(order: OrderModel, bar: Bar) -> Decimal | None:
        if order.order_type == OrderType.MARKET.value:
            return bar.open
        limit = Decimal(order.limit_price)
        if order.side == Side.BUY.value and bar.low <= limit:
            return min(bar.open, limit)
        if order.side == Side.SELL.value and bar.high >= limit:
            return max(bar.open, limit)
        return None
