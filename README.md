# 🤖 Modular Trading Agent

A flexible, extensible trading agent framework with pluggable components for cryptocurrency and stock trading. Built with modularity and ease of use in mind.

## ✨ Features

- **🔌 Modular Architecture**: Swap data providers, strategies, and executors independently
- **📊 Multiple Data Sources**: Support for Binance, Alpha Vantage, and custom data providers
- **🎯 Various Trading Strategies**: Simple momentum, Moving Average, RSI, and combination strategies
- **💼 Flexible Execution**: Print-only, paper trading, and live trading executors
- **📈 Performance Tracking**: Built-in performance metrics and portfolio monitoring
- **🛡️ Risk Management**: Configurable position sizing and risk controls
- **🎮 Easy to Use**: Simple CLI and programmatic interfaces

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/denniswon/modular-trading-agent.git
cd modular-trading-agent
pip install -r requirements.txt
```

### Basic Usage

```bash
# Run demo with all strategies (recommended first step)
python3 -m agent.main --demo

# Run specific strategy with multiple symbols
python3 -m agent.main --strategy sma --symbols BTC-USD ETH-USD --iterations 5

# Run continuous trading with risk management
python3 -m agent.main --strategy combo --continuous --risk-equity 10000
```

### Programmatic Usage

```python
from agent.data_provider import InMemoryMarketData
from agent.strategy import SmaCrossoverStrategy
from agent.executor import PaperBroker
from agent.filters import ConfidenceFilter, VolatilityFilter
from agent.risk_manager import RiskManager
from agent.trading_agent import TradingAgent

# Create components
data = InMemoryMarketData()
strategy = SmaCrossoverStrategy(fast=10, slow=30)
broker = PaperBroker()
filters = [ConfidenceFilter(min_confidence=0.6)]
risk = RiskManager(account_equity=10000, risk_per_trade=0.01)

# Create and run agent
agent = TradingAgent(data, strategy, broker, filters, risk)
agent.run_loop(["BTC-USD"], iterations=3)
```

## 🏗️ Architecture

The framework is built around four core abstract components with clean interfaces:

### 📡 Data Providers (`MarketDataProvider`)
- **InMemoryMarketData**: Generates synthetic OHLCV candles for testing
- Returns `MarketSnapshot` objects with ordered candle data

### 🧠 Trading Strategies (`SignalProcessor`)  
- **SmaCrossoverStrategy**: SMA crossover buy/sell signals
- **RsiStrategy**: RSI overbought/oversold signals
- **ComboStrategy**: Combines SMA and RSI strategies

### ⚡ Trade Executors (`TradeExecutor`)
- **PaperBroker**: Simulated order execution with realistic fills

### 🛡️ Pre-Trade Filters (`PreTradeFilter`)
- **BasicTimeFilter**: Trading hours restriction
- **VolatilityFilter**: Minimum volatility requirements  
- **TrendFilter**: Trend alignment filtering
- **ConfidenceFilter**: Minimum confidence thresholds

## 📋 Command Line Interface

```bash
python3 -m agent.main [OPTIONS]

Options:
  -s, --symbols TEXT+         Trading symbols (default: BTC-USD ETH-USD SOL-USD)
  -st, --strategy TEXT        Strategy: sma, rsi, combo (default: sma)
  -i, --iterations INT        Number of iterations (default: 3)  
  -p, --poll-seconds INT      Polling interval in seconds (default: 2)
  -e, --risk-equity FLOAT     Account equity for risk management (default: 50000)
  -r, --risk-per-trade FLOAT  Risk per trade percentage (default: 0.01)
  --demo                      Run demo with all strategies
  --continuous                Run continuously until interrupted
  --verbose                   Enable verbose logging
```

## 📄 Example Output

```
🤖 Trading Agent Configuration:
   Symbols: BTC-USD, ETH-USD
   Strategy: sma
   Risk Equity: $50,000.00
   Risk Per Trade: 1.00%
   Poll Interval: 2s
   Iterations: 3

🚀 Starting trading agent with 2 symbols for 3 iterations
--- Iteration 1/3 ---
[PaperBroker] Placed BUY 4.2847 BTC-USD (market)
✅ EXECUTED | BTC-USD BUY | Price: 140.3778 | Conf: 68.40% | RR: 2.0
         Order ID: paper-1755842009152
⏸️ SKIPPED | ETH-USD FLAT | Price: 101.9742 | Conf: 41.30% | RR: 0.0
💤 Waiting 2s before next iteration...
```

## 🔧 Configuration & Customization

### Creating Custom Data Providers

```python
from agent.base import MarketDataProvider, MarketSnapshot, Candle
from datetime import datetime, timedelta
from typing import List

class MyDataProvider(MarketDataProvider):
    def get_snapshot(self, symbol: str, lookback: int = 200, timeframe: str = "1h") -> MarketSnapshot:
        # Fetch from your data source (CCXT, Alpaca, etc.)
        candles = []
        for i in range(lookback):
            candle = Candle(
                ts=datetime.now() - timedelta(hours=i),
                open=50000.0, high=51000.0, low=49000.0, close=50500.0, volume=1000.0
            )
            candles.append(candle)
        return MarketSnapshot(symbol=symbol, candles=list(reversed(candles)))
```

### Creating Custom Strategies

```python
from agent.base import SignalProcessor, Signal, MarketSnapshot

class MyStrategy(SignalProcessor):
    def generate(self, snapshot: MarketSnapshot) -> Signal:
        # Implement your trading logic
        closes = [c.close for c in snapshot.candles]
        current_price = closes[-1]
        
        # Example: simple momentum
        if len(closes) >= 2:
            change = (closes[-1] - closes[-2]) / closes[-2]
            if change > 0.02:  # 2% increase
                return Signal(snapshot.symbol, "buy", 0.8, {"momentum": change})
            elif change < -0.02:  # 2% decrease
                return Signal(snapshot.symbol, "sell", 0.8, {"momentum": change})
        
        return Signal(snapshot.symbol, "flat", 0.1, {"reason": "no clear signal"})
```

### Creating Custom Executors

```python
from agent.base import TradeExecutor, OrderRequest, OrderResult
import time

class MyExecutor(TradeExecutor):
    def place_order(self, order: OrderRequest) -> OrderResult:
        # Implement your execution logic (API calls to exchange)
        try:
            # Simulate order execution
            order_id = f"order-{int(time.time()*1000)}"
            return OrderResult(
                ok=True,
                order_id=order_id,
                filled_price=order.limit_price,
                filled_size=order.size
            )
        except Exception as e:
            return OrderResult(ok=False, error=str(e))
```

### Creating Custom Filters

```python
from agent.base import PreTradeFilter, MarketSnapshot, Signal

class VolumeFilter(PreTradeFilter):
    def __init__(self, min_volume: float = 10000):
        self.min_volume = min_volume
    
    def allow(self, snapshot: MarketSnapshot, signal: Signal) -> bool:
        if signal.side == "flat":
            return True
        
        recent_volume = sum(c.volume for c in snapshot.candles[-5:])  # Last 5 candles
        return recent_volume >= self.min_volume
```

## 🔐 Security & Risk Management

⚠️ **Important Security Notes:**

1. **Never commit API keys** to version control
2. **Use environment variables** for sensitive configuration
3. **Start with paper trading** before live trading
4. **Test thoroughly** with small amounts
5. **The BinanceExecutor is a placeholder** - implement proper authentication for production use

### Recommended Environment Setup

```bash
# Create .env file (don't commit this!)
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
ALPHA_VANTAGE_API_KEY=your_av_key_here
```

## 📚 Development

### Running Tests

```bash
# Install development dependencies
pip install pytest pytest-asyncio

# Run tests (when implemented)
pytest tests/
```

### Code Style

```bash
# Format code
black agent/

# Check style  
flake8 agent/

# Type checking
mypy agent/
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

**This software is for educational and research purposes only. Trading cryptocurrencies and stocks involves substantial risk of loss. The authors and contributors are not responsible for any financial losses incurred through the use of this software. Always do your own research and never invest more than you can afford to lose.**

## 🙋‍♂️ Support

- Create an [issue](https://github.com/denniswon/modular-trading-agent/issues) for bug reports
- Start a [discussion](https://github.com/denniswon/modular-trading-agent/discussions) for questions
- ⭐ Star the repo if you find it useful!

## 🗺️ Roadmap

- [ ] Add more sophisticated strategies (MACD, Bollinger Bands, etc.)
- [ ] Implement WebSocket data streaming
- [ ] Add database persistence for trade history
- [ ] Create web dashboard for monitoring
- [ ] Add backtesting framework
- [ ] Implement portfolio optimization
- [ ] Add alert/notification system
- [ ] Support for more exchanges (Coinbase, Kraken, etc.)

---

Made with ❤️ by [Dennis Won](https://github.com/denniswon)
