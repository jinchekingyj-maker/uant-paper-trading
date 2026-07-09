from datetime import date, timedelta
from decimal import Decimal

from quant_trader.domain import Bar, Market, Side
from quant_trader.strategy import MovingAverageCrossStrategy


def bars(closes):
    return [
        Bar(Market.US, "TEST", date(2024, 1, 1) + timedelta(days=i), Decimal(c), Decimal(c), Decimal(c), Decimal(c), 1)
        for i, c in enumerate(closes)
    ]


def test_moving_average_cross_generates_buy_without_lookahead():
    strategy = MovingAverageCrossStrategy(2, 3, Decimal("10"))
    history = bars(["3", "2", "1", "2", "4"])
    assert strategy.on_bar(history[:-1], Decimal("0")) == []
    signals = strategy.on_bar(history, Decimal("0"))
    assert len(signals) == 1
    assert signals[0].side == Side.BUY

