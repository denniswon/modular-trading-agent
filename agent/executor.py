"""
Example trade executor implementations.

This module contains concrete implementations of TradeExecutor.
"""

import time
import uuid
from typing import Dict, Any, Optional, List
from .base import TradeExecutor, TradingSignal, TradeResult, SignalType


class PrintExecutor(TradeExecutor):
    """Simple executor that prints trade actions without executing."""
    
    def __init__(self, initial_balance: Dict[str, float] = None):
        self.balances = initial_balance or {"USDT": 10000.0, "BTC": 0.0}
        self.open_orders = []
        self.trade_history = []
        
    def execute_trade(self, signal: TradingSignal) -> TradeResult:
        """Print trade signal instead of executing."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        order_id = str(uuid.uuid4())[:8]
        
        if signal.signal_type == SignalType.HOLD:
            print(f"[{timestamp}] HOLD signal for {signal.symbol}")
            print(f"  Confidence: {signal.confidence:.2%}")
            if signal.metadata:
                print(f"  Reason: {signal.metadata.get('reason', 'No reason provided')}")
            print()
            
            return TradeResult(
                success=True,
                message="Hold signal processed",
                order_id=order_id
            )
        
        action = signal.signal_type.value.upper()
        quantity = signal.quantity or 1.0
        price = signal.price or 0.0
        
        print(f"[{timestamp}] {action} signal for {signal.symbol}")
        print(f"  Quantity: {quantity}")
        print(f"  Price: ${price:,.2f}")
        print(f"  Confidence: {signal.confidence:.2%}")
        
        if signal.metadata:
            print(f"  Reason: {signal.metadata.get('reason', 'No reason provided')}")
            # Print additional metadata
            for key, value in signal.metadata.items():
                if key != 'reason' and not key.endswith('_metadata'):
                    if isinstance(value, float):
                        print(f"  {key}: {value:.4f}")
                    else:
                        print(f"  {key}: {value}")
        
        # Simulate portfolio impact
        self._simulate_trade(signal)
        print(f"  Simulated Balance - USDT: ${self.balances.get('USDT', 0):,.2f}, BTC: {self.balances.get('BTC', 0):.6f}")
        print()
        
        # Record trade
        self.trade_history.append({
            'timestamp': timestamp,
            'signal': signal,
            'order_id': order_id
        })
        
        return TradeResult(
            success=True,
            message=f"{action} signal processed for {signal.symbol}",
            order_id=order_id,
            executed_price=price,
            executed_quantity=quantity
        )
    
    def _simulate_trade(self, signal: TradingSignal):
        """Simulate the effect of a trade on balances."""
        if signal.signal_type == SignalType.HOLD or not signal.price or not signal.quantity:
            return
            
        if signal.signal_type == SignalType.BUY:
            # Buy crypto with USDT
            cost = signal.price * signal.quantity
            if self.balances.get("USDT", 0) >= cost:
                self.balances["USDT"] = self.balances.get("USDT", 0) - cost
                self.balances["BTC"] = self.balances.get("BTC", 0) + signal.quantity
                
        elif signal.signal_type == SignalType.SELL:
            # Sell crypto for USDT
            if self.balances.get("BTC", 0) >= signal.quantity:
                self.balances["BTC"] = self.balances.get("BTC", 0) - signal.quantity
                self.balances["USDT"] = self.balances.get("USDT", 0) + (signal.price * signal.quantity)
    
    def get_account_balance(self) -> Dict[str, float]:
        """Return current simulated balances."""
        return self.balances.copy()
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return empty list since this is a simulation."""
        return []


class PaperTradingExecutor(TradeExecutor):
    """Paper trading executor with realistic simulation."""
    
    def __init__(self, initial_balance: Dict[str, float] = None):
        self.balances = initial_balance or {"USDT": 10000.0}
        self.open_orders = []
        self.trade_history = []
        self.position_sizes = {}  # Track position sizes per symbol
        
    def execute_trade(self, signal: TradingSignal) -> TradeResult:
        """Execute paper trade with realistic simulation."""
        order_id = str(uuid.uuid4())[:8]
        
        if signal.signal_type == SignalType.HOLD:
            return TradeResult(
                success=True,
                message="Hold signal - no trade executed",
                order_id=order_id
            )
        
        # Calculate trade size based on available balance and risk management
        trade_size = self._calculate_trade_size(signal)
        
        if trade_size <= 0:
            return TradeResult(
                success=False,
                message="Insufficient balance or invalid trade size",
                order_id=order_id
            )
        
        # Execute the trade
        success, message = self._execute_paper_trade(signal, trade_size)
        
        # Record trade
        trade_record = {
            'timestamp': time.time(),
            'order_id': order_id,
            'symbol': signal.symbol,
            'signal_type': signal.signal_type.value,
            'quantity': trade_size,
            'price': signal.price,
            'success': success,
            'confidence': signal.confidence
        }
        self.trade_history.append(trade_record)
        
        return TradeResult(
            success=success,
            message=message,
            order_id=order_id,
            executed_price=signal.price,
            executed_quantity=trade_size if success else 0
        )
    
    def _calculate_trade_size(self, signal: TradingSignal) -> float:
        """Calculate appropriate trade size based on risk management."""
        if not signal.price:
            return 0.0
        
        # Risk per trade (2% of portfolio)
        risk_per_trade = 0.02
        total_portfolio_value = self._get_portfolio_value(signal.price)
        max_trade_value = total_portfolio_value * risk_per_trade
        
        if signal.signal_type == SignalType.BUY:
            # Use confidence as a multiplier (higher confidence = larger position)
            confidence_multiplier = signal.confidence
            trade_value = max_trade_value * confidence_multiplier
            
            # Ensure we have enough USDT
            available_usdt = self.balances.get("USDT", 0)
            trade_value = min(trade_value, available_usdt * 0.95)  # Keep 5% buffer
            
            return trade_value / signal.price
            
        elif signal.signal_type == SignalType.SELL:
            # Sell based on current position
            symbol_base = signal.symbol.replace("USDT", "")  # e.g., "BTC" from "BTCUSDT"
            current_position = self.balances.get(symbol_base, 0)
            
            # Sell portion based on confidence (higher confidence = sell more)
            sell_ratio = signal.confidence
            return current_position * sell_ratio
        
        return 0.0
    
    def _execute_paper_trade(self, signal: TradingSignal, quantity: float) -> tuple[bool, str]:
        """Execute the paper trade and update balances."""
        symbol_base = signal.symbol.replace("USDT", "")  # e.g., "BTC" from "BTCUSDT"
        
        if signal.signal_type == SignalType.BUY:
            cost = signal.price * quantity
            if self.balances.get("USDT", 0) >= cost:
                self.balances["USDT"] = self.balances.get("USDT", 0) - cost
                self.balances[symbol_base] = self.balances.get(symbol_base, 0) + quantity
                return True, f"Bought {quantity:.6f} {symbol_base} at ${signal.price:,.2f}"
            else:
                return False, "Insufficient USDT balance"
                
        elif signal.signal_type == SignalType.SELL:
            if self.balances.get(symbol_base, 0) >= quantity:
                self.balances[symbol_base] = self.balances.get(symbol_base, 0) - quantity
                revenue = signal.price * quantity
                self.balances["USDT"] = self.balances.get("USDT", 0) + revenue
                return True, f"Sold {quantity:.6f} {symbol_base} at ${signal.price:,.2f}"
            else:
                return False, f"Insufficient {symbol_base} balance"
        
        return False, "Invalid signal type"
    
    def _get_portfolio_value(self, btc_price: float) -> float:
        """Calculate total portfolio value in USDT."""
        total_value = self.balances.get("USDT", 0)
        
        # Add value of crypto holdings
        for symbol, amount in self.balances.items():
            if symbol != "USDT" and amount > 0:
                # Simplified: assume BTC price for all crypto
                total_value += amount * btc_price
        
        return total_value
    
    def get_account_balance(self) -> Dict[str, float]:
        """Return current balances."""
        return self.balances.copy()
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return list of open orders (empty for paper trading)."""
        return []
    
    def get_trade_history(self) -> List[Dict[str, Any]]:
        """Return trade history."""
        return self.trade_history.copy()
    
    def get_performance_stats(self, btc_price: float) -> Dict[str, Any]:
        """Calculate performance statistics."""
        if not self.trade_history:
            return {"error": "No trades executed yet"}
        
        current_value = self._get_portfolio_value(btc_price)
        initial_value = 10000.0  # Assuming initial USDT balance
        
        total_return = (current_value - initial_value) / initial_value
        num_trades = len(self.trade_history)
        
        # Calculate win rate
        winning_trades = sum(1 for trade in self.trade_history if trade['success'])
        win_rate = winning_trades / num_trades if num_trades > 0 else 0
        
        return {
            "initial_value": initial_value,
            "current_value": current_value,
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "num_trades": num_trades,
            "win_rate": win_rate,
            "win_rate_pct": win_rate * 100
        }


class BinanceExecutor(TradeExecutor):
    """Binance API executor (simplified example - NOT FOR PRODUCTION)."""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """
        Initialize Binance executor.
        
        WARNING: This is a simplified example. Production implementations should:
        - Use proper API libraries (python-binance)
        - Implement proper authentication and security
        - Add comprehensive error handling
        - Include rate limiting
        - Add order management features
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.base_url = "https://testnet.binance.vision/api/v3" if testnet else "https://api.binance.com/api/v3"
        
        print("WARNING: BinanceExecutor is a simplified example not suitable for production use!")
        
    def execute_trade(self, signal: TradingSignal) -> TradeResult:
        """Execute trade on Binance (simplified example)."""
        # This is a placeholder implementation
        # Real implementation would require proper API integration
        
        order_id = str(uuid.uuid4())[:8]
        
        if signal.signal_type == SignalType.HOLD:
            return TradeResult(
                success=True,
                message="Hold signal - no trade executed",
                order_id=order_id
            )
        
        # In a real implementation, you would:
        # 1. Authenticate the request
        # 2. Check account balance
        # 3. Calculate appropriate quantity
        # 4. Place market/limit order
        # 5. Handle API responses and errors
        
        print(f"SIMULATED: Would execute {signal.signal_type.value} order for {signal.symbol}")
        
        return TradeResult(
            success=False,
            message="BinanceExecutor not implemented for production use",
            order_id=order_id
        )
    
    def get_account_balance(self) -> Dict[str, float]:
        """Get account balance from Binance."""
        # Placeholder - real implementation would make API call
        return {"USDT": 0.0, "BTC": 0.0}
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders from Binance."""
        # Placeholder - real implementation would make API call
        return []


class DemoExecutor(TradeExecutor):
    """Demo executor that combines logging with paper trading."""
    
    def __init__(self, initial_balance: Dict[str, float] = None, log_file: str = None):
        self.paper_executor = PaperTradingExecutor(initial_balance)
        self.print_executor = PrintExecutor(initial_balance)
        self.log_file = log_file
        
    def execute_trade(self, signal: TradingSignal) -> TradeResult:
        """Execute trade with both logging and paper trading."""
        # Execute paper trade
        result = self.paper_executor.execute_trade(signal)
        
        # Log the trade
        self.print_executor.execute_trade(signal)
        
        # Optionally write to log file
        if self.log_file:
            with open(self.log_file, 'a') as f:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                f.write(f"[{timestamp}] {signal.signal_type.value} {signal.symbol} - {result.message}\n")
        
        return result
    
    def get_account_balance(self) -> Dict[str, float]:
        """Return paper trading balance."""
        return self.paper_executor.get_account_balance()
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return paper trading orders."""
        return self.paper_executor.get_open_orders(symbol)
    
    def get_performance_stats(self, btc_price: float) -> Dict[str, Any]:
        """Get performance statistics."""
        return self.paper_executor.get_performance_stats(btc_price)
