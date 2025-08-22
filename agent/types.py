"""
Type definitions for the modular trading agent.

This module contains Pydantic models for structured data handling.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class TokenTick(BaseModel):
    """Live token data from Dexscreener API."""
    
    source: str = Field(default="dexscreener", description="Data source identifier")
    chain: str = Field(default="solana", description="Blockchain network")
    token: str = Field(description="SPL mint address or symbol hint")
    price_usd: Optional[float] = Field(default=None, description="Current price in USD")
    volume_24h_usd: Optional[float] = Field(default=None, description="24-hour trading volume in USD")
    liquidity_usd: Optional[float] = Field(default=None, description="Total liquidity in USD")
    change_24h_pct: Optional[float] = Field(default=None, description="24-hour price change percentage")
    pair_address: Optional[str] = Field(default=None, description="DEX pair contract address")
    slot: Optional[int] = Field(default=None, description="Latest Solana slot number")
    rpc_healthy: bool = Field(default=True, description="Solana RPC connection health status")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Timestamp of the tick")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DexscreenerPair(BaseModel):
    """Dexscreener pair data structure."""
    
    chain_id: Optional[str] = Field(default=None, alias="chainId")
    dex_id: Optional[str] = Field(default=None, alias="dexId")
    url: Optional[str] = None
    pair_address: Optional[str] = Field(default=None, alias="pairAddress")
    base_token: Optional[Dict[str, Any]] = Field(default=None, alias="baseToken")
    quote_token: Optional[Dict[str, Any]] = Field(default=None, alias="quoteToken")
    price_native: Optional[str] = Field(default=None, alias="priceNative")
    price_usd: Optional[str] = Field(default=None, alias="priceUsd")
    txns: Optional[Dict[str, Any]] = None
    volume: Optional[Dict[str, Any]] = None
    price_change: Optional[Dict[str, Any]] = Field(default=None, alias="priceChange")
    liquidity: Optional[Dict[str, Any]] = None
    fdv: Optional[float] = None
    market_cap: Optional[float] = Field(default=None, alias="marketCap")
    
    class Config:
        """Pydantic configuration."""
        allow_population_by_field_name = True


class SolanaHealthInfo(BaseModel):
    """Solana RPC health information."""
    
    rpc_healthy: bool = Field(description="Whether the RPC endpoint is healthy")
    slot: Optional[int] = Field(default=None, description="Latest slot number")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    rpc_url: str = Field(description="RPC endpoint URL")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
