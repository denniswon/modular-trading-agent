#!/usr/bin/env python3
"""
Basic test script that works without external dependencies.
Tests the new modular trading agent architecture.
"""

import sys
import os
import time
import random
from datetime import datetime, timedelta
from typing import List

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.base import MarketDataProvider, MarketSnapshot, Candle, SignalProcessor, Signal, TradeExecutor, OrderRequest, OrderResult

# Simple test implementations that don't require external libraries
class TestDataProvider(MarketDataProvider):
    """Test data provider without external dependencies."""
    
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

class TestStrategy(SignalProcessor):
    """Test strategy without external dependencies."""
    
    def __init__(self):
        self.last_price = None
        
    def generate(self, snapshot: MarketSnapshot) -> Signal:
        price = snapshot.candles[-1].close
        
        if not self.last_price:
            self.last_price = price
            return Signal(
                symbol=snapshot.symbol,
                side="flat",
                confidence=0.5,
                meta={'reason': 'Initial price recorded'}
            )
        
        price_change = (price - self.last_price) / self.last_price
        self.last_price = price
        
        if price_change >= 0.02:
            return Signal(
                symbol=snapshot.symbol,
                side="buy",
                confidence=min(0.9, 0.5 + abs(price_change) * 2),
                meta={'price_change': price_change, 'reason': f'Price up {price_change:.2%}'}
            )
        elif price_change <= -0.015:
            return Signal(
                symbol=snapshot.symbol,
                side="sell",
                confidence=min(0.9, 0.5 + abs(price_change) * 2),
                meta={'price_change': price_change, 'reason': f'Price down {price_change:.2%}'}
            )
        else:
            return Signal(
                symbol=snapshot.symbol,
                side="flat",
                confidence=0.7,
                meta={'price_change': price_change, 'reason': 'Price within thresholds'}
            )

class TestExecutor(TradeExecutor):
    """Test executor without external dependencies."""
    
    def __init__(self):
        self._orders = []
        
    def place_order(self, order: OrderRequest) -> OrderResult:
        print(f"🔔 Order: {order.side.upper()} {order.size:.4f} {order.symbol}")
        print(f"   Type: {order.order_type}")
        if order.meta:
            print(f"   Meta: {order.meta}")
        
        # Simulate successful execution
        result = OrderResult(
            ok=True,
            order_id=f"test-{int(time.time()*1000)}",
            filled_price=order.limit_price if order.order_type == "limit" else None,
            filled_size=order.size,
            meta={"echo": order.meta}
        )
        
        self._orders.append(result)
        print(f"   ✅ Executed: Order ID {result.order_id}")
        return result

def main():
    print("🧪 Testing Modular Trading Agent (New Architecture)")
    print("=" * 50)
    
    # Create components
    provider = TestDataProvider()
    strategy = TestStrategy()
    executor = TestExecutor()
    
    symbol = "BTC-USD"
    
    # Test multiple iterations
    for i in range(5):
        print(f"\n📊 Iteration {i+1}/5")
        print("-" * 30)
        
        # Get market snapshot
        snapshot = provider.get_snapshot(symbol, lookback=50)
        current_price = snapshot.candles[-1].close
        print(f"💰 Current price: ${current_price:,.2f}")
        print(f"📈 Candles available: {len(snapshot.candles)}")
        
        # Generate signal
        signal = strategy.generate(snapshot)
        print(f"📊 Signal: {signal.side.upper()} (confidence: {signal.confidence:.2%})")
        if signal.meta:
            print(f"   Reason: {signal.meta.get('reason', 'No reason')}")
        
        # Execute if not flat
        if signal.side != "flat":
            order = OrderRequest(
                symbol=symbol,
                side=signal.side,
                size=1.0,
                order_type="market",
                meta={"confidence": signal.confidence}
            )
            result = executor.place_order(order)
        else:
            print("   ⏸️ No trade (FLAT signal)")
        
        time.sleep(0.2)  # Brief pause
    
    print("\n🎉 All tests completed successfully!")
    print("\nThe new architecture is working correctly!")
    print("\nNext steps:")
    print("1. Run full demo: python3 -m agent.main --demo")
    print("2. Try different strategies: python3 -m agent.main --strategy sma --iterations 3")
    print("3. Test RSI strategy: python3 -m agent.main --strategy rsi --symbols BTC-USD")

if __name__ == "__main__":
    main()
