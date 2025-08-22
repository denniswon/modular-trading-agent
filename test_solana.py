"""
Test script for Solana integration components.

This script tests the basic functionality of the Solana components without
requiring actual API connections.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
from typing import AsyncIterator

from agent.types import TokenTick
from agent.solana_agent import SolanaStreamingAgent
from agent.strategy import RsiStrategy
from agent.executor import PaperBroker
from agent.filters import ConfidenceFilter
from agent.risk_manager import RiskManager

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class MockDexScreenerProvider:
    """Mock data provider for testing."""
    
    def __init__(self):
        self.call_count = 0
    
    async def subscribe_ticks(self, tokens: list, interval_sec: int = 30) -> AsyncIterator[dict]:
        """Yield mock token ticks as dicts."""
        mock_prices = [1.23, 1.25, 1.21, 1.28, 1.24]  # Simulate price changes
        
        for i, price in enumerate(mock_prices):
            self.call_count += 1
            
            # Mock tick data as dict (matching the AsyncMarketDataProvider interface)
            tick_data = {
                "source": "mock",
                "chain": "solana",
                "token": "MOCK_TOKEN",
                "price_usd": price,
                "volume_24h_usd": 1000000 + (i * 50000),
                "liquidity_usd": 500000,
                "change_24h_pct": 0.05 + (i * 0.01),
                "pair_address": "MOCK_PAIR",
                "slot": 12345 + i,
                "rpc_healthy": True
            }
            
            log.info(f"Mock tick {self.call_count}: ${price:.3f}")
            yield tick_data
            
            await asyncio.sleep(0.5)  # Small delay for testing
    
    async def get_solana_health(self):
        """Mock Solana health check."""
        return {"status": "healthy", "slot": 12345}


async def test_single_cycle():
    """Test a single processing cycle."""
    log.info("=== Testing Single Cycle ===")
    
    # Create mock components
    data_provider = MockDexScreenerProvider()
    strategy = RsiStrategy(period=3, oversold=30, overbought=70)  # Short period for testing
    executor = PaperBroker()
    filters = [ConfidenceFilter(min_confidence=0.3)]  # Low threshold for testing
    risk_manager = RiskManager(account_equity=1000, risk_per_trade=0.01)
    
    # Create agent
    agent = SolanaStreamingAgent(
        data_provider=data_provider,
        strategy=strategy,
        executor=executor,
        filters=filters,
        risk_manager=risk_manager
    )
    
    # Run single cycle
    results = await agent.run_single_cycle(["MOCK_TOKEN"], interval_sec=1)
    
    log.info(f"Single cycle completed with {len(results)} results")
    for result in results:
        log.info(f"Result: {result}")
    
    return len(results) > 0


async def test_short_streaming():
    """Test streaming for a few iterations."""
    log.info("\\n=== Testing Short Streaming ===")
    
    # Create components
    data_provider = MockDexScreenerProvider()
    strategy = RsiStrategy(period=3, oversold=30, overbought=70)
    executor = PaperBroker()
    filters = []  # No filters for this test
    risk_manager = RiskManager(account_equity=1000, risk_per_trade=0.01)
    
    # Create agent
    agent = SolanaStreamingAgent(
        data_provider=data_provider,
        strategy=strategy,
        executor=executor,
        filters=filters,
        risk_manager=risk_manager
    )
    
    # Run streaming for short duration
    try:
        await agent.run_streaming(["MOCK_TOKEN"], interval_sec=1, max_duration_sec=3)
        log.info("Short streaming test completed successfully")
        return True
    except Exception as e:
        log.error(f"Streaming test failed: {e}")
        return False


async def test_strategy_integration():
    """Test strategy integration with mock data."""
    log.info("\\n=== Testing Strategy Integration ===")
    
    from agent.strategy import SmaCrossoverStrategy, ComboStrategy
    from agent.base import MarketSnapshot, Candle
    from datetime import datetime
    
    # Test data - create snapshots with candle data
    snapshots = []
    base_price = 1.0
    for i in range(10):
        price = base_price + (i * 0.01)  # Gradual price increase
        
        # Create candle data
        candles = []
        for j in range(20):  # 20 candles per snapshot
            candle_price = price + (j * 0.001)
            candle = Candle(
                ts=datetime.now(),
                open=candle_price,
                high=candle_price * 1.01,
                low=candle_price * 0.99,
                close=candle_price,
                volume=1000
            )
            candles.append(candle)
        
        snapshot = MarketSnapshot(
            symbol="TEST",
            candles=candles
        )
        snapshots.append(snapshot)
    
    # Test SMA strategy
    sma_strategy = SmaCrossoverStrategy(fast=3, slow=5, min_confidence=0.1)
    
    signals = []
    for snapshot in snapshots:
        signal = sma_strategy.generate(snapshot)
        if signal:
            signals.append(signal)
    
    log.info(f"SMA strategy generated {len(signals)} signals")
    
    # Test Combo strategy
    combo_strategy = ComboStrategy(fast=3, slow=5, rsi_period=5)
    
    combo_signals = []
    for snapshot in snapshots:
        signal = combo_strategy.generate(snapshot)
        if signal:
            combo_signals.append(signal)
    
    log.info(f"Combo strategy generated {len(combo_signals)} signals")
    
    return len(signals) > 0 and len(combo_signals) > 0


async def main():
    """Run all tests."""
    log.info("🧪 Testing Solana Integration Components")
    log.info("=" * 50)
    
    tests = [
        ("Strategy Integration", test_strategy_integration),
        ("Single Cycle", test_single_cycle),
        ("Short Streaming", test_short_streaming),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            status = "✅ PASS" if result else "❌ FAIL"
            results.append(result)
            log.info(f"{status} | {test_name}")
        except Exception as e:
            log.error(f"❌ FAIL | {test_name}: {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    log.info("\\n" + "=" * 50)
    log.info(f"🎯 Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        log.info("🎉 All tests passed! Solana integration is ready.")
    else:
        log.warning("⚠️ Some tests failed. Check the logs above.")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        log.info("\\n👋 Tests interrupted by user")
        exit(1)
    except Exception as e:
        log.error(f"💥 Unexpected error: {e}")
        exit(1)
