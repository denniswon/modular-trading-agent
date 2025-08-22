"""
Trading strategies.

This module contains concrete implementations of SignalProcessor.
"""

from typing import List, Optional
from .base import SignalProcessor, MarketSnapshot, Signal


def sma(values: List[float], window: int) -> List[Optional[float]]:
    """Simple Moving Average with None for initial periods without enough data."""
    out: List[Optional[float]] = []
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= window:
            s -= values[i - window]
        if i >= window - 1:
            out.append(s / window)
        else:
            out.append(None)
    return out


class SmaCrossoverStrategy(SignalProcessor):
    """
    Classic SMA crossover:
      - BUY when fast SMA crosses above slow SMA
      - SELL when fast SMA crosses below slow SMA
      - Otherwise FLAT with low confidence
    """

    def __init__(self, fast: int = 10, slow: int = 30, min_confidence: float = 0.55):
        assert fast < slow, "fast SMA must be < slow SMA"
        self.fast = fast
        self.slow = slow
        self.min_confidence = min_confidence

    def generate(self, snapshot: MarketSnapshot) -> Signal:
        closes = [c.close for c in snapshot.candles]
        fast_sma = sma(closes, self.fast)
        slow_sma = sma(closes, self.slow)

        # Need at least two recent points for crossover
        if len(closes) < self.slow + 1:
            return Signal(snapshot.symbol, "flat", 0.0, {"reason": "insufficient_data"})

        f_prev, f_now = fast_sma[-2], fast_sma[-1]
        s_prev, s_now = slow_sma[-2], slow_sma[-1]
        price = closes[-1]

        # If any None -> insufficient data
        if any(v is None for v in (f_prev, f_now, s_prev, s_now)):
            return Signal(snapshot.symbol, "flat", 0.0, {"reason": "insufficient_data"})

        crossed_up = f_prev < s_prev and f_now > s_now
        crossed_dn = f_prev > s_prev and f_now < s_now

        # Confidence: distance of SMAs vs price volatility proxy
        distance = abs((f_now - s_now) / price)
        confidence = min(1.0, 0.5 + distance * 20)  # simple scaling into [0,1]

        if crossed_up and confidence >= self.min_confidence:
            return Signal(snapshot.symbol, "buy", confidence, {
                "price": price,
                "fast_sma": f_now,
                "slow_sma": s_now,
                "event": "bullish_crossover"
            })
        elif crossed_dn and confidence >= self.min_confidence:
            return Signal(snapshot.symbol, "sell", confidence, {
                "price": price,
                "fast_sma": f_now,
                "slow_sma": s_now,
                "event": "bearish_crossover"
            })
        else:
            return Signal(snapshot.symbol, "flat", max(0.1, confidence * 0.5), {
                "price": price,
                "fast_sma": f_now,
                "slow_sma": s_now,
                "event": "no_signal"
            })


class RsiStrategy(SignalProcessor):
    """
    RSI strategy:
      - BUY when RSI is oversold
      - SELL when RSI is overbought 
      - Otherwise FLAT
    """

    def __init__(self, period=14, oversold=30, overbought=70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate(self, snapshot: MarketSnapshot) -> Signal:
        closes = [c.close for c in snapshot.candles]
        if len(closes) < self.period + 1:
            return Signal(snapshot.symbol, "flat", 0.0, {"reason": "insufficient"})
        
        # minimal RSI calculation
        gains = []
        losses = []
        for i in range(1, self.period + 1):
            ch = closes[-i] - closes[-i-1]
            gains.append(max(ch, 0))
            losses.append(max(-ch, 0))
        
        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period or 1e-9
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        if rsi < self.oversold:
            return Signal(snapshot.symbol, "buy", 0.6, {"rsi": rsi})
        if rsi > self.overbought:
            return Signal(snapshot.symbol, "sell", 0.6, {"rsi": rsi})
        return Signal(snapshot.symbol, "flat", 0.2, {"rsi": rsi})


class ComboStrategy(SignalProcessor):
    """Combines SMA crossover with RSI confirmation."""
    
    def __init__(self, fast=10, slow=30, rsi_period=14, rsi_oversold=30, rsi_overbought=70):
        self.sma_strategy = SmaCrossoverStrategy(fast, slow)
        self.rsi_strategy = RsiStrategy(rsi_period, rsi_oversold, rsi_overbought)
    
    def generate(self, snapshot: MarketSnapshot) -> Signal:
        sma_signal = self.sma_strategy.generate(snapshot)
        rsi_signal = self.rsi_strategy.generate(snapshot)
        
        # If both agree on direction, boost confidence
        if sma_signal.side == rsi_signal.side and sma_signal.side != "flat":
            combined_confidence = min(1.0, (sma_signal.confidence + rsi_signal.confidence) / 2 * 1.3)
            return Signal(snapshot.symbol, sma_signal.side, combined_confidence, {
                "sma_signal": sma_signal.side,
                "sma_confidence": sma_signal.confidence,
                "rsi_signal": rsi_signal.side, 
                "rsi_confidence": rsi_signal.confidence,
                "reason": "SMA and RSI agree"
            })
        
        # If they disagree or one is flat, use lower confidence
        if sma_signal.side != "flat" and rsi_signal.side == "flat":
            # Use SMA signal but with reduced confidence
            return Signal(snapshot.symbol, sma_signal.side, sma_signal.confidence * 0.7, {
                "reason": "SMA signal, RSI neutral",
                "sma_meta": sma_signal.meta,
                "rsi_meta": rsi_signal.meta
            })
        elif sma_signal.side == "flat" and rsi_signal.side != "flat":
            # Use RSI signal but with reduced confidence  
            return Signal(snapshot.symbol, rsi_signal.side, rsi_signal.confidence * 0.7, {
                "reason": "RSI signal, SMA neutral",
                "sma_meta": sma_signal.meta,
                "rsi_meta": rsi_signal.meta
            })
        else:
            # Both flat or they disagree - stay flat
            return Signal(snapshot.symbol, "flat", 0.3, {
                "reason": "Signals disagree or both flat",
                "sma_signal": sma_signal.side,
                "rsi_signal": rsi_signal.side
            })
