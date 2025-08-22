"""
Command-line interface for transaction execution.

This module provides a CLI for executing trades through various DEX aggregators
including Photon and GMGN with comprehensive logging and error handling.
"""

import asyncio
import json
import os
from typing import Literal, Optional
import argparse
import sys

from dotenv import load_dotenv
from pydantic import ValidationError

from agent.executor_base import ExecutionRequest, QuoteRequest, TransactionType
from agent.executors import PhotonExecutor, GmgnExecutor, AutoExecutor
from agent.tx_logger import TxLogger, set_global_logger


# Common Solana token addresses for convenience
COMMON_TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
}


def resolve_token_address(token: str) -> str:
    """Resolve a token symbol to its mint address."""
    if token.upper() in COMMON_TOKENS:
        return COMMON_TOKENS[token.upper()]
    return token


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Execute Solana token trades through DEX aggregators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simulate a SOL -> USDC swap (default)
  python -m agent.execute_trade --from SOL --to USDC --amount 0.1

  # Execute real trade with Photon
  python -m agent.execute_trade --provider photon --from SOL --to BONK \\
    --amount 0.05 --simulate false --wallet YOUR_PUBKEY

  # Get quote only
  python -m agent.execute_trade --quote-only --from USDC --to WIF --amount 10

  # Use AutoExecutor with best price strategy
  python -m agent.execute_trade --provider auto --strategy best_price \\
    --from SOL --to RAY --amount 0.1 --limit-price 0.15

Environment Variables:
  OWNER_PUBKEY           - Your Solana wallet public key
  SOLANA_SECRET_KEY_B58  - Your private key in base58 (for real trades)
  SOLANA_RPC             - Solana RPC endpoint
  PHOTON_API_KEY         - Photon API key (optional)
  GMGN_API_KEY          - GMGN API key (optional)
  LOG_LEVEL             - Logging level (DEBUG, INFO, WARNING, ERROR)
        """
    )
    
    # Core trading parameters
    parser.add_argument(
        "--provider", "-p",
        choices=["auto", "photon", "gmgn"],
        default="auto",
        help="DEX aggregator to use (default: auto)"
    )
    
    parser.add_argument(
        "--from", "--token-in",
        dest="token_in",
        required=True,
        help="Input token symbol or mint address"
    )
    
    parser.add_argument(
        "--to", "--token-out",
        dest="token_out",
        required=True,
        help="Output token symbol or mint address"
    )
    
    parser.add_argument(
        "--amount", "-a",
        type=float,
        required=True,
        help="Amount to trade in UI units (e.g., 0.1 for 0.1 SOL)"
    )
    
    parser.add_argument(
        "--wallet", "--owner-pubkey",
        dest="owner_pubkey",
        help="Wallet public key (from env OWNER_PUBKEY if not provided)"
    )
    
    # Trading parameters
    parser.add_argument(
        "--slippage",
        type=float,
        default=1.0,
        help="Slippage tolerance in percent (default: 1.0)"
    )
    
    parser.add_argument(
        "--priority-fee",
        type=int,
        default=0,
        help="Priority fee in lamports (default: 0)"
    )
    
    parser.add_argument(
        "--limit-price",
        type=float,
        help="Maximum price per token in USD"
    )
    
    # Execution options
    parser.add_argument(
        "--simulate",
        type=str,
        choices=["true", "false"],
        default="true",
        help="Simulate only (true) or execute real trade (false)"
    )
    
    parser.add_argument(
        "--quote-only",
        action="store_true",
        help="Get quote only, don't execute trade"
    )
    
    parser.add_argument(
        "--strategy",
        choices=["first_success", "best_price", "fastest"],
        default="first_success",
        help="AutoExecutor routing strategy (default: first_success)"
    )
    
    # System options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--output-format",
        choices=["json", "human"],
        default="human",
        help="Output format (default: human)"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)"
    )
    
    return parser.parse_args()


def format_amount_atomic(amount_ui: float, token_address: str) -> int:
    """
    Convert UI amount to atomic units.
    
    This is a simplified version - in production you'd want to
    fetch the actual token decimals from the blockchain.
    """
    # Common token decimals
    token_decimals = {
        COMMON_TOKENS["SOL"]: 9,     # SOL
        COMMON_TOKENS["USDC"]: 6,    # USDC
        COMMON_TOKENS["USDT"]: 6,    # USDT
        COMMON_TOKENS["RAY"]: 6,     # RAY
        COMMON_TOKENS["BONK"]: 5,    # BONK
        COMMON_TOKENS["WIF"]: 6,     # WIF
    }
    
    decimals = token_decimals.get(token_address, 6)  # Default to 6 decimals
    return int(amount_ui * (10 ** decimals))


async def execute_quote(args, executor):
    """Execute a quote request."""
    token_in = resolve_token_address(args.token_in)
    token_out = resolve_token_address(args.token_out)
    amount_atomic = format_amount_atomic(args.amount, token_in)
    
    quote_req = QuoteRequest(
        token_in_mint=token_in,
        token_out_mint=token_out,
        amount_in_atomic=amount_atomic,
        slippage_bps=int(args.slippage * 100)  # Convert percent to bps
    )
    
    print(f"Getting quote: {args.amount} {args.token_in} -> {args.token_out}")
    print(f"Provider: {executor.name}")
    print("-" * 50)
    
    result = await executor.get_quote(quote_req)
    
    if args.output_format == "json":
        print(json.dumps(result.model_dump(), indent=2))
    else:
        if result.ok:
            print(f"✅ Quote successful from {result.provider}")
            if result.price_usd:
                print(f"   Price: ${result.price_usd:.6f} per token")
            if result.amount_out:
                print(f"   Output: {result.amount_out} atomic units")
            if result.impact_bps:
                print(f"   Price Impact: {result.impact_bps / 100:.2f}%")
            if result.fee_usd:
                print(f"   Fee: ${result.fee_usd:.4f}")
        else:
            print(f"❌ Quote failed: {result.error}")
    
    return result.ok


async def execute_trade(args, executor):
    """Execute a trade request."""
    token_in = resolve_token_address(args.token_in)
    token_out = resolve_token_address(args.token_out)
    amount_atomic = format_amount_atomic(args.amount, token_in)
    simulate_only = args.simulate.lower() == "true"
    
    # Get owner pubkey
    owner_pubkey = args.owner_pubkey or os.getenv("OWNER_PUBKEY")
    if not owner_pubkey:
        print("❌ Error: Owner public key required. Set --wallet or OWNER_PUBKEY env var.")
        return False
    
    execution_req = ExecutionRequest(
        owner_pubkey=owner_pubkey,
        token_in_mint=token_in,
        token_out_mint=token_out,
        amount_in_atomic=amount_atomic,
        transaction_type=TransactionType.BUY,
        limit_price_usd=args.limit_price,
        slippage_bps=int(args.slippage * 100),
        priority_fee_lamports=args.priority_fee,
        simulate_only=simulate_only,
        timeout_seconds=args.timeout,
        strategy_name="cli",
        metadata={"source": "execute_trade_cli"}
    )
    
    action = "Simulating" if simulate_only else "Executing"
    print(f"{action} trade: {args.amount} {args.token_in} -> {args.token_out}")
    print(f"Provider: {executor.name}")
    print(f"Wallet: {owner_pubkey}")
    print(f"Slippage: {args.slippage}%")
    if args.limit_price:
        print(f"Limit Price: ${args.limit_price}")
    print("-" * 50)
    
    result = await executor.execute_buy(execution_req)
    
    if args.output_format == "json":
        print(json.dumps(result.model_dump(), indent=2))
    else:
        if result.ok:
            print(f"✅ Trade successful from {result.provider}")
            if result.price_usd:
                print(f"   Price: ${result.price_usd:.6f} per token")
            if result.amount_out:
                print(f"   Output: {result.amount_out} atomic units")
            if result.tx_sig:
                print(f"   Transaction: {result.tx_sig}")
                print(f"   Explorer: https://solscan.io/tx/{result.tx_sig}")
            if result.execution_time_ms:
                print(f"   Execution Time: {result.execution_time_ms}ms")
        else:
            print(f"❌ Trade failed: {result.error}")
    
    return result.ok


async def main():
    """Main CLI entry point."""
    # Load environment
    load_dotenv()
    
    # Parse arguments
    args = parse_args()
    
    # Setup logging
    logger = TxLogger(level=args.log_level)
    set_global_logger(logger)
    
    # Create executor
    if args.provider == "photon":
        executor = PhotonExecutor()
    elif args.provider == "gmgn":
        executor = GmgnExecutor()
    else:  # auto
        executor = AutoExecutor(strategy=args.strategy)
    
    success = False
    
    try:
        async with executor:
            if args.quote_only:
                success = await execute_quote(args, executor)
            else:
                success = await execute_trade(args, executor)
    
    except ValidationError as e:
        print(f"❌ Validation Error: {e}")
        return 1
    
    except KeyboardInterrupt:
        print("\\n⏹️ Execution cancelled by user")
        return 1
    
    except Exception as e:
        print(f"💥 Unexpected error: {type(e).__name__}: {e}")
        logger.error(f"CLI execution failed: {e}")
        return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
