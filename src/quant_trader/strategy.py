from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from enum import StrEnum

from .domain import Bar, OrderIntent, Side


class StrategyType(StrEnum):
    MOVING_AVERAGE_CROSS = "MOVING_AVERAGE_CROSS"
    BUY_AND_HOLD = "BUY_AND_HOLD"


STRATEGY_DESCRIPTIONS = {
    StrategyType.MOVING_AVERAGE_CROSS: "均线交叉：快线向上穿过慢线时买入，快线向下穿过慢线时清仓。",
    StrategyType.BUY_AND_HOLD: "买入并持有：首个可交易日买入固定数量，之后一直持有到回测结束。",
}


class Strategy(ABC):
    name: StrategyType
    description: str

    @abstractmethod
    def on_bar(self, history: list[Bar], position_quantity: Decimal) -> list[OrderIntent]: ...


class MovingAverageCrossStrategy(Strategy):
    def __init__(self, fast_window: int = 3, slow_window: int = 5, trade_quantity: Decimal = Decimal("100")):
        if fast_window >= slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        self.name = StrategyType.MOVING_AVERAGE_CROSS
        self.description = STRATEGY_DESCRIPTIONS[self.name]
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


class BuyAndHoldStrategy(Strategy):
    def __init__(self, trade_quantity: Decimal = Decimal("100")):
        self.name = StrategyType.BUY_AND_HOLD
        self.description = STRATEGY_DESCRIPTIONS[self.name]
        self.trade_quantity = trade_quantity

    def on_bar(self, history: list[Bar], position_quantity: Decimal) -> list[OrderIntent]:
        if position_quantity > 0:
            return []
        bar = history[-1]
        return [OrderIntent(bar.market, bar.symbol, Side.BUY, self.trade_quantity)]


def create_strategy(
    strategy_type: StrategyType,
    fast_window: int,
    slow_window: int,
) -> Strategy:
    if strategy_type == StrategyType.MOVING_AVERAGE_CROSS:
        return MovingAverageCrossStrategy(fast_window, slow_window)
    if strategy_type == StrategyType.BUY_AND_HOLD:
        return BuyAndHoldStrategy()
    raise ValueError(f"unsupported strategy: {strategy_type}")
