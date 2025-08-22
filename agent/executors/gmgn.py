"""
GMGN API executor for Solana token swaps.

This module implements transaction execution through GMGN's DEX aggregator API,
based on their official documentation at https://docs.gmgn.ai/
"""

from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone

import aiohttp
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
import base58

from agent.executor_base import TransactionExecutor, ExecutionRequest, ExecutionResult, QuoteRequest, QuoteResult
from agent.tx_logger import TxLogger, get_logger


# GMGN API configuration
GMGN_BASE_URL = "https://gmgn.ai/defi/quotev2"  # Based on their docs
GMGN_SWAP_URL = "https://gmgn.ai/defi/swapv2"


class GmgnExecutor(TransactionExecutor):
    """
    GMGN DEX aggregator executor.
    
    Implements transaction execution through GMGN's API which provides
    quote and swap functionality for Solana tokens.
    """
    
    name = "gmgn"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        rpc_url: Optional[str] = None,
        logger: Optional[TxLogger] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize GMGN executor.
        
        Args:
            api_key: GMGN API key (from env GMGN_API_KEY if not provided)
            rpc_url: Solana RPC URL (from env SOLANA_RPC if not provided)
            logger: Transaction logger instance
            base_url: Custom GMGN API base URL
        """
        load_dotenv()
        
        self.api_key = api_key or os.getenv("GMGN_API_KEY", "")
        self.rpc_url = rpc_url or os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
        self.base_url = base_url or os.getenv("GMGN_BASE", GMGN_BASE_URL)
        self.logger = logger or get_logger()
        
        # HTTP session for connection pooling
        self._session: Optional[aiohttp.ClientSession] = None
        self._own_session = False
        
        # Solana client for transaction broadcasting
        self._rpc_client: Optional[AsyncClient] = None
        
        # Keypair for signing (optional - only needed if simulate_only=False)
        self._keypair: Optional[Keypair] = None
        secret_key_b58 = os.getenv("SOLANA_SECRET_KEY_B58")
        if secret_key_b58:
            try:
                secret_bytes = base58.b58decode(secret_key_b58)
                self._keypair = Keypair.from_bytes(secret_bytes)
            except Exception as e:
                self.logger.warning(f"Failed to load keypair: {e}")
    
    async def _ensure_clients(self):
        """Ensure HTTP session and RPC client are initialized."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._own_session = True
        
        if self._rpc_client is None:
            self._rpc_client = AsyncClient(self.rpc_url)
    
    async def _close_clients(self):
        """Close HTTP session and RPC client."""
        if self._rpc_client:
            await self._rpc_client.close()
            self._rpc_client = None
            
        if self._own_session and self._session:
            await self._session.close()
            self._session = None
    
    async def get_quote(self, req: QuoteRequest) -> QuoteResult:
        """
        Get a price quote from GMGN without executing.
        
        Args:
            req: Quote request parameters
            
        Returns:
            QuoteResult with pricing information
        """
        await self._ensure_clients()
        start_time = time.time()
        
        try:
            self.logger.log_quote_request(self.name, req.model_dump())
            
            quote_data = await self._get_quote_data(req)
            
            if not quote_data.get("success", True):
                result = QuoteResult(
                    ok=False,
                    provider=self.name,
                    error=quote_data.get("error", "Quote failed"),
                    raw=quote_data
                )
                self.logger.log_quote_result(result.model_dump())
                return result
            
            # Parse successful response
            routes = quote_data.get("routes", [])
            if not routes:
                result = QuoteResult(
                    ok=False,
                    provider=self.name,
                    error="No routes found",
                    raw=quote_data
                )
                self.logger.log_quote_result(result.model_dump())
                return result
            
            # Get the best route (highest output amount)
            best_route = max(routes, key=lambda r: int(r.get("outAmount", 0)))
            
            price_usd = best_route.get("priceUsd")
            amount_out = best_route.get("outAmount") 
            route_id = best_route.get("routeId") or best_route.get("id")
            impact_bps = best_route.get("priceImpact")
            fee_usd = best_route.get("fee")
            
            result = QuoteResult(
                ok=True,
                provider=self.name,
                price_usd=float(price_usd) if price_usd else None,
                amount_out=int(amount_out) if amount_out else None,
                route_id=route_id,
                impact_bps=int(float(impact_bps) * 10000) if impact_bps else None,  # Convert to bps
                fee_usd=float(fee_usd) if fee_usd else None,
                raw={"best_route": best_route, "all_routes": routes}
            )
            
            self.logger.log_quote_result(result.model_dump())
            return result
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.log_performance(self.name, "quote", duration_ms, False)
            
            error_msg = f"Quote request failed: {type(e).__name__}: {e}"
            self.logger.log_error(self.name, error_msg, {"request": req.model_dump()})
            
            return QuoteResult(
                ok=False,
                provider=self.name,
                error=error_msg
            )
        
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.log_performance(self.name, "quote", duration_ms, True)
    
    async def execute_buy(self, req: ExecutionRequest) -> ExecutionResult:
        """
        Execute a buy order through GMGN.
        
        Args:
            req: Execution request parameters
            
        Returns:
            ExecutionResult with transaction details
        """
        await self._ensure_clients()
        start_time = time.time()
        
        try:
            self.logger.log_execution_request(self.name, req.model_dump())
            
            # Step 1: Get quote/route
            quote_req = QuoteRequest(
                token_in_mint=req.token_in_mint,
                token_out_mint=req.token_out_mint,
                amount_in_atomic=req.amount_in_atomic,
                slippage_bps=req.slippage_bps
            )
            
            quote_result = await self.get_quote(quote_req)
            if not quote_result.ok:
                result = ExecutionResult(
                    ok=False,
                    provider=self.name,
                    error=f"Quote failed: {quote_result.error}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    request_metadata=req.metadata
                )
                self.logger.log_execution_result(result.model_dump())
                return result
            
            # Step 2: Check limit price if provided
            if req.limit_price_usd and quote_result.price_usd:
                if quote_result.price_usd > req.limit_price_usd:
                    error = f"Price ${quote_result.price_usd} exceeds limit ${req.limit_price_usd}"
                    result = ExecutionResult(
                        ok=False,
                        provider=self.name,
                        error=error,
                        price_usd=quote_result.price_usd,
                        raw=quote_result.raw,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        request_metadata=req.metadata
                    )
                    self.logger.log_execution_result(result.model_dump())
                    return result
            
            # Step 3: Build transaction
            swap_data = await self._build_swap_transaction(req, quote_result.route_id)
            
            if not swap_data.get("success", True):
                result = ExecutionResult(
                    ok=False,
                    provider=self.name,
                    error=swap_data.get("error", "Failed to build transaction"),
                    price_usd=quote_result.price_usd,
                    raw={"quote": quote_result.raw, "swap": swap_data},
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    request_metadata=req.metadata
                )
                self.logger.log_execution_result(result.model_dump())
                return result
            
            # Step 4: Handle simulation vs real execution
            if req.simulate_only or not self._keypair:
                # Return simulation result
                result = ExecutionResult(
                    ok=True,
                    provider=self.name,
                    route_id=quote_result.route_id,
                    price_usd=quote_result.price_usd,
                    amount_out=quote_result.amount_out,
                    raw={"quote": quote_result.raw, "swap": swap_data},
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    request_metadata=req.metadata
                )
                self.logger.log_execution_result(result.model_dump())
                return result
            
            # Step 5: Sign and broadcast transaction
            tx_sig, slot = await self._sign_and_send_transaction(swap_data, req)
            
            duration_ms = int((time.time() - start_time) * 1000)
            result = ExecutionResult(
                ok=True,
                provider=self.name,
                route_id=quote_result.route_id,
                price_usd=quote_result.price_usd,
                amount_out=quote_result.amount_out,
                tx_sig=tx_sig,
                slot=slot,
                execution_time_ms=duration_ms,
                raw={"quote": quote_result.raw, "swap": swap_data},
                timestamp=datetime.now(timezone.utc).isoformat(),
                request_metadata=req.metadata
            )
            
            self.logger.log_execution_result(result.model_dump())
            return result
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.log_performance(self.name, "execute_buy", duration_ms, False)
            
            error_msg = f"Execution failed: {type(e).__name__}: {e}"
            self.logger.log_error(self.name, error_msg, {"request": req.model_dump()})
            
            return ExecutionResult(
                ok=False,
                provider=self.name,
                error=error_msg,
                execution_time_ms=duration_ms,
                timestamp=datetime.now(timezone.utc).isoformat(),
                request_metadata=req.metadata
            )
        
        finally:
            # Keep clients open for reuse unless explicitly closed
            pass
    
    async def _get_quote_data(self, req: QuoteRequest) -> Dict[str, Any]:
        """Get quote data from GMGN API."""
        assert self._session is not None
        
        # Build quote request parameters
        params = {
            "from": req.token_in_mint,
            "to": req.token_out_mint,
            "amount": str(req.amount_in_atomic),
            "slippage": req.slippage_bps / 10000,  # Convert bps to decimal (e.g., 100 bps = 0.01)
            "chain": "solana"
        }
        
        headers = {
            "accept": "application/json",
            "user-agent": "ModularTradingAgent/1.0"
        }
        
        if self.api_key:
            headers["x-api-key"] = self.api_key
        
        try:
            async with self._session.get(
                self.base_url,
                params=params,
                headers=headers
            ) as response:
                
                if response.status == 429:
                    self.logger.log_rate_limit(self.name, {"status": response.status})
                    return {
                        "success": False,
                        "error": "Rate limited by GMGN API"
                    }
                
                data = await response.json()
                
                if response.status != 200:
                    return {
                        "success": False,
                        "error": f"Quote failed: {response.status} - {data.get('error', 'Unknown error')}",
                        "raw": data
                    }
                
                # Handle GMGN response format
                if data.get("code") != 0:  # GMGN typically uses code=0 for success
                    return {
                        "success": False,
                        "error": f"GMGN API error: {data.get('msg', 'Unknown error')}",
                        "raw": data
                    }
                
                return {
                    "success": True,
                    "routes": data.get("data", {}).get("routes", [data.get("data", {})]),  # Handle both formats
                    "raw": data
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Quote request failed: {type(e).__name__}: {e}"
            }
    
    async def _build_swap_transaction(self, req: ExecutionRequest, route_id: Optional[str]) -> Dict[str, Any]:
        """Build a swap transaction through GMGN's API."""
        assert self._session is not None
        
        # Build swap request payload
        payload = {
            "from": req.token_in_mint,
            "to": req.token_out_mint,
            "amount": str(req.amount_in_atomic),
            "slippage": req.slippage_bps / 10000,
            "userPublicKey": req.owner_pubkey,
            "chain": "solana"
        }
        
        if route_id:
            payload["routeId"] = route_id
        
        if req.priority_fee_lamports > 0:
            payload["priorityFee"] = req.priority_fee_lamports
        
        headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": "ModularTradingAgent/1.0"
        }
        
        if self.api_key:
            headers["x-api-key"] = self.api_key
        
        try:
            async with self._session.post(
                GMGN_SWAP_URL,
                json=payload,
                headers=headers
            ) as response:
                
                if response.status == 429:
                    self.logger.log_rate_limit(self.name, {"status": response.status})
                    return {
                        "success": False,
                        "error": "Rate limited by GMGN API"
                    }
                
                data = await response.json()
                
                if response.status != 200:
                    return {
                        "success": False,
                        "error": f"Swap build failed: {response.status} - {data.get('error', 'Unknown error')}",
                        "raw": data
                    }
                
                # Handle GMGN response format
                if data.get("code") != 0:
                    return {
                        "success": False,
                        "error": f"GMGN swap error: {data.get('msg', 'Unknown error')}",
                        "raw": data
                    }
                
                swap_data = data.get("data", {})
                return {
                    "success": True,
                    "transaction": swap_data.get("transaction") or swap_data.get("tx"),
                    "raw": data
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Swap build failed: {type(e).__name__}: {e}"
            }
    
    async def _sign_and_send_transaction(self, swap_data: Dict[str, Any], req: ExecutionRequest) -> tuple[str, Optional[int]]:
        """Sign and broadcast the transaction."""
        if not self._keypair:
            raise ValueError("No keypair available for signing")
        
        # Get the base64 encoded transaction
        tx_b64 = swap_data.get("transaction")
        if not tx_b64:
            raise ValueError("No transaction data in GMGN response")
        
        # Decode and reconstruct the transaction
        tx_bytes = base64.b64decode(tx_b64)
        vtx = VersionedTransaction.from_bytes(tx_bytes)
        
        # Sign the transaction
        vtx = VersionedTransaction.populate_and_sign(vtx.message, [self._keypair])
        
        # Send to Solana network
        assert self._rpc_client is not None
        
        send_opts = TxOpts(
            skip_preflight=False,
            max_retries=req.max_retries
        )
        
        send_result = await self._rpc_client.send_raw_transaction(
            bytes(vtx),
            opts=send_opts
        )
        
        tx_sig = str(send_result.value)
        
        # Get current slot
        try:
            slot_result = await self._rpc_client.get_slot()
            slot = slot_result.value
        except Exception:
            slot = None
        
        return tx_sig, slot
    
    async def health_check(self) -> bool:
        """Check if GMGN API is healthy."""
        try:
            await self._ensure_clients()
            assert self._session is not None
            
            headers = {
                "accept": "application/json",
                "user-agent": "ModularTradingAgent/1.0"
            }
            
            if self.api_key:
                headers["x-api-key"] = self.api_key
            
            # Use a simple quote request as health check
            params = {
                "from": "So11111111111111111111111111111111111111112",  # SOL
                "to": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                "amount": "1000000",  # 0.001 SOL
                "slippage": 0.01,  # 1%
                "chain": "solana"
            }
            
            async with self._session.get(
                self.base_url,
                params=params,
                headers=headers
            ) as response:
                healthy = response.status == 200
                
                details = {
                    "status_code": response.status,
                    "response_time_ms": 0  # Could add timing if needed
                }
                
                self.logger.log_health_check(self.name, healthy, details)
                return healthy
        
        except Exception as e:
            self.logger.log_health_check(self.name, False, {"error": str(e)})
            return False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_clients()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_clients()
