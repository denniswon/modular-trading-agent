"""
Base classes for the modular trading agent.

This module defines the abstract interfaces that all components must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class SignalType(Enum):
    """Trading signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class MarketData:
    """Market data structure."""
    symbol: str
    price: float
    volume: float
    timestamp: float
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class TradingSignal:
    """Trading signal structure."""
    symbol: str
    signal_type: SignalType
    confidence: float  # 0.0 to 1.0
    quantity: Optional[float] = None
    price: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TradeResult:
    """Trade execution result."""
    success: bool
    message: str
    order_id: Optional[str] = None
    executed_price: Optional[float] = None
    executed_quantity: Optional[float] = None


class MarketDataProvider(ABC):
    """Abstract base class for market data providers."""
    
    @abstractmethod
    def fetch_data(self, symbol: str) -> MarketData:
        """
        Fetch market data for a given symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            
        Returns:
            MarketData object with current market information
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_historical_data(self, symbol: str, period: str, limit: int = 100) -> list[MarketData]:
        """
        Get historical market data.
        
        Args:
            symbol: Trading symbol
            period: Time period (e.g., '1h', '1d')
            limit: Number of data points to retrieve
            
        Returns:
            List of historical MarketData objects
        """
        raise NotImplementedError


class SignalProcessor(ABC):
    """Abstract base class for trading signal processors."""
    
    @abstractmethod
    def generate_signal(self, data: MarketData, historical_data: Optional[list[MarketData]] = None) -> TradingSignal:
        """
        Generate a trading signal based on market data.
        
        Args:
            data: Current market data
            historical_data: Optional historical data for analysis
            
        Returns:
            TradingSignal with recommendation
        """
        raise NotImplementedError
    
    @abstractmethod
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """
        Update strategy parameters.
        
        Args:
            parameters: Dictionary of parameter updates
        """
        raise NotImplementedError


class TradeExecutor(ABC):
    """Abstract base class for trade executors."""
    
    @abstractmethod
    def execute_trade(self, signal: TradingSignal) -> TradeResult:
        """
        Execute a trade based on the given signal.
        
        Args:
            signal: TradingSignal to execute
            
        Returns:
            TradeResult with execution details
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_account_balance(self) -> Dict[str, float]:
        """
        Get current account balances.
        
        Returns:
            Dictionary mapping asset symbols to balances
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> list[Dict[str, Any]]:
        """
        Get list of open orders.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of open order dictionaries
        """
        raise NotImplementedError
