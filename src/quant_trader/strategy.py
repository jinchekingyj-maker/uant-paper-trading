from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from .domain import Bar, OrderIntent, Side


class Strategy(ABC):
    @abstractmethod
    def on_bar(self, history: list[Bar], position_quantity: Decimal) -> list[OrderIntent]: ...


class MovingAverageCrossStrategy(Strategy):
    def __init__(self, fast_window: int = 3, slow_window: int = 5, trade_quantity: Decimal = Decimal("100")):
        if fast_window >= slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.trade_quantity = trade_quantity

    def on_bar(self, history: list[Bar], position_quantity: Decimal) -> list[OrderIntent]:
        if len(history) < self.slow_window + 1:
            return []
        closes = [bar.close for bar in history]
        previous_fast = sum(closes[-self.fast_window - 1 : -1]) / self.fast_window
        previous_slow = sum(closes[-self.slow_window - 1 : -1]) / self.slow_window
        current_fast = sum(closes[-self.fast_window :]) / self.fast_window
        current_slow = sum(closes[-self.slow_window :]) / self.slow_window
        bar = history[-1]
        if previous_fast <= previous_slow and current_fast > current_slow and position_quantity == 0:
            return [OrderIntent(bar.market, bar.symbol, Side.BUY, self.trade_quantity)]
        if previous_fast >= previous_slow and current_fast < current_slow and position_quantity > 0:
            return [OrderIntent(bar.market, bar.symbol, Side.SELL, position_quantity)]
        return []

