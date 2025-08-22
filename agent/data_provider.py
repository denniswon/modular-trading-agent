"""
Market data providers.

Includes an example in-memory provider generating synthetic candles.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List
import random

from .base import MarketDataProvider, MarketSnapshot, Candle


class InMemoryMarketData(MarketDataProvider):
    """
    Example provider that synthesizes candles.
    Replace with: Binance/Coinbase/Alpaca/CCXT/Polygon.io/etc.
    """

    def __init__(self, seed: int = 42):
        random.seed(seed)

    def _generate_series(self, start_price: float, n: int) -> List[Candle]:
        now = datetime.utcnow()
        candles: List[Candle] = []
        price = start_price
        for i in range(n):
            # simple random walk
            change = random.gauss(0, 0.5)
            o = price
            c = max(0.1, price + change)
            h = max(o, c) + random.random() * 0.3
            l = min(o, c) - random.random() * 0.3
            v = random.uniform(1000, 10000)
            ts = now - timedelta(hours=(n - i))
            candles.append(Candle(ts=ts, open=o, high=h, low=l, close=c, volume=v))
            price = c
        return candles

    def get_snapshot(self, symbol: str, lookback: int = 200, timeframe: str = "1h") -> MarketSnapshot:
        base = 100.0 + hash(symbol) % 50  # deterministic-ish seed per symbol
        candles = self._generate_series(float(base), lookback)
        return MarketSnapshot(symbol=symbol, candles=candles)
