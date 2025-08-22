"""
Modular Trading Agent

A flexible, extensible trading agent framework with pluggable components.
"""

__version__ = "0.1.0"
__author__ = "Dennis Won"

from .base import MarketDataProvider, SignalProcessor, TradeExecutor

__all__ = ["MarketDataProvider", "SignalProcessor", "TradeExecutor"]
