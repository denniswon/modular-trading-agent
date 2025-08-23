import os, asyncio, aiohttp
from src.utils.logging_utils import JsonLogger
from src.data_providers.dexscreener_ws import DexScreenerWS
from src.agents.validators import Validators
from src.strategy.memecoin_strategy import Strategy
from src.utils.prices import get_sol_price_usd
from src.executors.solana_wallet import SolanaWallet
from src.executors.gmgn_executor import GMGNExecutor
from src.executors.photon_executor import PhotonExecutor

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
WSOL = "So11111111111111111111111111111111111111112"

class TradingAgent:
    def __init__(self, cfg):
        self.cfg = cfg
        self.log = JsonLogger()
        self.ds = DexScreenerWS(self.log)
        self.validators = Validators(cfg, self.log)
        self.strategy = Strategy(cfg)
        self.auto = bool(cfg.get("auto_execute", False))
        self.wallet = SolanaWallet(os.getenv("SOLANA_RPC_URL","https://api.mainnet-beta.solana.com"), cfg["wallet"]["key_name"])
        self.gmgn = GMGNExecutor(cfg, self.wallet, self.log)
        self.photon = PhotonExecutor(cfg, self.wallet, self.log)
        self.preferred_mints = cfg.get("preferred_input_mints", [USDC, WSOL])

    async def _choose_in_mint(self, session: aiohttp.ClientSession) -> str:
        # pick USDC if available (assumed), otherwise WSOL
        return self.preferred_mints[0]

    async def run(self):
        await self.wallet.connect()
        async with aiohttp.ClientSession() as session:
            sol_price = await get_sol_price_usd(session)
            self.log.log("INFO","SOL price loaded", sol_price=sol_price)

            async for ev in self.ds.stream_solana_pairs():
                # Expect ev to contain pairs; here we simulate a simplified structure
                pairs = ev.get("pairs") or []
                for p in pairs:
                    try:
                        mint = p.get("baseToken",{}).get("address") or p.get("pair","")
                        symbol = p.get("baseToken",{}).get("symbol","?")
                        price = float(p.get("priceUsd") or p.get("price","0") or 0.0)
                        liq = float(p.get("liquidity",{}).get("usd", 0.0))
                        fdv = float(p.get("fdv", 0.0))
                        age_h = float(p.get("pairCreatedAt",0))/3600000.0 if p.get("pairCreatedAt") else 0.0
                        tx1h = int(p.get("txns",{}).get("h1",{}).get("buys",0)) + int(p.get("txns",{}).get("h1",{}).get("sells",0))

                        f = self.cfg["filters"]
                        if liq < f["min_liquidity_usd"] or fdv < f["min_fdv_usd"] or age_h > f["max_pair_age_hours"] or tx1h < f["min_txns_last_hour"]:
                            continue

                        # Rug gates
                        if not await self.validators.rugcheck_ok(session, mint):
                            continue
                        if not await self.validators.bubblemaps_ok(session, mint):
                            continue

                        # Strategy
                        # fake SOL balance read: you can wire RPC balance call here; assume 10 SOL for sizing
                        sol_balance = 10.0
                        sig = self.strategy.on_tick(mint, symbol, price, sol_balance)
                        if not sig:
                            continue

                        self.log.log("INFO","Signal", mint=mint, symbol=symbol, price=price, rr=sig.rr_ratio, pos_sol=sig.position_size_sol)

                        if not self.auto:
                            continue

                        in_mint = await self._choose_in_mint(session)

                        # Convert position_size_sol (in USD) to amount in in_mint atomic
                        # If USDC, 6 decimals, assume 1 USDC = 1 USD
                        if in_mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":
                            decimals = 6
                            amount_in = int(max(1, round(sig.position_size_sol * sol_price * (10**decimals))))
                        else:
                            # WSOL
                            decimals = 9
                            amount_in = int(max(1, round(sig.position_size_sol * (10**decimals))))

                        # Try GMGN then Photon
                        ok = await self.gmgn.build_and_execute_buy(session, in_mint, mint, amount_in)
                        if not ok:
                            await self.photon.build_and_execute_buy(session, in_mint, mint, amount_in)

                    except Exception as e:
                        self.log.log("ERROR","tick error", err=str(e))
