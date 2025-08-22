"""
Pre-trade filters to suppress low-quality signals.
"""

from datetime import datetime
from typing import List
from .base import PreTradeFilter, MarketSnapshot, Signal, Candle


class BasicTimeFilter(PreTradeFilter):
    """Filter signals based on trading hours."""

    def __init__(self, start_hour_utc: int = 0, end_hour_utc: int = 24):
        """
        Initialize time filter.
        
        Args:
            start_hour_utc: Start hour for trading (0-23)
            end_hour_utc: End hour for trading (0-24)
        """
        self.start = start_hour_utc
        self.end = end_hour_utc

    def allow(self, snapshot: MarketSnapshot, signal: Signal) -> bool:
        """Allow trading only during specified hours."""
        current_hour = datetime.utcnow().hour
        return self.start <= current_hour < self.end


class VolatilityFilter(PreTradeFilter):
    """Filter signals based on recent volatility."""

    def __init__(self, min_volatility: float = 0.001, lookback: int = 20):
        """
        Initialize volatility filter.
        
        Args:
            min_volatility: Minimum volatility threshold (as percentage)
            lookback: Number of candles to look back for volatility calculation
        """
        self.min_volatility = min_volatility
        self.lookback = lookback

    def _calculate_volatility(self, candles: List[Candle]) -> float:
        """Calculate price volatility over the lookback period."""
        if len(candles) < 2:
            return 0.0
        
        # Use recent candles up to lookback limit
        recent_candles = candles[-self.lookback:] if len(candles) >= self.lookback else candles
        
        if len(recent_candles) < 2:
            return 0.0
        
        # Calculate returns and standard deviation
        returns = []
        for i in range(1, len(recent_candles)):
            prev_close = recent_candles[i-1].close
            curr_close = recent_candles[i].close
            if prev_close > 0:
                returns.append((curr_close - prev_close) / prev_close)
        
        if not returns:
            return 0.0
        
        # Simple standard deviation calculation
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5
        
        return volatility

    def allow(self, snapshot: MarketSnapshot, signal: Signal) -> bool:
        """Allow signals only if volatility is above minimum threshold."""
        if signal.side == 'flat':
            return True  # Always allow flat signals
        
        volatility = self._calculate_volatility(snapshot.candles)
        return volatility >= self.min_volatility


class TrendFilter(PreTradeFilter):
    """Filter signals based on overall trend direction."""

    def __init__(self, trend_window: int = 50):
        """
        Initialize trend filter.
        
        Args:
            trend_window: Number of candles to use for trend calculation
        """
        self.trend_window = trend_window

    def _get_trend_direction(self, candles: List[Candle]) -> str:
        """
        Determine trend direction based on price movement.
        
        Returns:
            'up', 'down', or 'neutral'
        """
        if len(candles) < self.trend_window:
            return 'neutral'
        
        # Compare current price to price N periods ago
        current_price = candles[-1].close
        past_price = candles[-self.trend_window].close
        
        price_change = (current_price - past_price) / past_price
        
        if price_change > 0.02:  # 2% threshold for uptrend
            return 'up'
        elif price_change < -0.02:  # 2% threshold for downtrend
            return 'down'
        else:
            return 'neutral'

    def allow(self, snapshot: MarketSnapshot, signal: Signal) -> bool:
        """Allow signals that align with the overall trend."""
        if signal.side == 'flat':
            return True
        
        trend = self._get_trend_direction(snapshot.candles)
        
        # Allow buy signals in uptrend, sell signals in downtrend
        if trend == 'up' and signal.side == 'buy':
            return True
        elif trend == 'down' and signal.side == 'sell':
            return True
        elif trend == 'neutral':
            return True  # Allow all signals in neutral trend
        else:
            return False  # Block counter-trend signals


class ConfidenceFilter(PreTradeFilter):
    """Filter signals based on minimum confidence threshold."""

    def __init__(self, min_confidence: float = 0.6):
        """
        Initialize confidence filter.
        
        Args:
            min_confidence: Minimum confidence threshold (0.0 to 1.0)
        """
        self.min_confidence = min_confidence

    def allow(self, snapshot: MarketSnapshot, signal: Signal) -> bool:
        """Allow signals only if confidence meets minimum threshold."""
        if signal.side == 'flat':
            return True  # Always allow flat signals
        
        return signal.confidence >= self.min_confidence
