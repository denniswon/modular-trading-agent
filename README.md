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
# Run a single trading iteration with demo mode
python -m agent.main --single --demo

# Run continuous trading with different strategies
python -m agent.main --strategy ma --executor paper --interval 30

# Use real Binance data (read-only)
python -m agent.main --data-provider binance --strategy rsi --executor demo
```

### Programmatic Usage

```python
from agent.data_provider import DummyProvider
from agent.strategy import MovingAverageStrategy
from agent.executor import PaperTradingExecutor
from agent.main import TradingBot

# Create components
data_provider = DummyProvider()
strategy = MovingAverageStrategy(short_window=5, long_window=20)
executor = PaperTradingExecutor()

# Create and run bot
bot = TradingBot(data_provider, strategy, executor)
bot.run_single_iteration("BTCUSDT")
```

## 🏗️ Architecture

The framework is built around three core abstract components:

### 📡 Data Providers (`MarketDataProvider`)
- **DummyProvider**: Generates fake market data for testing
- **BinanceProvider**: Fetches real-time data from Binance API
- **AlphaVantageProvider**: Fetches stock data from Alpha Vantage API

### 🧠 Trading Strategies (`SignalProcessor`)  
- **SimpleStrategy**: Basic momentum-based trading
- **MovingAverageStrategy**: MA crossover signals
- **RSIStrategy**: RSI overbought/oversold signals
- **ComboStrategy**: Combines multiple indicators

### ⚡ Trade Executors (`TradeExecutor`)
- **PrintExecutor**: Logs trades without execution
- **PaperTradingExecutor**: Realistic simulation with P&L tracking
- **DemoExecutor**: Combines logging and paper trading
- **BinanceExecutor**: Live trading (placeholder - needs implementation)

## 📋 Command Line Interface

```bash
python -m agent.main [OPTIONS]

Options:
  -s, --symbol TEXT           Trading symbol (default: BTCUSDT)
  -d, --data-provider TEXT    Data provider: dummy, binance
  -st, --strategy TEXT        Strategy: simple, ma, rsi, combo  
  -e, --executor TEXT         Executor: print, paper, demo
  -i, --interval INT          Trading interval in seconds
  --single                    Run single iteration
  --demo                      Run demo with all strategies
```

## 📊 Example Output

```
🤖 Trading Bot Configuration:
   Symbol: BTCUSDT
   Data Provider: dummy
   Strategy: ma
   Executor: demo

🔍 Fetching data for BTCUSDT...
Current price: $51,234.56
Historical data points: 50
Generated signal: BUY (confidence: 78%)

[2024-01-15 10:30:15] BUY signal for BTCUSDT
  Quantity: 0.195000
  Price: $51,234.56
  Confidence: 78.00%
  Reason: Bullish crossover: MA5 > MA20
  short_ma: 51145.2340
  long_ma: 50987.8901

✅ Trade executed: Bought 0.195000 BTC at $51,234.56

💰 Current balances:
   USDT: $0.00
   BTC: 0.195000

📈 Performance stats:
   Portfolio value: $9,990.74
   Total return: -0.09%
   Number of trades: 1
   Win rate: 100.0%
```

## 🔧 Configuration & Customization

### Creating Custom Data Providers

```python
from agent.base import MarketDataProvider, MarketData

class MyDataProvider(MarketDataProvider):
    def fetch_data(self, symbol: str) -> MarketData:
        # Implement your data fetching logic
        return MarketData(
            symbol=symbol,
            price=50000.0,
            volume=1000.0,
            timestamp=time.time()
        )
    
    def get_historical_data(self, symbol: str, period: str, limit: int = 100):
        # Implement historical data fetching
        return []
```

### Creating Custom Strategies

```python
from agent.base import SignalProcessor, TradingSignal, SignalType

class MyStrategy(SignalProcessor):
    def generate_signal(self, data, historical_data=None) -> TradingSignal:
        # Implement your trading logic
        return TradingSignal(
            symbol=data.symbol,
            signal_type=SignalType.BUY,  # or SELL, HOLD
            confidence=0.8,
            quantity=1.0,
            price=data.price
        )
    
    def update_parameters(self, parameters):
        # Update strategy parameters
        pass
```

### Creating Custom Executors

```python
from agent.base import TradeExecutor, TradeResult

class MyExecutor(TradeExecutor):
    def execute_trade(self, signal) -> TradeResult:
        # Implement your execution logic
        return TradeResult(
            success=True,
            message=f"Executed {signal.signal_type.value} for {signal.symbol}",
            order_id="12345"
        )
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
