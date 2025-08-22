"""
Main entry point for the modular trading agent.

This module demonstrates how to use the different components together.
"""

import time
import argparse
from typing import Optional

from .data_provider import DummyProvider, BinanceProvider
from .strategy import SimpleStrategy, MovingAverageStrategy, RSIStrategy, ComboStrategy
from .executor import PrintExecutor, PaperTradingExecutor, DemoExecutor


class TradingBot:
    """Main trading bot that orchestrates all components."""
    
    def __init__(self, data_provider, strategy, executor):
        self.data_provider = data_provider
        self.strategy = strategy
        self.executor = executor
        self.running = False
        
    def run_single_iteration(self, symbol: str = "BTCUSDT") -> None:
        """Run a single trading iteration."""
        print(f"🔍 Fetching data for {symbol}...")
        
        # Get current market data
        current_data = self.data_provider.fetch_data(symbol)
        print(f"Current price: ${current_data.price:,.2f}")
        
        # Get historical data for better analysis
        historical_data = self.data_provider.get_historical_data(symbol, "1h", 50)
        print(f"Historical data points: {len(historical_data)}")
        
        # Generate trading signal
        signal = self.strategy.generate_signal(current_data, historical_data)
        print(f"Generated signal: {signal.signal_type.value.upper()} (confidence: {signal.confidence:.2%})")
        
        # Execute trade
        result = self.executor.execute_trade(signal)
        
        if result.success:
            print(f"✅ Trade executed: {result.message}")
        else:
            print(f"❌ Trade failed: {result.message}")
        
        print("-" * 50)
    
    def run_continuous(self, symbol: str = "BTCUSDT", interval: int = 60) -> None:
        """Run the bot continuously with specified interval."""
        print(f"🚀 Starting continuous trading bot for {symbol}")
        print(f"⏰ Trading interval: {interval} seconds")
        print("Press Ctrl+C to stop\n")
        
        self.running = True
        iteration = 0
        
        try:
            while self.running:
                iteration += 1
                print(f"📊 Iteration #{iteration} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                self.run_single_iteration(symbol)
                
                # Show current balances if available
                try:
                    balances = self.executor.get_account_balance()
                    print("💰 Current balances:")
                    for asset, amount in balances.items():
                        if amount > 0:
                            if asset == "USDT":
                                print(f"   {asset}: ${amount:,.2f}")
                            else:
                                print(f"   {asset}: {amount:.6f}")
                    print()
                except AttributeError:
                    pass  # Executor doesn't have balance tracking
                
                # Show performance stats if available
                try:
                    current_data = self.data_provider.fetch_data(symbol)
                    stats = self.executor.get_performance_stats(current_data.price)
                    if "error" not in stats:
                        print("📈 Performance stats:")
                        print(f"   Portfolio value: ${stats['current_value']:,.2f}")
                        print(f"   Total return: {stats['total_return_pct']:+.2f}%")
                        print(f"   Number of trades: {stats['num_trades']}")
                        print(f"   Win rate: {stats['win_rate_pct']:.1f}%")
                        print()
                except AttributeError:
                    pass  # Executor doesn't have performance stats
                
                # Wait for next iteration
                if self.running:
                    time.sleep(interval)
                    
        except KeyboardInterrupt:
            print("\n⏹️  Bot stopped by user")
            self.running = False
    
    def stop(self):
        """Stop the bot."""
        self.running = False


def create_bot(data_provider_type: str = "dummy", 
               strategy_type: str = "simple", 
               executor_type: str = "print",
               **kwargs) -> TradingBot:
    """Factory function to create a trading bot with specified components."""
    
    # Create data provider
    if data_provider_type.lower() == "dummy":
        data_provider = DummyProvider()
    elif data_provider_type.lower() == "binance":
        data_provider = BinanceProvider()
    else:
        print(f"Unknown data provider: {data_provider_type}, using dummy")
        data_provider = DummyProvider()
    
    # Create strategy
    if strategy_type.lower() == "simple":
        strategy = SimpleStrategy()
    elif strategy_type.lower() == "ma" or strategy_type.lower() == "moving_average":
        strategy = MovingAverageStrategy()
    elif strategy_type.lower() == "rsi":
        strategy = RSIStrategy()
    elif strategy_type.lower() == "combo":
        strategy = ComboStrategy()
    else:
        print(f"Unknown strategy: {strategy_type}, using simple")
        strategy = SimpleStrategy()
    
    # Create executor
    if executor_type.lower() == "print":
        executor = PrintExecutor()
    elif executor_type.lower() == "paper":
        executor = PaperTradingExecutor()
    elif executor_type.lower() == "demo":
        executor = DemoExecutor()
    else:
        print(f"Unknown executor: {executor_type}, using print")
        executor = PrintExecutor()
    
    return TradingBot(data_provider, strategy, executor)


def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(description="Modular Trading Agent")
    parser.add_argument("--symbol", "-s", default="BTCUSDT", 
                       help="Trading symbol (default: BTCUSDT)")
    parser.add_argument("--data-provider", "-d", default="dummy",
                       choices=["dummy", "binance"],
                       help="Data provider to use (default: dummy)")
    parser.add_argument("--strategy", "-st", default="simple",
                       choices=["simple", "ma", "rsi", "combo"],
                       help="Trading strategy to use (default: simple)")
    parser.add_argument("--executor", "-e", default="demo",
                       choices=["print", "paper", "demo"],
                       help="Trade executor to use (default: demo)")
    parser.add_argument("--interval", "-i", type=int, default=60,
                       help="Trading interval in seconds (default: 60)")
    parser.add_argument("--single", action="store_true",
                       help="Run single iteration instead of continuous")
    parser.add_argument("--demo", action="store_true",
                       help="Run demo with different strategies")
    
    args = parser.parse_args()
    
    if args.demo:
        run_demo()
        return
    
    # Create and run bot
    bot = create_bot(
        data_provider_type=args.data_provider,
        strategy_type=args.strategy,
        executor_type=args.executor
    )
    
    print(f"🤖 Trading Bot Configuration:")
    print(f"   Symbol: {args.symbol}")
    print(f"   Data Provider: {args.data_provider}")
    print(f"   Strategy: {args.strategy}")
    print(f"   Executor: {args.executor}")
    print(f"   Interval: {args.interval}s")
    print()
    
    if args.single:
        bot.run_single_iteration(args.symbol)
    else:
        bot.run_continuous(args.symbol, args.interval)


def run_demo():
    """Run a demonstration with different strategies."""
    print("🎯 Running Trading Agent Demo")
    print("=" * 60)
    
    symbol = "BTCUSDT"
    strategies = [
        ("Simple Momentum", SimpleStrategy()),
        ("Moving Average", MovingAverageStrategy(short_window=5, long_window=15)),
        ("RSI Strategy", RSIStrategy()),
        ("Combo Strategy", ComboStrategy())
    ]
    
    # Use dummy data provider and demo executor
    data_provider = DummyProvider()
    
    for strategy_name, strategy in strategies:
        print(f"\n📊 Testing {strategy_name}")
        print("-" * 40)
        
        executor = DemoExecutor()
        bot = TradingBot(data_provider, strategy, executor)
        
        # Run 3 iterations
        for i in range(3):
            print(f"Iteration {i+1}/3:")
            bot.run_single_iteration(symbol)
            time.sleep(1)  # Brief pause
        
        # Show final stats
        try:
            current_data = data_provider.fetch_data(symbol)
            stats = executor.get_performance_stats(current_data.price)
            if "error" not in stats:
                print(f"Final Performance - Return: {stats['total_return_pct']:+.2f}%, Trades: {stats['num_trades']}")
        except:
            pass
        
        print()


if __name__ == "__main__":
    main()
