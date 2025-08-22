"""
DexScreener Solana market data provider.

This module implements an async MarketDataProvider that fetches live token data
from the Dexscreener API and maintains a Solana RPC connection for network health.
"""

import asyncio
import os
import random
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import aiohttp
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient

from agent.base import AsyncMarketDataProvider
from agent.types import TokenTick, SolanaHealthInfo

# Setup logging
log = logging.getLogger(__name__)

# Dexscreener API endpoints
DEXSCREENER_BASE = "https://api.dexscreener.com/latest/dex"


def _pick_best_pair(pairs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Pick the most relevant pair for trading metrics.
    
    Prefers highest liquidity in USD on Solana chain.
    
    Args:
        pairs: List of pair data from Dexscreener API
        
    Returns:
        Best pair dict or None if no suitable pairs found
    """
    best = None
    best_liq = -1.0
    
    for p in pairs or []:
        if p.get("chainId") != "solana":
            continue
            
        liq = 0.0
        liq_usd = p.get("liquidity", {}).get("usd")
        try:
            if liq_usd is not None:
                liq = float(liq_usd)
        except (ValueError, TypeError):
            liq = 0.0
            
        if liq > best_liq:
            best_liq = liq
            best = p
            
    return best


class DexScreenerSolanaProvider(AsyncMarketDataProvider):
    """
    Async market data provider that fetches live token data from Dexscreener API.
    
    Features:
    - Fetches live price, volume, liquidity, and 24h change data
    - Maintains Solana RPC connection for network health monitoring
    - Handles API rate limiting with jitter
    - Robust error handling with fallback data
    """

    def __init__(self, base_rpc: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None):
        """
        Initialize the provider.
        
        Args:
            base_rpc: Custom Solana RPC URL (defaults to mainnet-beta)
            session: Optional aiohttp session (will create if not provided)
        """
        load_dotenv()
        self._rpc_url = base_rpc or os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
        self._session = session
        self._own_session = session is None
        self._client: Optional[AsyncClient] = None
        
        log.info(f"Initialized DexScreenerSolanaProvider with RPC: {self._rpc_url}")

    async def _ensure_clients(self):
        """Ensure HTTP session and Solana RPC client are initialized."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=20, connect=5)
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=10)
            self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
            
        if self._client is None:
            self._client = AsyncClient(self._rpc_url)

    async def _close(self):
        """Clean up resources."""
        if self._client:
            await self._client.close()
            self._client = None
            
        if self._own_session and self._session:
            await self._session.close()
            self._session = None

    async def _fetch_token_best_pair(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the best trading pair for a token from Dexscreener API.
        
        Args:
            token: SPL mint address (preferred) or symbol
            
        Returns:
            Best pair data dict or None if not found
        """
        if self._session is None:
            raise RuntimeError("HTTP session not initialized")
            
        url = f"{DEXSCREENER_BASE}/tokens/{token}"
        
        try:
            async with self._session.get(url) as resp:
                if resp.status == 429:  # Rate limited
                    log.warning(f"Rate limited for token {token}, backing off")
                    await asyncio.sleep(1 + random.random() * 2)
                    return None
                    
                if resp.status != 200:
                    log.warning(f"API error {resp.status} for token {token}")
                    return None
                    
                data = await resp.json()
                pairs = data.get("pairs", [])
                return _pick_best_pair(pairs)
                
        except asyncio.TimeoutError:
            log.warning(f"Timeout fetching data for token {token}")
            return None
        except Exception as e:
            log.error(f"Error fetching data for token {token}: {e}")
            return None

    async def _rpc_health(self) -> SolanaHealthInfo:
        """
        Check Solana RPC health and get latest slot.
        
        Returns:
            SolanaHealthInfo with health status and slot
        """
        if self._client is None:
            return SolanaHealthInfo(
                rpc_healthy=False,
                slot=None,
                rpc_url=self._rpc_url
            )
            
        try:
            # Check health
            health_res = await self._client.get_health()
            healthy = (health_res.value == "ok")
            
            # Get latest slot
            slot_res = await self._client.get_slot()
            slot = slot_res.value
            
            return SolanaHealthInfo(
                rpc_healthy=healthy,
                slot=slot,
                rpc_url=self._rpc_url
            )
            
        except Exception as e:
            log.warning(f"RPC health check failed: {e}")
            return SolanaHealthInfo(
                rpc_healthy=False,
                slot=None,
                rpc_url=self._rpc_url
            )

    def _to_tick(self, token: str, pair: Optional[Dict[str, Any]], health: SolanaHealthInfo) -> TokenTick:
        """
        Convert pair data and health info to TokenTick.
        
        Args:
            token: Token identifier
            pair: Dexscreener pair data (can be None)
            health: Solana RPC health info
            
        Returns:
            TokenTick with parsed data
        """
        price = None
        liq_usd = None
        vol24 = None
        chg24 = None
        pair_addr = None

        if pair:
            # Parse price (string to float)
            try:
                price_str = pair.get("priceUsd")
                if price_str is not None:
                    price = float(price_str)
            except (ValueError, TypeError):
                price = None
                
            # Parse liquidity
            try:
                liquidity = pair.get("liquidity", {})
                if liquidity and "usd" in liquidity:
                    liq_usd = float(liquidity["usd"])
            except (ValueError, TypeError):
                liq_usd = None
                
            # Parse 24h volume
            try:
                volume = pair.get("volume", {})
                if volume and "h24" in volume:
                    vol24 = float(volume["h24"])
            except (ValueError, TypeError):
                vol24 = None
                
            # Parse 24h price change
            try:
                price_change = pair.get("priceChange", {})
                if price_change and "h24" in price_change:
                    chg24 = float(price_change["h24"])
            except (ValueError, TypeError):
                chg24 = None

            # Get pair address
            pair_addr = pair.get("pairAddress")

        return TokenTick(
            token=token,
            price_usd=price,
            volume_24h_usd=vol24,
            liquidity_usd=liq_usd,
            change_24h_pct=chg24,
            pair_address=pair_addr,
            slot=health.slot,
            rpc_healthy=health.rpc_healthy,
        )

    async def subscribe_ticks(
        self,
        tokens: List[str],
        interval_sec: int = 10,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream live token ticks from Dexscreener API.
        
        Args:
            tokens: List of SPL mint addresses (preferred) or symbols
            interval_sec: Update interval in seconds (default: 10)
            
        Yields:
            TokenTick data as dict for each token on each interval
        """
        if not tokens:
            log.warning("No tokens provided for subscription")
            return
            
        log.info(f"Starting tick subscription for {len(tokens)} tokens, interval={interval_sec}s")
        await self._ensure_clients()

        try:
            while True:
                # Check Solana RPC health once per cycle
                health = await self._rpc_health()
                
                # Fetch data for each token
                results: List[TokenTick] = []
                for token in tokens:
                    try:
                        pair = await self._fetch_token_best_pair(token)
                        tick = self._to_tick(token, pair, health)
                        results.append(tick)
                        
                        # Log successful data fetch
                        if tick.price_usd is not None:
                            log.debug(f"Token {token}: ${tick.price_usd:.6f} "
                                    f"(24h: {tick.change_24h_pct:+.2f}% if tick.change_24h_pct else 'N/A')")
                        else:
                            log.debug(f"Token {token}: No price data available")
                            
                    except Exception as e:
                        log.error(f"Error processing token {token}: {e}")
                        # Create failed tick but still yield something
                        results.append(
                            TokenTick(
                                token=token,
                                price_usd=None,
                                volume_24h_usd=None,
                                liquidity_usd=None,
                                change_24h_pct=None,
                                pair_address=None,
                                slot=health.slot,
                                rpc_healthy=health.rpc_healthy,
                            )
                        )
                    
                    # Add jitter to be API-friendly
                    await asyncio.sleep(0.05 + random.random() * 0.1)

                # Yield each tick as dict (JSON-serializable)
                for tick in results:
                    yield tick.model_dump()

                # Wait until next cycle
                await asyncio.sleep(interval_sec)
                
        except asyncio.CancelledError:
            log.info("Tick subscription cancelled")
            raise
        except Exception as e:
            log.error(f"Unexpected error in tick subscription: {e}")
            raise
        finally:
            await self._close()


# Popular Solana token mint addresses for reference
POPULAR_SOLANA_TOKENS = {
    "BONK": "DeZKbrG68Etnn9QhGS8GqVqGkG2i8jZ5YoZ5v9pA9C8h",  # BONK
    "WIF": "EKbAHjfVqBHHtdm7jSF92yJ7k3wB7KCZYqgqjJ8U7y8w",     # WIF (example)
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",    # USDC
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",    # USDT  
    "SOL": "So11111111111111111111111111111111111111112",     # Wrapped SOL
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",     # Raydium
    "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",    # Orca
}
