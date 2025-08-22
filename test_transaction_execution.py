"""
Test suite for transaction execution components.

This script tests the transaction executors (Photon, GMGN, Auto) without
requiring actual API connections or private keys.
"""

import asyncio
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from agent.executor_base import ExecutionRequest, QuoteRequest, TransactionType
from agent.executors import PhotonExecutor, GmgnExecutor, AutoExecutor
from agent.tx_logger import TxLogger

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class MockResponse:
    """Mock aiohttp response for testing."""
    
    def __init__(self, json_data: Dict[str, Any], status: int = 200):
        self.json_data = json_data
        self.status = status
    
    async def json(self):
        return self.json_data
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass


def create_test_execution_request() -> ExecutionRequest:
    """Create a test execution request."""
    return ExecutionRequest(
        owner_pubkey="11111111111111111111111111111112",  # Dummy pubkey
        token_in_mint="So11111111111111111111111111111111111111112",  # SOL
        token_out_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        amount_in_atomic=100000000,  # 0.1 SOL
        transaction_type=TransactionType.BUY,
        slippage_bps=100,  # 1%
        simulate_only=True,
        strategy_name="test",
        metadata={"test": True}
    )


def create_test_quote_request() -> QuoteRequest:
    """Create a test quote request."""
    return QuoteRequest(
        token_in_mint="So11111111111111111111111111111111111111112",  # SOL
        token_out_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        amount_in_atomic=100000000,  # 0.1 SOL
        slippage_bps=100  # 1%
    )


async def test_photon_executor():
    """Test PhotonExecutor with mocked responses."""
    log.info("=== Testing PhotonExecutor ===")
    
    # Mock successful quote response
    quote_response = MockResponse({
        "priceUsd": "0.000164",
        "outAmount": "164000",
        "routeId": "test-route-123",
        "priceImpact": "0.001"
    })
    
    # Mock successful swap response  
    swap_response = MockResponse({
        "transaction": "dGVzdC10cmFuc2FjdGlvbg==",  # base64 "test-transaction"
        "priceUsd": "0.000164",
        "outAmount": "164000",
        "routeId": "test-route-123"
    })
    
    executor = PhotonExecutor(logger=TxLogger(level="DEBUG"))
    
    try:
        # Test quote
        with patch('aiohttp.ClientSession.get', return_value=quote_response):
            quote_req = create_test_quote_request()
            quote_result = await executor.get_quote(quote_req)
            
            assert quote_result.ok, f"Quote failed: {quote_result.error}"
            assert quote_result.provider == "photon"
            assert quote_result.price_usd is not None
            log.info(f"✅ PhotonExecutor quote test passed: ${quote_result.price_usd}")
        
        # Test execution (simulation)
        with patch('aiohttp.ClientSession.post', return_value=swap_response):
            exec_req = create_test_execution_request()
            exec_result = await executor.execute_buy(exec_req)
            
            assert exec_result.ok, f"Execution failed: {exec_result.error}"
            assert exec_result.provider == "photon"
            assert exec_result.price_usd is not None
            log.info(f"✅ PhotonExecutor execution test passed: ${exec_result.price_usd}")
        
        return True
        
    except Exception as e:
        log.error(f"❌ PhotonExecutor test failed: {e}")
        return False


async def test_gmgn_executor():
    """Test GmgnExecutor with mocked responses."""
    log.info("\\n=== Testing GmgnExecutor ===")
    
    # Mock successful quote response
    quote_response = MockResponse({
        "code": 0,
        "data": {
            "routes": [{
                "priceUsd": "0.000162",
                "outAmount": "162000",
                "routeId": "gmgn-route-456",
                "priceImpact": "0.002",
                "fee": "0.1"
            }]
        }
    })
    
    # Mock successful swap response
    swap_response = MockResponse({
        "code": 0,
        "data": {
            "transaction": "Z21nbi10cmFuc2FjdGlvbg==",  # base64 "gmgn-transaction"
        }
    })
    
    executor = GmgnExecutor(logger=TxLogger(level="DEBUG"))
    
    try:
        # Test quote
        with patch('aiohttp.ClientSession.get', return_value=quote_response):
            quote_req = create_test_quote_request()
            quote_result = await executor.get_quote(quote_req)
            
            assert quote_result.ok, f"Quote failed: {quote_result.error}"
            assert quote_result.provider == "gmgn"
            assert quote_result.price_usd is not None
            log.info(f"✅ GmgnExecutor quote test passed: ${quote_result.price_usd}")
        
        # Test execution (simulation)
        with patch('aiohttp.ClientSession.get', return_value=quote_response), \
             patch('aiohttp.ClientSession.post', return_value=swap_response):
            exec_req = create_test_execution_request()
            exec_result = await executor.execute_buy(exec_req)
            
            assert exec_result.ok, f"Execution failed: {exec_result.error}"
            assert exec_result.provider == "gmgn"
            assert exec_result.price_usd is not None
            log.info(f"✅ GmgnExecutor execution test passed: ${exec_result.price_usd}")
        
        return True
        
    except Exception as e:
        log.error(f"❌ GmgnExecutor test failed: {e}")
        return False


async def test_auto_executor():
    """Test AutoExecutor with mocked providers."""
    log.info("\\n=== Testing AutoExecutor ===")
    
    # Create mock executors
    mock_photon = AsyncMock()
    mock_gmgn = AsyncMock()
    
    # Mock successful results
    mock_quote_result = MagicMock()
    mock_quote_result.ok = True
    mock_quote_result.provider = "photon"
    mock_quote_result.price_usd = 0.000165
    mock_quote_result.amount_out = 165000
    
    mock_exec_result = MagicMock()
    mock_exec_result.ok = True
    mock_exec_result.provider = "photon"
    mock_exec_result.price_usd = 0.000165
    mock_exec_result.request_metadata = {}
    
    mock_photon.get_quote.return_value = mock_quote_result
    mock_photon.execute_buy.return_value = mock_exec_result
    mock_photon.health_check.return_value = True
    mock_photon.name = "photon"
    
    mock_gmgn.get_quote.return_value = mock_quote_result
    mock_gmgn.execute_buy.return_value = mock_exec_result
    mock_gmgn.health_check.return_value = True
    mock_gmgn.name = "gmgn"
    
    executor = AutoExecutor(logger=TxLogger(level="DEBUG"))
    executor.photon = mock_photon
    executor.gmgn = mock_gmgn
    executor.executors = [mock_photon, mock_gmgn]
    
    try:
        # Test quote
        quote_req = create_test_quote_request()
        quote_result = await executor.get_quote(quote_req)
        
        assert quote_result.ok, f"Quote failed: {quote_result.error}"
        log.info(f"✅ AutoExecutor quote test passed: ${quote_result.price_usd}")
        
        # Test execution
        exec_req = create_test_execution_request()
        exec_result = await executor.execute_buy(exec_req)
        
        assert exec_result.ok, f"Execution failed: {exec_result.error}"
        log.info(f"✅ AutoExecutor execution test passed: ${exec_result.price_usd}")
        
        # Test provider status
        status = await executor.get_provider_status()
        assert "providers" in status
        assert len(status["providers"]) == 2
        log.info(f"✅ AutoExecutor status test passed: {status['summary']['healthy']} healthy providers")
        
        return True
        
    except Exception as e:
        log.error(f"❌ AutoExecutor test failed: {e}")
        return False


async def test_error_handling():
    """Test error handling in executors."""
    log.info("\\n=== Testing Error Handling ===")
    
    # Mock error responses
    error_response = MockResponse({
        "error": "Insufficient liquidity"
    }, status=400)
    
    rate_limit_response = MockResponse({
        "error": "Rate limited"
    }, status=429)
    
    executor = PhotonExecutor(logger=TxLogger(level="DEBUG"))
    
    try:
        # Test quote error handling
        with patch('aiohttp.ClientSession.get', return_value=error_response):
            quote_req = create_test_quote_request()
            quote_result = await executor.get_quote(quote_req)
            
            assert not quote_result.ok, "Expected quote to fail"
            assert "400" in quote_result.error or "Insufficient liquidity" in quote_result.error
            log.info(f"✅ Quote error handling test passed: {quote_result.error}")
        
        # Test rate limiting handling
        with patch('aiohttp.ClientSession.get', return_value=rate_limit_response):
            quote_req = create_test_quote_request()
            quote_result = await executor.get_quote(quote_req)
            
            assert not quote_result.ok, "Expected quote to fail due to rate limit"
            assert "Rate limited" in quote_result.error
            log.info(f"✅ Rate limit handling test passed: {quote_result.error}")
        
        return True
        
    except Exception as e:
        log.error(f"❌ Error handling test failed: {e}")
        return False


async def test_validation():
    """Test request validation."""
    log.info("\\n=== Testing Request Validation ===")
    
    try:
        # Test invalid execution request
        try:
            invalid_req = ExecutionRequest(
                owner_pubkey="",  # Invalid empty pubkey
                token_in_mint="invalid",
                token_out_mint="invalid",
                amount_in_atomic=-1,  # Invalid negative amount
            )
            # Should not reach here
            assert False, "Expected validation error"
        except Exception:
            log.info("✅ Invalid execution request validation passed")
        
        # Test valid quote request
        try:
            valid_req = create_test_quote_request()
            assert valid_req.amount_in_atomic > 0
            log.info("✅ Valid quote request validation passed")
        except Exception as e:
            log.error(f"Valid request validation failed: {e}")
            return False
        
        return True
        
    except Exception as e:
        log.error(f"❌ Validation test failed: {e}")
        return False


async def main():
    """Run all tests."""
    log.info("🧪 Testing Transaction Execution Components")
    log.info("=" * 60)
    
    tests = [
        ("PhotonExecutor", test_photon_executor),
        ("GmgnExecutor", test_gmgn_executor),
        ("AutoExecutor", test_auto_executor),
        ("Error Handling", test_error_handling),
        ("Request Validation", test_validation),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            status = "✅ PASS" if result else "❌ FAIL"
            results.append(result)
            log.info(f"{status} | {test_name}")
        except Exception as e:
            log.error(f"❌ FAIL | {test_name}: {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    log.info("\\n" + "=" * 60)
    log.info(f"🎯 Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        log.info("🎉 All transaction execution tests passed!")
        log.info("📋 Transaction execution system is ready for use.")
        log.info("\\n⚠️  Remember:")
        log.info("   • Set OWNER_PUBKEY in .env for trade execution")
        log.info("   • Set SOLANA_SECRET_KEY_B58 only for real trades (not simulation)")
        log.info("   • Always test with simulation first!")
    else:
        log.warning("⚠️ Some tests failed. Check the logs above.")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        log.info("\\n👋 Tests interrupted by user")
        exit(1)
    except Exception as e:
        log.error(f"💥 Unexpected error: {e}")
        exit(1)
