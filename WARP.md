# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Development Commands

### Quick Testing
```bash
# Run basic test without any dependencies - good for verifying core functionality
python3 test_basic.py

# Install dependencies
pip install -r requirements.txt

# Run demo with all strategies (recommended first step)
python3 -m agent.main --demo

# Run single strategy with specific configuration
python3 -m agent.main --strategy sma --symbols BTC-USD ETH-USD --iterations 5
```

### Development Workflow
```bash
# Install development dependencies (when available)
pip install pytest pytest-asyncio black flake8 mypy

# Code formatting
black agent/

# Code linting
flake8 agent/

# Type checking
mypy agent/
```

### Running the Trading Bot

```bash
# Run continuous trading (safe paper trading mode)
python3 -m agent.main --strategy combo --continuous

# Test with specific risk parameters
python3 -m agent.main --strategy rsi --risk-equity 25000 --risk-per-trade 0.02

# Run with custom polling interval
python3 -m agent.main --strategy sma --symbols BTC-USD --poll-seconds 5 --iterations 10

# Available strategies: sma (SMA crossover), rsi (RSI overbought/oversold), combo (combined SMA + RSI)
# All trading uses synthetic market data and paper trading for safety
```

## Architecture Overview

This is a **modular trading agent framework** built around pluggable components with clean interfaces:

### Core Architecture Pattern
The system uses a **Strategy Pattern** with four main interfaces:

1. **MarketDataProvider** (`agent/base.py`): Abstract interface for data sources
   - Implementation: `InMemoryMarketData` (generates synthetic OHLCV candles)
   - Returns `MarketSnapshot` with ordered candle data (oldest → newest)

2. **SignalProcessor** (`agent/base.py`): Abstract interface for trading strategies
   - Implementations: `SmaCrossoverStrategy`, `RsiStrategy`, `ComboStrategy`
   - Takes market snapshots and generates buy/sell/flat signals with confidence

3. **TradeExecutor** (`agent/base.py`): Abstract interface for trade execution
   - Implementation: `PaperBroker` (simulated order execution)
   - Processes order requests and returns execution results

4. **PreTradeFilter** (`agent/base.py`): Optional filters for signal validation
   - Implementations: `BasicTimeFilter`, `VolatilityFilter`, `TrendFilter`, `ConfidenceFilter`
   - Can block low-quality signals before execution

### Key Data Structures
- **Candle**: OHLCV data with timestamp
- **MarketSnapshot**: Symbol + ordered list of candles
- **Signal**: Trading recommendation (buy/sell/flat) with confidence and metadata
- **OrderRequest**: Trade order with symbol, side, size, type, and optional limit price
- **OrderResult**: Execution result with success status, order ID, and fill details

### Component Orchestration
The `TradingAgent` class (`agent/trading_agent.py`) orchestrates all components:
1. Fetches market snapshots from data provider
2. Generates signals using the strategy
3. Applies optional pre-trade filters
4. Calculates position sizing via risk manager
5. Executes qualifying trades via the broker
6. Handles continuous trading loops with configurable intervals

## Key Implementation Details

### Strategy Development
When creating new strategies, inherit from `SignalProcessor` and implement:
- `generate(snapshot)`: Core trading logic that processes market snapshots
- Return `Signal` objects with side ('buy', 'sell', 'flat'), confidence (0.0-1.0), and metadata

Strategies should include reasoning in the metadata for debugging and analysis.

### Risk Management
The `RiskManager` class handles position sizing based on:
- Account equity
- Risk per trade (percentage)
- Entry and stop loss prices
- Formula: `size = (equity × risk%) / |entry - stop|`

### Filtering System
Pre-trade filters can block signals based on:
- **Time**: Trading hours restriction
- **Volatility**: Minimum volatility requirements
- **Trend**: Align signals with overall trend direction
- **Confidence**: Minimum confidence thresholds

### Data Flow
1. **Data Provider** → `MarketSnapshot` with OHLCV candles
2. **Strategy** processes snapshot → `Signal` with confidence
3. **Filters** validate signal → allow/block decision
4. **Risk Manager** calculates position size
5. **Executor** processes `OrderRequest` → `OrderResult`
6. **Agent** orchestrates the cycle with performance tracking

## Testing Strategy

### Basic Testing
The `test_basic.py` file provides dependency-free testing of the new architecture with synthetic data generation and minimal test implementations.

### Integration Testing
Use demo mode to test all strategies:
```bash
python3 -m agent.main --demo
```

### Manual Testing
Test specific configurations:
```bash
python3 -m agent.main --strategy rsi --symbols BTC-USD --iterations 3
```

## Environment Configuration

### Development Setup
The framework uses synthetic data by default - no API keys needed for development.

### Future Real Data Integration
For real exchange data, store credentials in environment variables:
```bash
export BINANCE_API_KEY="your_key_here"
export BINANCE_API_SECRET="your_secret_here"
```

## Extension Points

### Adding New Data Providers
```python
class CcxtDataProvider(MarketDataProvider):
    def get_snapshot(self, symbol: str, lookback: int = 200, timeframe: str = "1h") -> MarketSnapshot:
        # Fetch from exchange via CCXT
        pass
```

### Adding New Strategies
```python
class MacdStrategy(SignalProcessor):
    def generate(self, snapshot: MarketSnapshot) -> Signal:
        # Implement MACD logic
        pass
```

### Adding New Filters
```python
class VolumeFilter(PreTradeFilter):
    def allow(self, snapshot: MarketSnapshot, signal: Signal) -> bool:
        # Check volume requirements
        pass
```

### Component Registration
Add new components in `agent/main.py` in the `create_agent()` factory function.

## Risk Management Notes

⚠️ **Educational software with built-in safety features**:
- Uses synthetic market data by default
- Paper trading only (no real money at risk)
- Risk management with configurable position sizing
- Multiple safety filters to prevent bad trades
- All trading is logged for analysis
