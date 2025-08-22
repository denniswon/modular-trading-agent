"""
Transaction logging utilities.

This module provides structured logging for transaction execution,
including JSONL logging for analysis and standard logging for debugging.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
import sys


class TxLogger:
    """
    Specialized logger for transaction execution.
    
    Provides both structured JSONL logging for analysis and
    human-readable logging for development and debugging.
    """
    
    def __init__(self, log_dir: str = "logs", level: str = "INFO"):
        """
        Initialize transaction logger.
        
        Args:
            log_dir: Directory to store log files
            level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Remove default logger and add custom ones
        logger.remove()
        
        # Console logger with colors
        logger.add(
            sys.stderr,
            level=level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                   "<level>{message}</level>",
            colorize=True
        )
        
        # File logger for general logs
        logger.add(
            self.log_dir / "executor.log",
            level=level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation="10 MB",
            retention="30 days",
            compression="gz"
        )
        
        # Separate logger for errors
        logger.add(
            self.log_dir / "executor_errors.log",
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation="10 MB",
            retention="30 days",
            compression="gz"
        )
        
        self.logger = logger.bind(component="TxExecutor")
    
    def write_jsonl(self, filename: str, record: Dict[str, Any]) -> None:
        """
        Write a record to a JSONL file.
        
        Args:
            filename: Name of the JSONL file (will be created in log_dir)
            record: Dictionary to write as JSON line
        """
        path = self.log_dir / filename
        
        # Add timestamp if not present
        if "timestamp" not in record:
            record["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Ensure we can serialize the record
        try:
            line = json.dumps(record, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as e:
            # Fallback: convert problematic values to strings
            sanitized = self._sanitize_for_json(record)
            line = json.dumps(sanitized, ensure_ascii=False, default=str)
            self.logger.warning(f"Had to sanitize record for JSON serialization: {e}")
        
        # Write to file
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write to JSONL file {path}: {e}")
    
    def _sanitize_for_json(self, obj: Any) -> Any:
        """Recursively sanitize an object to be JSON serializable."""
        if isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._sanitize_for_json(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        else:
            # Convert anything else to string
            return str(obj)
    
    def log_execution_request(self, provider: str, request: Dict[str, Any]) -> None:
        """Log an execution request."""
        record = {
            "event": "execution_request",
            "provider": provider,
            "request": request,
        }
        self.write_jsonl("tx_requests.jsonl", record)
        
        # Also log to console for debugging
        token_in = request.get("token_in_mint", "unknown")[-8:]  # Last 8 chars
        token_out = request.get("token_out_mint", "unknown")[-8:]
        amount = request.get("amount_in_atomic", 0)
        simulate = request.get("simulate_only", True)
        
        self.logger.info(
            f"[{provider}] {'Simulating' if simulate else 'Executing'} swap: "
            f"{amount} {token_in} → {token_out}"
        )
    
    def log_execution_result(self, result: Dict[str, Any]) -> None:
        """Log an execution result."""
        record = {
            "event": "execution_result",
            **result,
        }
        self.write_jsonl("tx_results.jsonl", record)
        
        provider = result.get("provider", "unknown")
        success = result.get("ok", False)
        
        if success:
            tx_sig = result.get("tx_sig")
            price = result.get("price_usd")
            
            if tx_sig:
                self.logger.success(f"[{provider}] Transaction successful: {tx_sig}")
            else:
                self.logger.info(f"[{provider}] Simulation successful")
            
            if price:
                self.logger.info(f"[{provider}] Execution price: ${price:.6f}")
        else:
            error = result.get("error", "Unknown error")
            self.logger.error(f"[{provider}] Execution failed: {error}")
    
    def log_quote_request(self, provider: str, request: Dict[str, Any]) -> None:
        """Log a quote request."""
        record = {
            "event": "quote_request",
            "provider": provider,
            "request": request,
        }
        self.write_jsonl("tx_quotes.jsonl", record)
    
    def log_quote_result(self, result: Dict[str, Any]) -> None:
        """Log a quote result."""
        record = {
            "event": "quote_result",
            **result,
        }
        self.write_jsonl("tx_quotes.jsonl", record)
        
        provider = result.get("provider", "unknown")
        success = result.get("ok", False)
        
        if success:
            price = result.get("price_usd")
            amount_out = result.get("amount_out")
            impact = result.get("impact_bps")
            
            self.logger.info(
                f"[{provider}] Quote: ${price:.6f} per token, "
                f"out: {amount_out}, impact: {impact}bps"
            )
        else:
            error = result.get("error", "Unknown error")
            self.logger.warning(f"[{provider}] Quote failed: {error}")
    
    def log_error(self, provider: str, error: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log an error with context."""
        record = {
            "event": "error",
            "provider": provider,
            "error": error,
            "context": context or {},
        }
        self.write_jsonl("tx_errors.jsonl", record)
        self.logger.error(f"[{provider}] {error}")
    
    def log_health_check(self, provider: str, healthy: bool, details: Optional[Dict[str, Any]] = None) -> None:
        """Log a health check result."""
        record = {
            "event": "health_check",
            "provider": provider,
            "healthy": healthy,
            "details": details or {},
        }
        self.write_jsonl("tx_health.jsonl", record)
        
        status = "healthy" if healthy else "unhealthy"
        self.logger.info(f"[{provider}] Health check: {status}")
    
    def log_rate_limit(self, provider: str, details: Dict[str, Any]) -> None:
        """Log rate limiting information."""
        record = {
            "event": "rate_limit",
            "provider": provider,
            **details,
        }
        self.write_jsonl("tx_rate_limits.jsonl", record)
        self.logger.warning(f"[{provider}] Rate limit encountered")
    
    def log_performance(self, provider: str, operation: str, duration_ms: int, success: bool) -> None:
        """Log performance metrics."""
        record = {
            "event": "performance",
            "provider": provider,
            "operation": operation,
            "duration_ms": duration_ms,
            "success": success,
        }
        self.write_jsonl("tx_performance.jsonl", record)
        
        status = "✓" if success else "✗"
        self.logger.debug(f"[{provider}] {operation}: {duration_ms}ms {status}")
    
    # Convenience methods that match the original simple interface
    def info(self, msg: str) -> None:
        """Log an info message."""
        self.logger.info(msg)
    
    def error(self, msg: str) -> None:
        """Log an error message."""
        self.logger.error(msg)
    
    def warning(self, msg: str) -> None:
        """Log a warning message."""
        self.logger.warning(msg)
    
    def debug(self, msg: str) -> None:
        """Log a debug message."""
        self.logger.debug(msg)
    
    def success(self, msg: str) -> None:
        """Log a success message."""
        self.logger.success(msg)


# Global logger instance
_global_logger: Optional[TxLogger] = None


def get_logger() -> TxLogger:
    """Get the global transaction logger instance."""
    global _global_logger
    if _global_logger is None:
        _global_logger = TxLogger()
    return _global_logger


def set_global_logger(logger: TxLogger) -> None:
    """Set the global transaction logger instance."""
    global _global_logger
    _global_logger = logger
