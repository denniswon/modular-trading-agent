import os, aiohttp
from src.utils.logging_utils import JsonLogger

RUGCHECK = os.getenv("RUGCHECK_URL", "https://api.rugcheck.xyz/v1/tokens")
BUBBLEMAPS = os.getenv("BUBBLEMAPS_URL", "https://api.bubblemaps.io/solana")

class Validators:
    def __init__(self, cfg, logger: JsonLogger):
        self.cfg = cfg
        self.log = logger

    async def rugcheck_ok(self, session: aiohttp.ClientSession, mint: str) -> bool:
        url = f"{RUGCHECK}/{mint}"
        try:
            async with session.get(url, timeout=20) as r:
                if r.status != 200:
                    self.log.log("WARN", "Rugcheck non-200", mint=mint, status=r.status)
                    return False
                js = await r.json()
                status = (js.get("status") or "").upper()
                if status != "GOOD":
                    self.log.log("WARN", "Rugcheck rejected", mint=mint, status=status, reason=js.get("reason"))
                    return False
                return True
        except Exception as e:
            self.log.log("ERROR", "Rugcheck fetch error", mint=mint, err=str(e))
            return False

    async def bubblemaps_ok(self, session: aiohttp.ClientSession, mint: str) -> bool:
        # expects API that returns top holders concentration in % for mint
        url = f"{BUBBLEMAPS}/holders/{mint}"
        try:
            async with session.get(url, timeout=20) as r:
                if r.status != 200:
                    self.log.log("WARN", "BubbleMaps non-200", mint=mint, status=r.status)
                    return False
                js = await r.json()
                # pseudo: expect 'top10_pct'
                top10 = float(js.get("top10_pct", 100.0))
                thresh = float(self.cfg["filters"]["bubblemaps_top10_max_pct"])
                ok = top10 <= thresh
                if not ok:
                    self.log.log("WARN", "BubbleMaps concentration too high", mint=mint, top10_pct=top10, thresh=thresh)
                return ok
        except Exception as e:
            self.log.log("ERROR", "BubbleMaps fetch error", mint=mint, err=str(e))
            return False
