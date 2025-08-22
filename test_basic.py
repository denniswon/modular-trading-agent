#!/usr/bin/env python3
"""
Basic test script that works without external dependencies.
Tests only the core modular functionality.
"""

import sys
import os
import time
import random

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.base import MarketDataProvider, MarketData, SignalProcessor, TradingSignal, SignalType, TradeExecutor, TradeResult

# Simple test implementations that don't require external libraries
class TestDataProvider(MarketDataProvider):
    """Test data provider without external dependencies."""
    
    def __init__(self):
        self.price_cache = {}
        
    def fetch_data(self, symbol: str) -> MarketData:
        base_price = self.price_cache.get(symbol, 50000.0 if 'BTC' in symbol else 100.0)
        price_change = random.uniform(-0.02, 0.025)
        new_price = base_price * (1 + price_change)
        self.price_cache[symbol] = new_price
        
        return MarketData(
            symbol=symbol,
            price=round(new_price, 2),
            volume=random.uniform(1000, 10000),
            timestamp=time.time(),
            additional_data={
                'high_24h': new_price * 1.05,
                'low_24h': new_price * 0.95,
                'change_24h': random.uniform(-5, 5)
            }
        )
    
    def get_historical_data(self, symbol: str, period: str, limit: int = 100) -> list[MarketData]:
        historical_data = []
        current_time = time.time()
        base_price = 50000.0 if 'BTC' in symbol else 100.0
        
        for i in range(limit):
            timestamp = current_time - (i * 3600)
            price_change = random.uniform(-0.03, 0.03)
            price = base_price * (1 + price_change)
            base_price = price
            
            historical_data.append(MarketData(
                symbol=symbol,
                price=round(price, 2),
                volume=random.uniform(500, 5000),
                timestamp=timestamp,
                additional_data={'period': period}
            ))
        
        return list(reversed(historical_data))

class TestStrategy(SignalProcessor):
    """Test strategy without external dependencies."""
    
    def __init__(self):
        self.last_price = None
        
    def generate_signal(self, data: MarketData, historical_data=None) -> TradingSignal:
        if not self.last_price:
            self.last_price = data.price
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.HOLD,
                confidence=0.5,
                metadata={'reason': 'Initial price recorded'}
            )
        
        price_change = (data.price - self.last_price) / self.last_price
        self.last_price = data.price
        
        if price_change >= 0.02:
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.BUY,
                confidence=min(0.9, 0.5 + abs(price_change) * 2),
                quantity=1.0,
                price=data.price,
                metadata={'price_change': price_change, 'reason': f'Price up {price_change:.2%}'}
            )
        elif price_change <= -0.015:
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.SELL,
                confidence=min(0.9, 0.5 + abs(price_change) * 2),
                quantity=1.0,
                price=data.price,
                metadata={'price_change': price_change, 'reason': f'Price down {price_change:.2%}'}
            )
        else:
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.HOLD,
                confidence=0.7,
                metadata={'price_change': price_change, 'reason': 'Price within thresholds'}
            )
    
    def update_parameters(self, parameters):
        pass

class TestExecutor(TradeExecutor):
    """Test executor without external dependencies."""
    
    def __init__(self):
        self.balances = {"USDT": 10000.0, "BTC": 0.0}
        
    def execute_trade(self, signal: TradingSignal) -> TradeResult:
        print(f"🔔 Signal: {signal.signal_type.value.upper()} {signal.symbol}")
        print(f"   Confidence: {signal.confidence:.2%}")
        if signal.metadata:
            print(f"   Reason: {signal.metadata.get('reason', 'No reason')}")
        
        if signal.signal_type == SignalType.HOLD:
            return TradeResult(success=True, message="Hold position")
        
        # Simulate trade execution
        return TradeResult(
            success=True,
            message=f"Simulated {signal.signal_type.value} for {signal.symbol}",
            order_id="test123",
            executed_price=signal.price,
            executed_quantity=signal.quantity
        )
    
    def get_account_balance(self):
        return self.balances.copy()
    
    def get_open_orders(self, symbol=None):
        return []

def main():
    print("🧪 Testing Modular Trading Agent (Basic)")
    print("=" * 50)
    
    # Create components
    provider = TestDataProvider()
    strategy = TestStrategy()
    executor = TestExecutor()
    
    symbol = "BTCUSDT"
    
    # Test multiple iterations
    for i in range(5):
        print(f"\n📊 Iteration {i+1}/5")
        print("-" * 30)
        
        # Get data
        data = provider.fetch_data(symbol)
        print(f"💰 Current price: ${data.price:,.2f}")
        
        # Generate signal
        signal = strategy.generate_signal(data)
        
        # Execute trade
        result = executor.execute_trade(signal)
        
        if result.success:
            print(f"✅ {result.message}")
        else:
            print(f"❌ {result.message}")
        
        time.sleep(0.5)  # Brief pause
    
    print("\n🎉 All tests completed successfully!")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Run full demo: python -m agent.main --demo")
    print("3. Try different strategies: python -m agent.main --strategy ma --single")

if __name__ == "__main__":
    main()
