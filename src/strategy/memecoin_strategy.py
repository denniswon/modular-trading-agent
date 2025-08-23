from collections import deque
from dataclasses import dataclass
from typing import Optional

@dataclass
class Signal:
    mint: str
    symbol: str
    price: float
    entry: float
    stop: float
    target: float
    rr_ratio: float
    position_size_sol: float
    expected_duration_days: int

class RollingStats:
    def __init__(self, ma_window: int, atr_window: int):
        self.ma_window = ma_window
        self.atr_window = atr_window
        self.prices = deque(maxlen=ma_window)
        self.trs = deque(maxlen=atr_window)
        self.prev_close: Optional[float] = None

    def update(self, price: float) -> None:
        if self.prev_close is not None:
            tr = abs(price - self.prev_close)
            self.trs.append(tr)
        self.prices.append(price)
        self.prev_close = price

    @property
    def ma(self) -> Optional[float]:
        if len(self.prices) < self.prices.maxlen:
            return None
        return sum(self.prices)/len(self.prices)

    @property
    def atr(self) -> Optional[float]:
        if len(self.trs) < self.trs.maxlen:
            return None
        return sum(self.trs)/len(self.trs)

class Strategy:
    def __init__(self, cfg):
        st = cfg["strategy"]
        self.ma_window = int(st["ma_window"])
        self.atr_window = int(st["atr_window"])
        self.rr_floor = float(st["rr_floor"])
        self.risk = cfg["risk"]
        self.stats = {}

    def _stats(self, mint: str) -> RollingStats:
        if mint not in self.stats:
            self.stats[mint] = RollingStats(self.ma_window, self.atr_window)
        return self.stats[mint]

    def on_tick(self, mint: str, symbol: str, price: float, sol_balance: float) -> Optional[Signal]:
        rs = self._stats(mint)
        rs.update(price)
        ma = rs.ma
        atr = rs.atr
        if ma is None or atr is None:
            return None

        # simple long bias if price > MA
        if price <= ma:
            return None

        stop = max(price * (1 - self.risk["base_stop_pct"]/100.0), price - 2*atr)
        target = max(price * (1 + self.risk["base_target_pct"]/100.0), price + 3*atr)
        risk_per_unit = price - stop
        reward_per_unit = target - price
        if risk_per_unit <= 0:
            return None
        rr = reward_per_unit / risk_per_unit
        if rr < self.rr_floor:
            return None

        # position sizing
        max_risk_sol = sol_balance * (self.risk["max_account_risk_pct"]/100.0)
        units = max_risk_sol / risk_per_unit if risk_per_unit > 0 else 0.0
        pos_sol = max(0.0, units)

        return Signal(
            mint=mint, symbol=symbol, price=price, entry=price, stop=stop, target=target,
            rr_ratio=rr, position_size_sol=pos_sol, expected_duration_days=3
        )
