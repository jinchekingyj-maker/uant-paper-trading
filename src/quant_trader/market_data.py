from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote

import httpx

from .domain import Bar, Market


def provider_symbol(symbol: str, market: Market) -> str:
    value = symbol.strip().upper()
    if market == Market.HK and not value.endswith(".HK"):
        value = f"{value.zfill(4)}.HK"
    return value


async def fetch_daily_bars(
    symbol: str,
    market: Market,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Bar]:
    end = end_date or date.today()
    start = start_date or end - timedelta(days=365 * 2)
    if start >= end:
        raise ValueError("start_date must be earlier than end_date")
    ticker = provider_symbol(symbol, market)
    period1 = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    period2 = int(datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker)}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history"
    )
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as client:
        response = await client.get(url)
        response.raise_for_status()
    payload = response.json()
    result = payload.get("chart", {}).get("result")
    if not result:
        message = payload.get("chart", {}).get("error", {}).get("description", "symbol not found")
        raise ValueError(message)
    item = result[0]
    quote_data = item["indicators"]["quote"][0]
    bars: list[Bar] = []
    for index, timestamp in enumerate(item.get("timestamp", [])):
        values = {name: quote_data.get(name, [None])[index] for name in ("open", "high", "low", "close", "volume")}
        if any(values[name] is None for name in ("open", "high", "low", "close")):
            continue
        bars.append(
            Bar(
                market=market,
                symbol=symbol.strip().upper(),
                trading_date=datetime.fromtimestamp(timestamp, timezone.utc).date(),
                open=Decimal(str(values["open"])),
                high=Decimal(str(values["high"])),
                low=Decimal(str(values["low"])),
                close=Decimal(str(values["close"])),
                volume=int(values["volume"] or 0),
            )
        )
    if not bars:
        raise ValueError("no daily bars returned for this symbol and date range")
    return bars

