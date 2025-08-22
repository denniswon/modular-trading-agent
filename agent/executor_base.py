"""
Base classes and interfaces for transaction execution.

This module defines the core abstractions for executing trades through various
DEX aggregators and APIs like Photon and GMGN.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class TransactionType(str, Enum):
    """Types of transactions supported."""
    BUY = "buy"
    SELL = "sell"
    SWAP = "swap"


class ExecutionRequest(BaseModel):
    """
    Request for executing a transaction through a DEX aggregator.
    
    This represents a swap where we pay `token_in` to receive `token_out`.
    """
    # Core transaction details
    owner_pubkey: str = Field(..., description="Wallet public key that will execute the transaction")
    token_in_mint: str = Field(..., description="Mint address of input token (what we're paying)")
    token_out_mint: str = Field(..., description="Mint address of output token (what we're buying)")
    amount_in_atomic: int = Field(..., description="Amount in smallest units of token_in (lamports for SOL)")
    
    # Trading parameters
    transaction_type: TransactionType = Field(default=TransactionType.BUY, description="Type of transaction")
    limit_price_usd: Optional[float] = Field(default=None, description="Maximum price per token in USD")
    slippage_bps: int = Field(default=100, description="Slippage tolerance in basis points (100 = 1%)")
    priority_fee_lamports: int = Field(default=0, description="Priority fee in lamports for faster execution")
    
    # Safety and simulation
    simulate_only: bool = Field(default=True, description="If True, only simulate; don't broadcast transaction")
    max_retries: int = Field(default=3, description="Maximum number of retry attempts")
    timeout_seconds: int = Field(default=30, description="Timeout for API calls in seconds")
    
    # Metadata
    strategy_name: Optional[str] = Field(default=None, description="Name of strategy that generated this request")
    confidence: Optional[float] = Field(default=None, description="Signal confidence (0.0-1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for logging")


class ExecutionResult(BaseModel):
    """
    Result of a transaction execution attempt.
    
    Contains all relevant information about the execution including
    success/failure, pricing, transaction details, and error information.
    """
    # Execution status
    ok: bool = Field(..., description="Whether the execution was successful")
    provider: str = Field(..., description="Name of the provider that executed the transaction")
    
    # Transaction details
    route_id: Optional[str] = Field(default=None, description="Route/quote identifier from the provider")
    price_usd: Optional[float] = Field(default=None, description="Actual execution price per token in USD")
    amount_out: Optional[int] = Field(default=None, description="Actual amount received in atomic units")
    
    # Blockchain details
    tx_sig: Optional[str] = Field(default=None, description="Transaction signature if broadcast")
    slot: Optional[int] = Field(default=None, description="Solana slot number when transaction was processed")
    
    # Error information
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    error_code: Optional[str] = Field(default=None, description="Provider-specific error code")
    
    # Performance metrics
    execution_time_ms: Optional[int] = Field(default=None, description="Total execution time in milliseconds")
    gas_used: Optional[int] = Field(default=None, description="Gas/compute units used")
    
    # Raw provider response (sanitized)
    raw: Optional[Dict[str, Any]] = Field(default=None, description="Provider response (sanitized)")
    
    # Metadata
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp of execution")
    request_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata from original request")


class QuoteRequest(BaseModel):
    """Request for getting a quote without executing."""
    token_in_mint: str
    token_out_mint: str
    amount_in_atomic: int
    slippage_bps: int = 100


class QuoteResult(BaseModel):
    """Result of a quote request."""
    ok: bool
    provider: str
    price_usd: Optional[float] = None
    amount_out: Optional[int] = None
    route_id: Optional[str] = None
    impact_bps: Optional[int] = None  # Price impact in basis points
    fee_usd: Optional[float] = None
    error: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


class TransactionExecutor(ABC):
    """
    Abstract base class for transaction executors.
    
    Implementations handle the specifics of different DEX aggregators
    like Photon, GMGN, Jupiter, etc.
    """
    name: str
    
    @abstractmethod
    async def execute_buy(self, req: ExecutionRequest) -> ExecutionResult:
        """
        Execute a buy order through this provider.
        
        Args:
            req: Execution request with all transaction details
            
        Returns:
            ExecutionResult with success/failure and transaction details
        """
        raise NotImplementedError
    
    @abstractmethod
    async def get_quote(self, req: QuoteRequest) -> QuoteResult:
        """
        Get a price quote without executing the transaction.
        
        Args:
            req: Quote request with token details
            
        Returns:
            QuoteResult with pricing information
        """
        raise NotImplementedError
    
    async def execute_sell(self, req: ExecutionRequest) -> ExecutionResult:
        """
        Execute a sell order through this provider.
        
        Default implementation swaps token_in and token_out for buy logic.
        Override if provider has specific sell endpoints.
        """
        # For most DEX aggregators, selling is just buying in reverse
        sell_req = req.model_copy()
        sell_req.token_in_mint, sell_req.token_out_mint = req.token_out_mint, req.token_in_mint
        sell_req.transaction_type = TransactionType.SELL
        
        result = await self.execute_buy(sell_req)
        result.request_metadata["original_type"] = "sell"
        return result
    
    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and responsive.
        
        Returns:
            True if provider is healthy, False otherwise
        """
        try:
            # Override in implementations with provider-specific health checks
            return True
        except Exception:
            return False


class MultiExecutor(TransactionExecutor):
    """
    Executor that can route to multiple providers with fallback logic.
    
    This is useful for having primary/backup providers or for choosing
    the best price across multiple aggregators.
    """
    name = "multi"
    
    def __init__(self, executors: List[TransactionExecutor], strategy: str = "first_success"):
        """
        Initialize multi-executor with a list of providers.
        
        Args:
            executors: List of TransactionExecutor instances
            strategy: Routing strategy ("first_success", "best_price", "fastest")
        """
        self.executors = executors
        self.strategy = strategy
        
        if not executors:
            raise ValueError("At least one executor must be provided")
    
    async def execute_buy(self, req: ExecutionRequest) -> ExecutionResult:
        """Execute using the configured strategy."""
        if self.strategy == "first_success":
            return await self._execute_first_success(req)
        elif self.strategy == "best_price":
            return await self._execute_best_price(req)
        elif self.strategy == "fastest":
            return await self._execute_fastest(req)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    async def get_quote(self, req: QuoteRequest) -> QuoteResult:
        """Get quote from first available provider."""
        for executor in self.executors:
            try:
                result = await executor.get_quote(req)
                if result.ok:
                    return result
            except Exception:
                continue
        
        return QuoteResult(
            ok=False,
            provider=self.name,
            error="All providers failed to provide quote"
        )
    
    async def _execute_first_success(self, req: ExecutionRequest) -> ExecutionResult:
        """Try executors in order until one succeeds."""
        last_error = None
        
        for executor in self.executors:
            try:
                result = await executor.execute_buy(req)
                if result.ok:
                    return result
                last_error = result.error
            except Exception as e:
                last_error = str(e)
                continue
        
        return ExecutionResult(
            ok=False,
            provider=self.name,
            error=f"All providers failed. Last error: {last_error}"
        )
    
    async def _execute_best_price(self, req: ExecutionRequest) -> ExecutionResult:
        """Get quotes from all providers and execute with the best price."""
        # First get quotes from all providers
        quote_req = QuoteRequest(
            token_in_mint=req.token_in_mint,
            token_out_mint=req.token_out_mint,
            amount_in_atomic=req.amount_in_atomic,
            slippage_bps=req.slippage_bps
        )
        
        quotes = []
        for executor in self.executors:
            try:
                quote = await executor.get_quote(quote_req)
                if quote.ok and quote.amount_out:
                    quotes.append((executor, quote))
            except Exception:
                continue
        
        if not quotes:
            return ExecutionResult(
                ok=False,
                provider=self.name,
                error="No providers returned valid quotes"
            )
        
        # Choose the quote with the highest amount out
        best_executor, best_quote = max(quotes, key=lambda x: x[1].amount_out or 0)
        
        # Execute with the best provider
        return await best_executor.execute_buy(req)
    
    async def _execute_fastest(self, req: ExecutionRequest) -> ExecutionResult:
        """Execute with all providers concurrently and return the first success."""
        import asyncio
        
        # Create tasks for all executors
        tasks = [executor.execute_buy(req) for executor in self.executors]
        
        # Wait for first successful result
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                if result.ok:
                    # Cancel remaining tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    return result
            except Exception:
                continue
        
        return ExecutionResult(
            ok=False,
            provider=self.name,
            error="All providers failed in fastest mode"
        )
