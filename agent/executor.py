"""
Trade executors.

Includes a simple paper broker that immediately fills orders.
"""

import time
import logging
from typing import List
from .base import TradeExecutor, OrderRequest, OrderResult

log = logging.getLogger("bot")


class PaperBroker(TradeExecutor):
    """Mock broker: records trades, returns fills at last price."""

    def __init__(self):
        self._orders: List[OrderResult] = []

    def place_order(self, order: OrderRequest) -> OrderResult:
        # Fill instantly at limit or leave filled_price None for market
        fill_price = order.limit_price if order.order_type == "limit" else None
        result = OrderResult(
            ok=True,
            order_id=f"paper-{int(time.time()*1000)}",
            filled_price=fill_price,
            filled_size=order.size,
            meta={"echo": order.meta}
        )
        self._orders.append(result)
        log.info(f"[PaperBroker] Placed {order.side.upper()} {order.size} {order.symbol} ({order.order_type})")
        return result
