import os, asyncio, json, websockets
from src.utils.logging_utils import JsonLogger

DEX_WS = os.getenv("DEXSCREENER_WS", "wss://io.dexscreener.com/dex/screener/v1/subscribe")

class DexScreenerWS:
    def __init__(self, logger: JsonLogger):
        self.log = logger

    async def stream_solana_pairs(self):
        # simplified subscription payload
        sub = {"method": "subscribe", "params": {"chain": "solana"}}
        while True:
            try:
                async with websockets.connect(DEX_WS, ping_interval=20) as ws:
                    await ws.send(json.dumps(sub))
                    async for msg in ws:
                        try:
                            js = json.loads(msg)
                            yield js
                        except Exception as e:
                            self.log.log("ERROR", "WS parse error", err=str(e))
            except Exception as e:
                self.log.log("ERROR", "WS error; retrying", err=str(e))
                await asyncio.sleep(3)
