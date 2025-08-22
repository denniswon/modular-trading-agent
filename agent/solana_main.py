"""
Main entry point for Solana token trading using Dexscreener API.

This module demonstrates how to use the SolanaStreamingAgent with live token data
from Dexscreener and Solana RPC connectivity.
"""

import asyncio
import os
import logging
from typing import List

from dotenv import load_dotenv

from agent.data_provider_dexscreener import DexScreenerSolanaProvider, POPULAR_SOLANA_TOKENS
from agent.strategy import SmaCrossoverStrategy, RsiStrategy, ComboStrategy
from agent.executor import PaperBroker
from agent.filters import ConfidenceFilter, VolatilityFilter, BasicTimeFilter
from agent.risk_manager import RiskManager
from agent.solana_agent import SolanaStreamingAgent

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger(__name__)


def get_tokens_from_env() -> List[str]:
    """Get token mint addresses from environment variables."""
    tokens = []
    
    # Try to get from specific env vars first
    bonk = os.getenv("MINT_BONK")
    if bonk:
        tokens.append(bonk)
        
    wif = os.getenv("MINT_WIF") 
    if wif:
        tokens.append(wif)
        
    sol = os.getenv("MINT_SOL")
    if sol:
        tokens.append(sol)
    
    # If no env vars set, use some popular defaults
    if not tokens:
        tokens = [
            POPULAR_SOLANA_TOKENS["BONK"],
            POPULAR_SOLANA_TOKENS["SOL"], 
            POPULAR_SOLANA_TOKENS["USDC"]
        ]
        log.info("Using default token list - set MINT_* env vars to customize")
    
    return tokens


async def run_solana_demo():
    """Run a demo of the Solana streaming agent with multiple strategies."""
    log.info("🚀 Starting Solana Trading Agent Demo")
    log.info("=" * 60)
    
    # Get tokens to trade
    tokens = get_tokens_from_env()
    log.info(f"Trading tokens: {tokens}")
    
    # Create data provider
    data_provider = DexScreenerSolanaProvider()
    
    # Create strategies to test
    strategies = [
        ("SMA Crossover", SmaCrossoverStrategy(fast=5, slow=15, min_confidence=0.6)),
        ("RSI Strategy", RsiStrategy(period=14, oversold=30, overbought=70)),
        ("Combo Strategy", ComboStrategy(fast=5, slow=15, rsi_period=10))
    ]
    
    # Test each strategy briefly
    for strategy_name, strategy in strategies:
        log.info(f"\n📊 Testing {strategy_name}")
        log.info("-" * 40)
        
        # Create components
        executor = PaperBroker()
        filters = [
            ConfidenceFilter(min_confidence=0.5),
            VolatilityFilter(min_volatility=0.0001)  # Very low threshold for demo
        ]
        risk_manager = RiskManager(
            account_equity=float(os.getenv("RISK_EQUITY", "10000")),
            risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.01"))
        )
        
        # Create streaming agent
        agent = SolanaStreamingAgent(
            data_provider=data_provider,
            strategy=strategy,
            executor=executor,
            filters=filters,
            risk_manager=risk_manager,
            min_price_change_threshold=float(os.getenv("MIN_PRICE_CHANGE_THRESHOLD", "0.001"))
        )
        
        # Run for a short time (60 seconds)
        try:
            await agent.run_streaming(tokens, interval_sec=15, max_duration_sec=60)
        except Exception as e:
            log.error(f"Error running {strategy_name}: {e}")
        
        # Small delay between strategies
        await asyncio.sleep(2)
    
    log.info("\n🎉 Demo completed!")


async def run_single_cycle():
    """Run a single cycle to test the system without continuous streaming."""
    log.info("🔄 Running single cycle test")
    
    tokens = get_tokens_from_env()
    
    # Create components
    data_provider = DexScreenerSolanaProvider()
    strategy = RsiStrategy(period=14, oversold=35, overbought=65)
    executor = PaperBroker()
    filters = [ConfidenceFilter(min_confidence=0.4)]
    risk_manager = RiskManager(account_equity=5000, risk_per_trade=0.005)
    
    # Create agent
    agent = SolanaStreamingAgent(
        data_provider=data_provider,
        strategy=strategy,
        executor=executor,
        filters=filters,
        risk_manager=risk_manager
    )
    
    # Run single cycle
    results = await agent.run_single_cycle(tokens, interval_sec=10)
    
    # Print results
    log.info(f"\\n📊 Single Cycle Results ({len(results)} tokens):")
    for result in results:
        token = result.get("token", "Unknown")
        signal = result.get("signal", "flat").upper()
        price = result.get("price")
        executed = result.get("executed", False)
        
        status = "✅ EXECUTED" if executed else "⏸️ SKIPPED"
        price_str = f"${price:.6f}" if price else "N/A"
        
        log.info(f"  {status} | {token} {signal} | Price: {price_str}")


async def run_continuous_trading(duration_minutes: int = 60):
    """Run continuous trading for a specified duration."""
    log.info(f"🔄 Starting continuous trading for {duration_minutes} minutes")
    
    tokens = get_tokens_from_env()
    
    # Create components with more conservative settings for longer runs
    data_provider = DexScreenerSolanaProvider()
    strategy = ComboStrategy(fast=8, slow=21, rsi_period=14)  # Slightly more responsive
    executor = PaperBroker()
    filters = [
        BasicTimeFilter(start_hour_utc=0, end_hour_utc=24),  # Allow all hours
        ConfidenceFilter(min_confidence=0.65),  # Higher confidence threshold
        VolatilityFilter(min_volatility=0.002)   # Require some volatility
    ]
    risk_manager = RiskManager(
        account_equity=float(os.getenv("RISK_EQUITY", "10000")),
        risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.01"))
    )
    
    # Create agent
    agent = SolanaStreamingAgent(
        data_provider=data_provider,
        strategy=strategy,
        executor=executor,
        filters=filters,
        risk_manager=risk_manager,
        min_price_change_threshold=0.005  # Higher threshold for longer runs
    )
    
    # Run for specified duration
    await agent.run_streaming(
        tokens, 
        interval_sec=30,  # 30-second intervals
        max_duration_sec=duration_minutes * 60
    )


async def main():
    """Main entry point with command line argument handling."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Solana Trading Agent using Dexscreener API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent.solana_main --demo
  python -m agent.solana_main --single-cycle  
  python -m agent.solana_main --continuous --duration 30
  python -m agent.solana_main --continuous --duration 120
        """
    )
    
    parser.add_argument(
        "--demo",
        action="store_true", 
        help="Run demo with all strategies (60s each)"
    )
    
    parser.add_argument(
        "--single-cycle",
        action="store_true",
        help="Run a single data fetching and processing cycle"
    )
    
    parser.add_argument(
        "--continuous", 
        action="store_true",
        help="Run continuous trading"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in minutes for continuous trading (default: 60)"
    )
    
    args = parser.parse_args()
    
    if args.demo:
        await run_solana_demo()
    elif args.single_cycle:
        await run_single_cycle()
    elif args.continuous:
        await run_continuous_trading(args.duration)
    else:
        # Default: run demo
        log.info("No specific mode selected, running demo...")
        await run_solana_demo()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("\\n👋 Goodbye!")
    except Exception as e:
        log.error(f"💥 Unexpected error: {e}")
        raise
