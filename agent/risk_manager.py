"""
Risk management utilities for position sizing and risk controls.
"""

from typing import Dict, Any


class RiskManager:
    """Basic position sizing and risk controls."""

    def __init__(self, account_equity: float, risk_per_trade: float = 0.01):
        """
        Initialize risk manager.
        
        Args:
            account_equity: total account value
            risk_per_trade: fraction of equity to risk per trade (e.g., 0.01 = 1%)
        """
        self.equity = account_equity
        self.risk_per_trade = risk_per_trade

    def position_size(self, entry: float, stop: float) -> float:
        """
        Calculate position size based on risk management.
        
        Risk-based sizing: size = (equity * risk%) / |entry - stop|
        
        Args:
            entry: Entry price for the position
            stop: Stop loss price
            
        Returns:
            Position size in units
        """
        risk_per_unit = abs(entry - stop)
        if risk_per_unit <= 0:
            return 0.0
        
        size = (self.equity * self.risk_per_trade) / risk_per_unit
        return max(0.0, size)

    def update_equity(self, new_equity: float) -> None:
        """Update account equity for position sizing calculations."""
        self.equity = new_equity

    def set_risk_per_trade(self, risk: float) -> None:
        """Update risk per trade percentage."""
        self.risk_per_trade = max(0.0, min(1.0, risk))  # Clamp between 0 and 1

    def get_stats(self) -> Dict[str, Any]:
        """Get current risk manager statistics."""
        return {
            "account_equity": self.equity,
            "risk_per_trade": self.risk_per_trade,
            "max_risk_amount": self.equity * self.risk_per_trade
        }
