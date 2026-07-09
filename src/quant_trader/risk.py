from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .db import AccountModel, PositionModel
from .domain import SecurityType, Side
from .portfolio import account_values, find_position


@dataclass(frozen=True)
class RiskDecision:
    accepted: bool
    reason: str | None = None


class RiskManager:
    def __init__(self, config: Settings):
        self.config = config

    def check(self, session: Session, request, reference_price: Decimal) -> RiskDecision:
        if request.security_type != SecurityType.STOCK:
            return RiskDecision(False, "option execution is not supported in MVP")
        if request.quantity <= 0 or reference_price <= 0:
            return RiskDecision(False, "quantity and price must be positive")
        account = session.get(AccountModel, request.account_id)
        if account is None:
            return RiskDecision(False, "account not found")
        notional = request.quantity * reference_price
        if notional > self.config.max_order_notional:
            return RiskDecision(False, "order notional exceeds limit")
        position = find_position(session, request.account_id, request.market.value, request.symbol)
        if request.side == Side.SELL:
            if position is None or Decimal(position.quantity) < request.quantity:
                return RiskDecision(False, "short selling is not allowed")
            return RiskDecision(True)
        values = account_values(session, request.account_id)
        if notional > values["cash"]:
            return RiskDecision(False, "insufficient cash")
        resulting_symbol_value = notional + (
            Decimal(position.quantity) * Decimal(position.last_price) if position else Decimal("0")
        )
        if resulting_symbol_value > values["equity"] * self.config.max_position_ratio:
            return RiskDecision(False, "position concentration exceeds limit")
        gross = sum(
            (
                Decimal(p.quantity) * Decimal(p.last_price)
                for p in session.scalars(
                    select(PositionModel).where(PositionModel.account_id == request.account_id)
                ).all()
            ),
            Decimal("0"),
        )
        if gross + notional > values["equity"] * self.config.max_gross_exposure_ratio:
            return RiskDecision(False, "gross exposure exceeds limit")
        return RiskDecision(True)

