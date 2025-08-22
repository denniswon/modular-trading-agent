# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## 🌟 NEW: Comprehensive Solana Trading Support!

This modular trading agent now supports **live Solana token trading** with real-time data from Dexscreener API!

## Development Commands

### Quick Testing
```bash
# Test traditional components (no dependencies)
python3 test_basic.py

# Install dependencies (required for Solana features)
pip install -r requirements.txt

# Test Solana integration components
python3 test_solana.py
```

### Traditional Trading (Synthetic Data)
```bash
# Run demo with all strategies (recommended first step)
python3 -m agent.main --demo

# Run single strategy with specific configuration
python3 -m agent.main --strategy sma --symbols BTC-USD ETH-USD --iterations 5

# Show Solana capabilities info
python3 -m agent.main --solana-info
```

### 🚀 Solana Token Trading (Live Data)
```bash
# Quick demo with live Solana token data
python3 -m agent.solana_main --demo

# Single data fetch and analysis cycle
python3 -m agent.solana_main --single-cycle

# Continuous trading for 30 minutes
python3 -m agent.solana_main --continuous --duration 30
```

### Environment Setup
```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup Solana configuration (optional - has defaults)
cp .env.example .env
# Edit .env with your preferred settings
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
The system uses a **Strategy Pattern** with dual operating modes:

#### Traditional Mode (Synthetic Data)
- **TradingAgent**: Synchronous orchestrator for testing and development
- Uses synthetic market data generation
- Single-threaded execution with configurable polling

#### 🌟 Solana Mode (Live Data)
- **SolanaStreamingAgent**: Asynchronous orchestrator for live trading
- Real-time token data from Dexscreener API
- Integrated Solana RPC health monitoring
- Rate limiting and error recovery

### Core Interfaces

1. **MarketDataProvider** (`agent/base.py`): Synchronous data sources
   - Implementation: `InMemoryMarketData` (generates synthetic OHLCV candles)
   - Returns `MarketSnapshot` with ordered candle data (oldest → newest)

2. **AsyncMarketDataProvider** (`agent/base.py`): 🌟 Async streaming data sources
   - Implementation: `DexScreenerSolanaProvider` (live Solana token data)
   - Streams real-time price, volume, liquidity data
   - Built-in rate limiting and health checks

3. **SignalProcessor** (`agent/base.py`): Abstract interface for trading strategies
   - Implementations: `SmaCrossoverStrategy`, `RsiStrategy`, `ComboStrategy`
   - Takes market snapshots and generates buy/sell/flat signals with confidence
   - **Same strategies work for both traditional and Solana modes!**

4. **TradeExecutor** (`agent/base.py`): Abstract interface for trade execution
   - Implementation: `PaperBroker` (simulated order execution)
   - Processes order requests and returns execution results

5. **PreTradeFilter** (`agent/base.py`): Optional filters for signal validation
   - Implementations: `BasicTimeFilter`, `VolatilityFilter`, `TrendFilter`, `ConfidenceFilter`
   - Can block low-quality signals before execution
   - **Same filters work for both traditional and Solana modes!**

### Key Data Structures
- **Candle**: OHLCV data with timestamp
- **MarketSnapshot**: Symbol + ordered list of candles
- **Signal**: Trading recommendation (buy/sell/flat) with confidence and metadata
- **OrderRequest**: Trade order with symbol, side, size, type, and optional limit price
- **OrderResult**: Execution result with success status, order ID, and fill details
- **TokenTick** 🌟: Live token data from Dexscreener (price, volume, liquidity, 24h change)

### Component Orchestration

#### Traditional Mode
The `TradingAgent` class (`agent/trading_agent.py`) orchestrates all components:
1. Fetches market snapshots from data provider
2. Generates signals using the strategy
3. Applies optional pre-trade filters
4. Calculates position sizing via risk manager
5. Executes qualifying trades via the broker
6. Handles continuous trading loops with configurable intervals

#### 🌟 Solana Streaming Mode
The `SolanaStreamingAgent` class (`agent/solana_agent.py`) provides async orchestration:
1. **Streams live token ticks** from Dexscreener API
2. **Monitors Solana RPC health** and slot info
3. **Converts ticks to market snapshots** compatible with existing strategies
4. **Applies same filtering and risk management** as traditional mode
5. **Rate limits API calls** with jitter and backoff
6. **Handles errors gracefully** with automatic recovery
7. **Provides detailed logging** and performance metrics

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

**Traditional (Sync):**
```python
class CcxtDataProvider(MarketDataProvider):
    def get_snapshot(self, symbol: str, lookback: int = 200, timeframe: str = "1h") -> MarketSnapshot:
        # Fetch from exchange via CCXT
        pass
```

**🌟 Async/Streaming:**
```python
class CustomAsyncProvider(AsyncMarketDataProvider):
    async def subscribe_ticks(self, tokens: List[str], interval_sec: int = 10) -> AsyncIterator[Dict[str, Any]]:
        # Stream from custom API
        for token in tokens:
            yield {
                "source": "custom",
                "token": token,
                "price_usd": await self.get_price(token),
                "volume_24h_usd": await self.get_volume(token),
                # ... other fields
            }
```

### Adding New Strategies
```python
class MacdStrategy(SignalProcessor):
    def generate(self, snapshot: MarketSnapshot) -> Signal:
        # Implement MACD logic
        # Works automatically with both traditional and Solana modes!
        pass
```

### Adding New Filters
```python
class VolumeFilter(PreTradeFilter):
    def allow(self, snapshot: MarketSnapshot, signal: Signal) -> bool:
        # Check volume requirements
        # Works automatically with both traditional and Solana modes!
        pass
```

### Component Registration
- **Traditional**: Add new components in `agent/main.py` in the `create_agent()` factory function
- **🌟 Solana**: Use directly in `agent/solana_main.py` or create custom configuration scripts

## 🌟 Solana Configuration

### Environment Variables (`.env` file)
```bash
# Solana RPC endpoint
SOLANA_RPC_ENDPOINT=https://api.mainnet-beta.solana.com

# Popular SPL token mint addresses
MINT_BONK=DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263
MINT_WIF=EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm
MINT_SOL=So11111111111111111111111111111111111111112
MINT_USDC=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v

# Trading configuration
MIN_PRICE_CHANGE_THRESHOLD=0.001

# Risk management
RISK_EQUITY=10000
RISK_PER_TRADE=0.01

# Logging
LOG_LEVEL=INFO
```

### Key Features
- **No API key required** - Uses Dexscreener public API
- **Built-in rate limiting** with jitter and exponential backoff
- **Solana RPC health monitoring** with automatic failover
- **Price change thresholds** to filter out stale data
- **All existing strategies and filters work automatically**

## Risk Management Notes

⚠️ **Educational software with built-in safety features**:

### Traditional Mode
- Uses synthetic market data by default
- Paper trading only (no real money at risk)
- Risk management with configurable position sizing
- Multiple safety filters to prevent bad trades
- All trading is logged for analysis

### 🌟 Solana Mode
- **Paper trading by default** (PaperBroker)
- **Live data with safety filters**
- **Rate limiting** prevents API abuse
- **Price change thresholds** filter stale data
- **Health monitoring** ensures RPC connectivity
- **Comprehensive logging** for debugging
- **Error recovery** with graceful degradation
- **Position sizing** based on account equity and risk tolerance

🛡️ **Always test thoroughly with paper trading before deploying any capital!**
