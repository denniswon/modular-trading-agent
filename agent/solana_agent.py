"""
Async Solana trading agent.

This module implements an async trading agent that can handle continuous data streams
from Dexscreener and execute trades based on live token data.
"""

import asyncio
import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from agent.base import AsyncMarketDataProvider, SignalProcessor, TradeExecutor, PreTradeFilter, MarketSnapshot, Candle, Signal, OrderRequest
from agent.risk_manager import RiskManager
from agent.types import TokenTick

# Setup logging
log = logging.getLogger(__name__)


class SolanaStreamingAgent:
    """
    Async trading agent for Solana tokens using streaming data from Dexscreener.
    
    Features:
    - Handles continuous data streams from Dexscreener API
    - Converts TokenTick data to MarketSnapshot for strategy compatibility
    - Supports filtering and risk management
    - Logs all trading decisions and executions
    """

    def __init__(
        self,
        data_provider: AsyncMarketDataProvider,
        strategy: SignalProcessor,
        executor: TradeExecutor,
        filters: Optional[List[PreTradeFilter]] = None,
        risk_manager: Optional[RiskManager] = None,
        min_price_change_threshold: float = 0.001,  # Minimum price change to trigger signal generation
    ):
        """
        Initialize the Solana streaming agent.
        
        Args:
            data_provider: Async data provider (e.g., DexScreenerSolanaProvider)
            strategy: Signal generation strategy
            executor: Trade executor
            filters: Optional pre-trade filters
            risk_manager: Risk management for position sizing
            min_price_change_threshold: Minimum price change to process (reduces noise)
        """
        self.data_provider = data_provider
        self.strategy = strategy
        self.executor = executor
        self.filters = filters or []
        self.risk_manager = risk_manager
        self.min_price_change_threshold = min_price_change_threshold
        
        # Track price history for creating MarketSnapshot objects
        self._price_history: Dict[str, List[Candle]] = {}
        self._last_prices: Dict[str, float] = {}
        
        log.info(f"Initialized SolanaStreamingAgent with {len(self.filters)} filters")

    def _tick_to_candle(self, tick: TokenTick) -> Candle:
        """
        Convert a TokenTick to a Candle for strategy compatibility.
        
        Since ticks don't have OHLC data, we create a synthetic candle
        where open = high = low = close = current price.
        
        Args:
            tick: TokenTick from data provider
            
        Returns:
            Candle object for strategy processing
        """
        price = tick.price_usd or 0.0
        volume = tick.volume_24h_usd or 0.0
        timestamp = tick.timestamp or datetime.utcnow()
        
        return Candle(
            ts=timestamp,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=volume
        )

    def _update_price_history(self, tick: TokenTick, max_history: int = 200) -> MarketSnapshot:
        """
        Update price history and create MarketSnapshot for the token.
        
        Args:
            tick: Latest token tick data
            max_history: Maximum number of candles to keep in history
            
        Returns:
            MarketSnapshot with recent price history
        """
        token = tick.token
        candle = self._tick_to_candle(tick)
        
        # Initialize history if needed
        if token not in self._price_history:
            self._price_history[token] = []
        
        # Add new candle
        self._price_history[token].append(candle)
        
        # Keep only recent history
        if len(self._price_history[token]) > max_history:
            self._price_history[token] = self._price_history[token][-max_history:]
        
        return MarketSnapshot(symbol=token, candles=self._price_history[token])

    def _should_process_tick(self, tick: TokenTick) -> bool:
        """
        Determine if a tick should be processed for signal generation.
        
        Filters out ticks with insufficient price changes to reduce noise.
        
        Args:
            tick: Token tick to evaluate
            
        Returns:
            True if tick should be processed
        """
        if tick.price_usd is None:
            return False
            
        token = tick.token
        current_price = tick.price_usd
        
        # Always process first tick for a token
        if token not in self._last_prices:
            self._last_prices[token] = current_price
            return True
        
        # Check if price change is significant enough
        last_price = self._last_prices[token]
        if last_price > 0:
            price_change = abs(current_price - last_price) / last_price
            if price_change >= self.min_price_change_threshold:
                self._last_prices[token] = current_price
                return True
        
        return False

    async def _process_tick(self, tick_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single tick and potentially generate/execute trades.
        
        Args:
            tick_data: Raw tick data dict from data provider
            
        Returns:
            Processing result summary or None
        """
        try:
            # Parse tick data
            tick = TokenTick(**tick_data)
            
            # Skip if not worth processing
            if not self._should_process_tick(tick):
                return None
            
            # Update price history and create snapshot
            snapshot = self._update_price_history(tick)
            
            # Generate signal
            signal = self.strategy.generate(snapshot)
            
            # Apply filters
            for filter_obj in self.filters:
                if not filter_obj.allow(snapshot, signal):
                    log.debug(f"Signal for {tick.token} blocked by {filter_obj.__class__.__name__}")
                    return {
                        "token": tick.token,
                        "signal": signal.side,
                        "confidence": signal.confidence,
                        "price": tick.price_usd,
                        "filtered": True,
                        "filter": filter_obj.__class__.__name__
                    }
            
            # Only proceed if signal is actionable
            if signal.side in ("buy", "sell"):
                # Calculate position size using risk manager
                size = 0.0
                if self.risk_manager and tick.price_usd:
                    # Simple position sizing: risk 1.5% below/above current price
                    entry_price = tick.price_usd
                    if signal.side == "buy":
                        stop_price = entry_price * 0.985  # 1.5% below
                    else:
                        stop_price = entry_price * 1.015  # 1.5% above
                    
                    size = self.risk_manager.position_size(entry_price, stop_price)
                else:
                    size = 100.0  # Default size if no risk manager
                
                if size > 0:
                    # Create order request
                    order = OrderRequest(
                        symbol=tick.token,
                        side=signal.side,
                        size=size,
                        order_type="market",
                        meta={
                            "confidence": signal.confidence,
                            "price": tick.price_usd,
                            "liquidity": tick.liquidity_usd,
                            "volume_24h": tick.volume_24h_usd,
                            "slot": tick.slot,
                            "signal_meta": signal.meta
                        }
                    )
                    
                    # Execute order
                    result = self.executor.place_order(order)
                    
                    return {
                        "token": tick.token,
                        "signal": signal.side,
                        "confidence": signal.confidence,
                        "price": tick.price_usd,
                        "size": size,
                        "executed": result.ok,
                        "order_id": result.order_id,
                        "error": result.error,
                        "liquidity": tick.liquidity_usd,
                        "rpc_healthy": tick.rpc_healthy,
                        "slot": tick.slot
                    }
            
            # Flat signal or no execution
            return {
                "token": tick.token,
                "signal": signal.side,
                "confidence": signal.confidence,
                "price": tick.price_usd,
                "executed": False,
                "reason": "flat_signal" if signal.side == "flat" else "no_position_size"
            }
            
        except Exception as e:
            log.error(f"Error processing tick: {e}")
            return {
                "error": str(e),
                "tick_data": tick_data
            }

    async def run_streaming(
        self, 
        tokens: List[str], 
        interval_sec: int = 10,
        max_duration_sec: Optional[int] = None
    ) -> None:
        """
        Run the streaming trading agent.
        
        Args:
            tokens: List of token identifiers to track
            interval_sec: Update interval in seconds
            max_duration_sec: Optional maximum duration to run (None = indefinite)
        """
        log.info(f"Starting Solana streaming agent for {len(tokens)} tokens")
        log.info(f"Tokens: {', '.join(tokens)}")
        log.info(f"Interval: {interval_sec}s, Max duration: {max_duration_sec}s")
        
        start_time = datetime.utcnow()
        processed_count = 0
        executed_trades = 0
        
        try:
            async for tick_data in self.data_provider.subscribe_ticks(tokens, interval_sec):
                # Check duration limit
                if max_duration_sec:
                    elapsed = (datetime.utcnow() - start_time).total_seconds()
                    if elapsed >= max_duration_sec:
                        log.info(f"Reached maximum duration of {max_duration_sec}s, stopping")
                        break
                
                # Process the tick
                result = await self._process_tick(tick_data)
                if result:
                    processed_count += 1
                    
                    # Log interesting results
                    if result.get("executed"):
                        executed_trades += 1
                        log.info(f"💰 EXECUTED: {result['signal'].upper()} {result['token']} "
                                f"${result['price']:.6f} size={result['size']:.2f} "
                                f"conf={result['confidence']:.2%} id={result['order_id']}")
                    elif result.get("filtered"):
                        log.debug(f"🚫 FILTERED: {result['signal'].upper()} {result['token']} "
                                 f"by {result['filter']}")
                    elif result.get("signal") != "flat":
                        log.debug(f"⏸️ SKIPPED: {result['signal'].upper()} {result['token']} "
                                 f"${result['price']:.6f} - {result.get('reason', 'unknown')}")
                    
                    # Print summary every 50 ticks
                    if processed_count % 50 == 0:
                        log.info(f"📊 Processed {processed_count} signals, executed {executed_trades} trades")
                        
        except KeyboardInterrupt:
            log.info("\n🛑 Streaming agent stopped by user")
        except Exception as e:
            log.error(f"💥 Unexpected error in streaming agent: {e}")
            raise
        finally:
            # Final summary
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            log.info(f"\n📈 Final Summary:")
            log.info(f"   Runtime: {elapsed:.1f}s")
            log.info(f"   Signals processed: {processed_count}")
            log.info(f"   Trades executed: {executed_trades}")
            log.info(f"   Success rate: {executed_trades/processed_count*100:.1f}%" if processed_count > 0 else "   No signals processed")

    async def run_single_cycle(
        self, 
        tokens: List[str], 
        interval_sec: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Run a single cycle of data fetching and processing.
        
        Useful for testing or one-off analysis.
        
        Args:
            tokens: List of token identifiers
            interval_sec: Interval for data fetching
            
        Returns:
            List of processing results
        """
        log.info(f"Running single cycle for {len(tokens)} tokens")
        results = []
        
        # Get one batch of ticks
        async for tick_data in self.data_provider.subscribe_ticks(tokens, interval_sec):
            result = await self._process_tick(tick_data)
            if result:
                results.append(result)
            
            # Stop after getting data for all tokens
            if len(results) >= len(tokens):
                break
        
        log.info(f"Single cycle completed: {len(results)} results")
        return results
