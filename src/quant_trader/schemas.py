from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .domain import Market, OrderStatus, OrderType, SecurityType, Side


class OrderCreate(BaseModel):
    account_id: str = "paper"
    market: Market
    symbol: str = Field(min_length=1, max_length=32)
    security_type: SecurityType = SecurityType.STOCK
    side: Side
    order_type: OrderType = OrderType.MARKET
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_limit(self):
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")
        return self


class OrderRead(OrderCreate):
    id: str
    status: OrderStatus
    rejection_reason: str | None = None
    submitted_at: datetime
    submitted_on: date | None = None
    model_config = ConfigDict(from_attributes=True)


class BarCreate(BaseModel):
    market: Market
    symbol: str
    trading_date: date
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self):
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close) or self.low > self.high:
            raise ValueError("invalid OHLC range")
        return self


class PositionRead(BaseModel):
    market: Market
    symbol: str
    security_type: SecurityType
    quantity: Decimal
    average_cost: Decimal
    last_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal


class AccountRead(BaseModel):
    id: str
    cash: Decimal
    realized_pnl: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    equity: Decimal


class BacktestRequest(BaseModel):
    market: Market = Market.US
    symbol: str = "DEMO"
    initial_cash: Decimal = Field(default=Decimal("100000"), gt=0)
    fast_window: int = Field(default=3, ge=1)
    slow_window: int = Field(default=5, ge=2)
    csv_path: str | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def windows(self):
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        return self
