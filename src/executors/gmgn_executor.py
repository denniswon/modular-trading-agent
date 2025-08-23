import os, aiohttp
from src.utils.logging_utils import JsonLogger

GMGN_BASE = "https://gmgn.ai/api/solana/v1"

class GMGNExecutor:
    def __init__(self, cfg, wallet, logger: JsonLogger):
        self.cfg = cfg
        self.wallet = wallet
        self.log = logger
        self.api_key = os.getenv("GMGN_API_KEY","")

    async def build_and_execute_buy(self, session: aiohttp.ClientSession, in_mint: str, out_mint: str, amount_in_atomic: int):
        url = f"{GMGN_BASE}/swap/build"
        payload = {
            "userPublicKey": str(self.wallet.pubkey),
            "inputMint": in_mint,
            "outputMint": out_mint,
            "amount": str(amount_in_atomic),
            "slippageBps": int(self.cfg["execution"]["slippage_bps"]),
            "computeUnitPriceMicroLamports": int(self.cfg["execution"]["priority_fee_micro_lamports"])
        }
        headers = {"Content-Type":"application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with session.post(url, json=payload, headers=headers, timeout=30) as r:
            js = await r.json()
            if r.status != 200:
                self.log.log("ERROR","GMGN build error", status=r.status, resp=js)
                return None
            tx_b64 = js.get("transaction") or js.get("tx") or js.get("swapTransaction")
            if not tx_b64:
                self.log.log("ERROR","GMGN missing transaction in response", resp=js)
                return None
            sig = await self.wallet.sign_and_send(tx_b64)
            self.log.log("INFO","GMGN buy sent", signature=sig, out_mint=out_mint, amount=amount_in_atomic)
            return sig
