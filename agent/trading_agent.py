"""
Main trading agent orchestrator.

This module coordinates data fetch, signal generation, risk management and execution.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from .base import MarketDataProvider, SignalProcessor, TradeExecutor, PreTradeFilter, OrderRequest
from .risk_manager import RiskManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("bot")


class TradingAgent:
    """Coordinates data fetch, signal generation, risk & execution."""

    def __init__(
        self,
        data: MarketDataProvider,
        strategy: SignalProcessor,
        broker: TradeExecutor,
        filters: Optional[List[PreTradeFilter]] = None,
        risk: Optional[RiskManager] = None,
        poll_seconds: int = 5,
    ):
        """
        Initialize trading agent.
        
        Args:
            data: Market data provider
            strategy: Signal generation strategy
            broker: Trade execution broker
            filters: Optional list of pre-trade filters
            risk: Risk manager for position sizing
            poll_seconds: Polling interval for continuous trading
        """
        self.data = data
        self.strategy = strategy
        self.broker = broker
        self.filters = filters or []
        self.risk = risk or RiskManager(account_equity=10_000, risk_per_trade=0.01)
        self.poll_seconds = poll_seconds

    def _derive_trade_levels(self, price: float, side: str) -> Dict[str, float]:
        """
        Calculate entry, stop, and target levels for a trade.
        
        Example levels:
          - For BUY: entry at price, stop below 1.5%, target 3%
          - For SELL: mirrored levels
        
        Args:
            price: Current market price
            side: Trade side ('buy' or 'sell')
            
        Returns:
            Dictionary with entry, stop, and target levels
        """
        if side == "buy":
            entry = price
            stop = price * 0.985  # -1.5%
            target = price * 1.03  # +3.0%
        elif side == "sell":
            entry = price
            stop = price * 1.015
            target = price * 0.97
        else:
            entry = stop = target = price
        return {"entry": entry, "stop": stop, "target": target}

    def _risk_reward(self, entry: float, stop: float, target: float, side: str) -> float:
        """
        Calculate risk/reward ratio for a trade.
        
        Args:
            entry: Entry price
            stop: Stop loss price
            target: Target price
            side: Trade side ('buy' or 'sell')
            
        Returns:
            Risk/reward ratio
        """
        if side == "buy":
            risk = max(1e-9, entry - stop)
            reward = max(0.0, target - entry)
        else:
            risk = max(1e-9, stop - entry)
            reward = max(0.0, entry - target)
        return reward / risk if risk > 0 else 0.0

    def run_once(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Run a single evaluation over symbols.
        
        Args:
            symbols: List of trading symbols to evaluate
            
        Returns:
            List of JSON-serializable summaries of signals considered
        """
        summaries: List[Dict[str, Any]] = []

        for symbol in symbols:
            try:
                # Fetch market data
                snap = self.data.get_snapshot(symbol, lookback=200, timeframe="1h")
                signal = self.strategy.generate(snap)

                # Apply filters
                filtered = False
                for filter_obj in self.filters:
                    if not filter_obj.allow(snap, signal):
                        log.info(f"[Filter] Blocked {signal.side} signal for {symbol} by {filter_obj.__class__.__name__}")
                        filtered = True
                        break

                if filtered:
                    continue

                price = snap.candles[-1].close
                levels = self._derive_trade_levels(price, signal.side)
                rr = self._risk_reward(levels["entry"], levels["stop"], levels["target"], signal.side)

                # Position sizing via risk manager
                size = 0.0
                if signal.side in ("buy", "sell"):
                    size = self.risk.position_size(levels["entry"], levels["stop"])

                summary = {
                    "symbol": symbol,
                    "side": signal.side,
                    "confidence": round(signal.confidence, 3),
                    "price": round(price, 4),
                    "entry": round(levels["entry"], 4),
                    "stop": round(levels["stop"], 4),
                    "target": round(levels["target"], 4),
                    "rr_ratio": round(rr, 2),
                    "size_units": round(size, 4),
                    "meta": signal.meta,
                }
                summaries.append(summary)

                # Example execution rule: only take trades with RR >= 1.5 and confidence >= 0.6
                if signal.side in ("buy", "sell") and rr >= 1.5 and signal.confidence >= 0.6 and size > 0:
                    order = OrderRequest(
                        symbol=symbol,
                        side=signal.side,
                        size=size,
                        order_type="market",
                        meta={"rr": rr, "confidence": signal.confidence},
                    )
                    res = self.broker.place_order(order)
                    summary["order_result"] = {
                        "ok": res.ok,
                        "order_id": res.order_id,
                        "filled_price": res.filled_price,
                        "error": res.error,
                    }
                else:
                    summary["order_result"] = {"ok": False, "reason": "did_not_meet_rules"}

            except Exception as e:
                log.error(f"Error processing {symbol}: {e}")
                summaries.append({
                    "symbol": symbol,
                    "error": str(e),
                    "order_result": {"ok": False, "reason": "processing_error"}
                })

        return summaries

    def run_loop(self, symbols: List[str], iterations: int = 3):
        """
        Simple loop runner (blocking).
        
        Args:
            symbols: List of trading symbols
            iterations: Number of iterations to run
        """
        log.info(f"🚀 Starting trading agent with {len(symbols)} symbols for {iterations} iterations")
        
        for i in range(iterations):
            log.info(f"--- Iteration {i+1}/{iterations} ---")
            results = self.run_once(symbols)
            
            for result in results:
                if "error" in result:
                    log.error(f"❌ {result['symbol']}: {result['error']}")
                else:
                    side = result['side'].upper()
                    conf = result['confidence']
                    price = result['price']
                    rr = result['rr_ratio']
                    
                    order_status = "✅ EXECUTED" if result["order_result"]["ok"] else "⏸️ SKIPPED"
                    log.info(f"{order_status} | {result['symbol']} {side} | Price: {price} | Conf: {conf:.2%} | RR: {rr}")
                    
                    # Log order details if executed
                    if result["order_result"]["ok"]:
                        order_id = result["order_result"].get("order_id", "N/A")
                        log.info(f"         Order ID: {order_id}")
            
            # Wait before next iteration
            if i < iterations - 1:  # Don't sleep after the last iteration
                log.info(f"💤 Waiting {self.poll_seconds}s before next iteration...")
                time.sleep(self.poll_seconds)
        
        log.info("🏁 Trading agent completed all iterations")

    def run_continuous(self, symbols: List[str]):
        """
        Run continuously until interrupted.
        
        Args:
            symbols: List of trading symbols
        """
        log.info(f"🔄 Starting continuous trading with {len(symbols)} symbols")
        log.info("Press Ctrl+C to stop")
        
        iteration = 0
        try:
            while True:
                iteration += 1
                log.info(f"--- Continuous Iteration #{iteration} ---")
                results = self.run_once(symbols)
                
                for result in results:
                    if "error" in result:
                        log.error(f"❌ {result['symbol']}: {result['error']}")
                    else:
                        side = result['side'].upper()
                        conf = result['confidence']
                        price = result['price']
                        
                        order_status = "✅ EXECUTED" if result["order_result"]["ok"] else "⏸️ SKIPPED"
                        log.info(f"{order_status} | {result['symbol']} {side} | Price: {price} | Conf: {conf:.2%}")
                
                time.sleep(self.poll_seconds)
                
        except KeyboardInterrupt:
            log.info("\n⏹️ Trading agent stopped by user")
        except Exception as e:
            log.error(f"💥 Unexpected error: {e}")
            raise
