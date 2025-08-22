"""
Main entry point for the modular trading agent.

This module demonstrates the new TradingAgent architecture with pluggable components.
"""

import argparse
import logging
from typing import List

from .data_provider import InMemoryMarketData
from .strategy import SmaCrossoverStrategy, RsiStrategy, ComboStrategy
from .executor import PaperBroker
from .filters import BasicTimeFilter, VolatilityFilter, TrendFilter, ConfidenceFilter
from .risk_manager import RiskManager
from .trading_agent import TradingAgent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("main")


def create_agent(strategy_name: str = "sma", 
                 risk_equity: float = 50000.0,
                 risk_per_trade: float = 0.01,
                 poll_seconds: int = 2) -> TradingAgent:
    """
    Factory function to create a TradingAgent with specified components.
    
    Args:
        strategy_name: Name of strategy to use ('sma', 'rsi', 'combo')
        risk_equity: Account equity for risk management
        risk_per_trade: Risk per trade as percentage (0.01 = 1%)
        poll_seconds: Polling interval for continuous mode
        
    Returns:
        Configured TradingAgent
    """
    # Create data provider
    data = InMemoryMarketData()
    
    # Create strategy
    if strategy_name.lower() == "sma":
        strategy = SmaCrossoverStrategy(fast=10, slow=30, min_confidence=0.55)
    elif strategy_name.lower() == "rsi":
        strategy = RsiStrategy(period=14, oversold=30, overbought=70)
    elif strategy_name.lower() == "combo":
        strategy = ComboStrategy(fast=10, slow=30, rsi_period=14)
    else:
        log.warning(f"Unknown strategy '{strategy_name}', using SMA")
        strategy = SmaCrossoverStrategy()
    
    # Create trade executor
    broker = PaperBroker()
    
    # Create filters
    filters = [
        BasicTimeFilter(start_hour_utc=0, end_hour_utc=24),  # Allow all hours by default
        VolatilityFilter(min_volatility=0.001),  # Minimum volatility filter
        ConfidenceFilter(min_confidence=0.6),    # Confidence threshold
    ]
    
    # Create risk manager
    risk = RiskManager(account_equity=risk_equity, risk_per_trade=risk_per_trade)
    
    # Create and return trading agent
    return TradingAgent(
        data=data,
        strategy=strategy,
        broker=broker,
        filters=filters,
        risk=risk,
        poll_seconds=poll_seconds,
    )


def run_demo(symbols: List[str] = None):
    """Run demonstration with different strategies."""
    if symbols is None:
        symbols = ["BTC-USD", "ETH-USD", "SOL-USD"]
    
    log.info("🎯 Running Trading Agent Demo")
    log.info("=" * 60)
    
    strategies = [
        ("SMA Crossover", "sma"),
        ("RSI Strategy", "rsi"),
        ("Combo Strategy", "combo")
    ]
    
    for strategy_name, strategy_key in strategies:
        log.info(f"\n📊 Testing {strategy_name}")
        log.info("-" * 40)
        
        agent = create_agent(
            strategy_name=strategy_key,
            risk_equity=10000.0,
            risk_per_trade=0.01,
            poll_seconds=1
        )
        
        # Run 2 iterations for this strategy
        agent.run_loop(symbols, iterations=2)
    
    log.info("\n🎉 Demo completed!")


def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(
        description="Modular Trading Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent.main --demo
  python -m agent.main --strategy sma --symbols BTC-USD ETH-USD --iterations 5
  python -m agent.main --strategy combo --continuous
  python -m agent.main --strategy rsi --risk-equity 25000 --risk-per-trade 0.02
        """
    )
    
    parser.add_argument(
        "--symbols", "-s", 
        nargs="+",
        default=["BTC-USD", "ETH-USD", "SOL-USD"],
        help="Trading symbols (default: BTC-USD ETH-USD SOL-USD)"
    )
    
    parser.add_argument(
        "--strategy", "-st", 
        choices=["sma", "rsi", "combo"],
        default="sma",
        help="Trading strategy to use (default: sma)"
    )
    
    parser.add_argument(
        "--iterations", "-i", 
        type=int, 
        default=3,
        help="Number of iterations to run (default: 3)"
    )
    
    parser.add_argument(
        "--poll-seconds", "-p", 
        type=int, 
        default=2,
        help="Polling interval in seconds (default: 2)"
    )
    
    parser.add_argument(
        "--risk-equity", "-e", 
        type=float, 
        default=50000.0,
        help="Account equity for risk management (default: 50000)"
    )
    
    parser.add_argument(
        "--risk-per-trade", "-r", 
        type=float, 
        default=0.01,
        help="Risk per trade as percentage (default: 0.01 = 1%)"
    )
    
    parser.add_argument(
        "--demo", 
        action="store_true",
        help="Run demo with all strategies"
    )
    
    parser.add_argument(
        "--continuous", "-c", 
        action="store_true",
        help="Run continuously until interrupted"
    )
    
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.demo:
        run_demo(args.symbols)
        return
    
    # Create and configure agent
    agent = create_agent(
        strategy_name=args.strategy,
        risk_equity=args.risk_equity,
        risk_per_trade=args.risk_per_trade,
        poll_seconds=args.poll_seconds
    )
    
    log.info(f"🤖 Trading Agent Configuration:")
    log.info(f"   Symbols: {', '.join(args.symbols)}")
    log.info(f"   Strategy: {args.strategy}")
    log.info(f"   Risk Equity: ${args.risk_equity:,.2f}")
    log.info(f"   Risk Per Trade: {args.risk_per_trade:.2%}")
    log.info(f"   Poll Interval: {args.poll_seconds}s")
    
    if args.continuous:
        agent.run_continuous(args.symbols)
    else:
        log.info(f"   Iterations: {args.iterations}")
        log.info("")
        agent.run_loop(args.symbols, args.iterations)


if __name__ == "__main__":
    main()
