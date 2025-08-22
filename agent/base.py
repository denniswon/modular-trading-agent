"""
Base classes for the modular trading agent.

This module defines the domain models and abstract interfaces that all components must implement.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime


# -----------------------------
# Domain models
# -----------------------------

@dataclass
class Candle:
    """OHLCV candle data structure."""
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class MarketSnapshot:
    """Market data snapshot containing recent candles."""
    symbol: str
    candles: List[Candle]  # ordered oldest -> newest


@dataclass
class Signal:
    """Trading signal with confidence and metadata."""
    symbol: str
    side: str  # 'buy', 'sell', 'flat'
    confidence: float  # 0.0 to 1.0
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderRequest:
    """Order request structure for trade execution."""
    symbol: str
    side: str            # 'buy' or 'sell'
    size: float          # units/shares
    order_type: str      # 'market', 'limit', etc.
    limit_price: Optional[float] = None
    time_in_force: str = "GTC"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderResult:
    """Trade execution result."""
    ok: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    filled_price: Optional[float] = None
    filled_size: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


# -----------------------------
# Base interfaces (extension points)
# -----------------------------

class MarketDataProvider(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    def get_snapshot(self, symbol: str, lookback: int = 200, timeframe: str = "1h") -> MarketSnapshot:
        """
        Return a snapshot of recent candles. Must be ordered oldest -> newest.
        
        Args:
            symbol: Trading symbol (e.g., 'BTC-USD')
            lookback: Number of candles to retrieve
            timeframe: Candle timeframe (e.g., '1h', '1d')
            
        Returns:
            MarketSnapshot with recent candles
        """
        raise NotImplementedError


class AsyncMarketDataProvider(ABC):
    """Abstract base class for async streaming market data providers."""

    @abstractmethod
    async def subscribe_ticks(
        self,
        tokens: List[str],
        interval_sec: int = 10,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream live ticks for given token mints/symbols.
        
        Args:
            tokens: List of token identifiers (mint addresses or symbols)
            interval_sec: Update interval in seconds
            
        Yields:
            Dict per token on each interval with fields like:
            {
              "source": "dexscreener",
              "chain": "solana",
              "token": "<mint_or_symbol>",
              "price_usd": float|None,
              "volume_24h_usd": float|None,
              "liquidity_usd": float|None,
              "change_24h_pct": float|None,
              "pair_address": str|None,
              "slot": int|None,
              "rpc_healthy": bool
            }
        """
        raise NotImplementedError


class SignalProcessor(ABC):
    """Abstract base class for trading signal processors."""

    @abstractmethod
    def generate(self, snapshot: MarketSnapshot) -> Signal:
        """
        Generate a trading signal from market data.
        
        Args:
            snapshot: Market snapshot with recent candles
            
        Returns:
            Signal with trading recommendation
        """
        raise NotImplementedError


class TradeExecutor(ABC):
    """Abstract base class for trade executors."""

    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResult:
        """
        Execute a trade order.
        
        Args:
            order: Order request to execute
            
        Returns:
            OrderResult with execution details
        """
        raise NotImplementedError


class PreTradeFilter(ABC):
    """Optional filters to suppress low-quality signals."""

    @abstractmethod
    def allow(self, snapshot: MarketSnapshot, signal: Signal) -> bool:
        """
        Determine if a signal should be allowed through.
        
        Args:
            snapshot: Market snapshot
            signal: Trading signal to evaluate
            
        Returns:
            True if signal should be allowed, False to block
        """
        raise NotImplementedError
