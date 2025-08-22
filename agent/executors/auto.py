"""
Auto executor with routing and fallback logic.

This module provides an AutoExecutor that can route to multiple providers
with configurable fallback strategies for optimal execution.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from agent.executor_base import TransactionExecutor, ExecutionRequest, ExecutionResult, QuoteRequest, QuoteResult, MultiExecutor
from agent.tx_logger import TxLogger, get_logger
from .photon import PhotonExecutor
from .gmgn import GmgnExecutor


class AutoExecutor(MultiExecutor):
    """
    Automatic executor with intelligent routing between Photon and GMGN.
    
    Provides fallback logic and can choose the best provider based on
    price, speed, or success rate.
    """
    
    name = "auto"
    
    def __init__(
        self,
        strategy: str = "first_success",
        rpc_url: Optional[str] = None,
        logger: Optional[TxLogger] = None,
        photon_api_key: Optional[str] = None,
        gmgn_api_key: Optional[str] = None,
        health_check_interval: int = 60  # seconds
    ):
        """
        Initialize AutoExecutor with Photon and GMGN providers.
        
        Args:
            strategy: Routing strategy ("first_success", "best_price", "fastest")
            rpc_url: Solana RPC URL for all executors
            logger: Transaction logger instance
            photon_api_key: API key for Photon (optional)
            gmgn_api_key: API key for GMGN (optional)
            health_check_interval: How often to check provider health (seconds)
        """
        self.logger = logger or get_logger()
        
        # Initialize individual executors
        self.photon = PhotonExecutor(
            api_key=photon_api_key,
            rpc_url=rpc_url,
            logger=self.logger
        )
        
        self.gmgn = GmgnExecutor(
            api_key=gmgn_api_key,
            rpc_url=rpc_url,
            logger=self.logger
        )
        
        # Initialize the MultiExecutor with our providers
        super().__init__(
            executors=[self.photon, self.gmgn],
            strategy=strategy
        )
        
        # Health tracking
        self.health_check_interval = health_check_interval
        self._last_health_check = {}
        self._provider_health = {"photon": True, "gmgn": True}
    
    async def execute_buy(self, req: ExecutionRequest) -> ExecutionResult:
        """
        Execute a buy order with intelligent routing.
        
        Args:
            req: Execution request parameters
            
        Returns:
            ExecutionResult from the best available provider
        """
        self.logger.info(f"AutoExecutor routing {req.transaction_type} order using {self.strategy} strategy")
        
        # Update provider health if needed
        await self._update_health_if_needed()
        
        # Filter to healthy providers only
        healthy_executors = [
            executor for executor in self.executors 
            if self._provider_health.get(executor.name, True)
        ]
        
        if not healthy_executors:
            self.logger.error("No healthy providers available")
            return ExecutionResult(
                ok=False,
                provider=self.name,
                error="No healthy providers available",
                timestamp=datetime.now(timezone.utc).isoformat(),
                request_metadata=req.metadata
            )
        
        # Temporarily use healthy executors
        original_executors = self.executors
        self.executors = healthy_executors
        
        try:
            # Use parent's routing logic but with health-filtered providers
            result = await super().execute_buy(req)
            
            # Add AutoExecutor metadata
            result.request_metadata["auto_executor"] = {
                "strategy": self.strategy,
                "healthy_providers": [e.name for e in healthy_executors],
                "total_providers": len(original_executors)
            }
            
            return result
        
        finally:
            # Restore original executor list
            self.executors = original_executors
    
    async def get_quote(self, req: QuoteRequest) -> QuoteResult:
        """
        Get quote from the best available provider.
        
        Args:
            req: Quote request parameters
            
        Returns:
            QuoteResult from the best provider
        """
        await self._update_health_if_needed()
        
        # Try providers in order of health and preference
        providers_to_try = []
        
        # First, try healthy providers
        if self._provider_health.get("photon", True):
            providers_to_try.append(("photon", self.photon))
        if self._provider_health.get("gmgn", True):
            providers_to_try.append(("gmgn", self.gmgn))
        
        # If no healthy providers, try all as fallback
        if not providers_to_try:
            providers_to_try = [("photon", self.photon), ("gmgn", self.gmgn)]
            self.logger.warning("No healthy providers for quote, trying all as fallback")
        
        last_error = None
        
        for provider_name, executor in providers_to_try:
            try:
                self.logger.debug(f"Trying quote from {provider_name}")
                result = await executor.get_quote(req)
                
                if result.ok:
                    self.logger.info(f"Quote successful from {provider_name}")
                    return result
                else:
                    last_error = result.error
                    self.logger.warning(f"Quote failed from {provider_name}: {result.error}")
            
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Quote exception from {provider_name}: {e}")
                continue
        
        # All providers failed
        return QuoteResult(
            ok=False,
            provider=self.name,
            error=f"All providers failed. Last error: {last_error}"
        )
    
    async def _update_health_if_needed(self):
        """Update provider health status if enough time has passed."""
        current_time = asyncio.get_event_loop().time()
        
        for executor in self.executors:
            last_check = self._last_health_check.get(executor.name, 0)
            
            if current_time - last_check > self.health_check_interval:
                try:
                    healthy = await executor.health_check()
                    self._provider_health[executor.name] = healthy
                    self._last_health_check[executor.name] = current_time
                    
                    if healthy:
                        self.logger.debug(f"Provider {executor.name} is healthy")
                    else:
                        self.logger.warning(f"Provider {executor.name} is unhealthy")
                
                except Exception as e:
                    self.logger.error(f"Health check failed for {executor.name}: {e}")
                    self._provider_health[executor.name] = False
                    self._last_health_check[executor.name] = current_time
    
    async def get_provider_status(self) -> Dict[str, Any]:
        """Get detailed status of all providers."""
        await self._update_health_if_needed()
        
        status = {
            "strategy": self.strategy,
            "providers": {},
            "summary": {
                "total": len(self.executors),
                "healthy": sum(self._provider_health.values()),
                "unhealthy": len(self.executors) - sum(self._provider_health.values())
            }
        }
        
        for executor in self.executors:
            status["providers"][executor.name] = {
                "healthy": self._provider_health.get(executor.name, True),
                "last_check": self._last_health_check.get(executor.name, 0)
            }
        
        return status
    
    async def force_health_check(self) -> Dict[str, bool]:
        """Force an immediate health check of all providers."""
        self.logger.info("Forcing health check of all providers")
        
        results = {}
        
        for executor in self.executors:
            try:
                healthy = await executor.health_check()
                self._provider_health[executor.name] = healthy
                self._last_health_check[executor.name] = asyncio.get_event_loop().time()
                results[executor.name] = healthy
                
                status = "healthy" if healthy else "unhealthy"
                self.logger.info(f"Provider {executor.name}: {status}")
            
            except Exception as e:
                self.logger.error(f"Health check failed for {executor.name}: {e}")
                self._provider_health[executor.name] = False
                results[executor.name] = False
        
        return results
    
    async def health_check(self) -> bool:
        """Check if AutoExecutor is healthy (at least one provider healthy)."""
        await self._update_health_if_needed()
        
        healthy_count = sum(self._provider_health.values())
        is_healthy = healthy_count > 0
        
        self.logger.log_health_check(
            self.name, 
            is_healthy, 
            {
                "healthy_providers": healthy_count,
                "total_providers": len(self.executors),
                "provider_health": self._provider_health
            }
        )
        
        return is_healthy
    
    def set_strategy(self, strategy: str):
        """Change the routing strategy."""
        if strategy not in ["first_success", "best_price", "fastest"]:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        self.strategy = strategy
        self.logger.info(f"AutoExecutor strategy changed to: {strategy}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        # Initialize all child executors
        await self.photon._ensure_clients()
        await self.gmgn._ensure_clients()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Close all child executors
        await self.photon._close_clients()
        await self.gmgn._close_clients()
