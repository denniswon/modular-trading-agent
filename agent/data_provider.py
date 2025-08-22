"""
Example data provider implementations.

This module contains concrete implementations of MarketDataProvider.
"""

import random
import time
from typing import Dict, Any
import requests
from .base import MarketDataProvider, MarketData


class DummyProvider(MarketDataProvider):
    """Dummy data provider for testing and development."""
    
    def __init__(self):
        self.price_cache = {}
        
    def fetch_data(self, symbol: str) -> MarketData:
        """Generate fake market data for testing."""
        # Simulate price movement from last cached price or start at $50,000 for BTC
        base_price = self.price_cache.get(symbol, 50000.0 if 'BTC' in symbol else 100.0)
        
        # Random walk with slight upward bias
        price_change = random.uniform(-0.02, 0.025)  # -2% to +2.5%
        new_price = base_price * (1 + price_change)
        self.price_cache[symbol] = new_price
        
        return MarketData(
            symbol=symbol,
            price=round(new_price, 2),
            volume=random.uniform(1000, 10000),
            timestamp=time.time(),
            additional_data={
                'high_24h': new_price * 1.05,
                'low_24h': new_price * 0.95,
                'change_24h': random.uniform(-5, 5)
            }
        )
    
    def get_historical_data(self, symbol: str, period: str, limit: int = 100) -> list[MarketData]:
        """Generate fake historical data."""
        historical_data = []
        current_time = time.time()
        base_price = 50000.0 if 'BTC' in symbol else 100.0
        
        for i in range(limit):
            # Generate decreasing timestamps
            timestamp = current_time - (i * 3600)  # 1 hour intervals
            
            # Random walk for historical prices
            price_change = random.uniform(-0.03, 0.03)
            price = base_price * (1 + price_change)
            base_price = price  # Update for next iteration
            
            historical_data.append(MarketData(
                symbol=symbol,
                price=round(price, 2),
                volume=random.uniform(500, 5000),
                timestamp=timestamp,
                additional_data={'period': period}
            ))
        
        return list(reversed(historical_data))  # Return chronological order


class BinanceProvider(MarketDataProvider):
    """Binance API data provider (simplified example)."""
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.binance.com/api/v3"
        
    def fetch_data(self, symbol: str) -> MarketData:
        """Fetch real-time data from Binance API."""
        try:
            # Get ticker price
            ticker_url = f"{self.base_url}/ticker/price"
            ticker_response = requests.get(ticker_url, params={'symbol': symbol})
            ticker_response.raise_for_status()
            ticker_data = ticker_response.json()
            
            # Get 24hr ticker statistics
            stats_url = f"{self.base_url}/ticker/24hr"
            stats_response = requests.get(stats_url, params={'symbol': symbol})
            stats_response.raise_for_status()
            stats_data = stats_response.json()
            
            return MarketData(
                symbol=symbol,
                price=float(ticker_data['price']),
                volume=float(stats_data['volume']),
                timestamp=time.time(),
                additional_data={
                    'high_24h': float(stats_data['highPrice']),
                    'low_24h': float(stats_data['lowPrice']),
                    'change_24h': float(stats_data['priceChangePercent']),
                    'open_price': float(stats_data['openPrice']),
                    'close_price': float(stats_data['prevClosePrice'])
                }
            )
            
        except requests.RequestException as e:
            print(f"Error fetching data from Binance: {e}")
            # Fallback to dummy data
            dummy = DummyProvider()
            return dummy.fetch_data(symbol)
    
    def get_historical_data(self, symbol: str, period: str, limit: int = 100) -> list[MarketData]:
        """Fetch historical data from Binance API."""
        try:
            url = f"{self.base_url}/klines"
            params = {
                'symbol': symbol,
                'interval': period,
                'limit': min(limit, 1000)  # Binance limit
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            klines = response.json()
            
            historical_data = []
            for kline in klines:
                historical_data.append(MarketData(
                    symbol=symbol,
                    price=float(kline[4]),  # Close price
                    volume=float(kline[5]),  # Volume
                    timestamp=kline[6] / 1000,  # Close time in seconds
                    additional_data={
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'period': period
                    }
                ))
            
            return historical_data
            
        except requests.RequestException as e:
            print(f"Error fetching historical data from Binance: {e}")
            # Fallback to dummy data
            dummy = DummyProvider()
            return dummy.get_historical_data(symbol, period, limit)


class AlphaVantageProvider(MarketDataProvider):
    """Alpha Vantage API data provider (example for stocks/forex)."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
    
    def fetch_data(self, symbol: str) -> MarketData:
        """Fetch real-time stock data from Alpha Vantage."""
        try:
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'Global Quote' in data:
                quote = data['Global Quote']
                return MarketData(
                    symbol=symbol,
                    price=float(quote['05. price']),
                    volume=float(quote['06. volume']),
                    timestamp=time.time(),
                    additional_data={
                        'open': float(quote['02. open']),
                        'high': float(quote['03. high']),
                        'low': float(quote['04. low']),
                        'change_percent': quote['10. change percent'],
                        'previous_close': float(quote['08. previous close'])
                    }
                )
            else:
                raise ValueError("Invalid response from Alpha Vantage API")
                
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Error fetching data from Alpha Vantage: {e}")
            # Fallback to dummy data
            dummy = DummyProvider()
            return dummy.fetch_data(symbol)
    
    def get_historical_data(self, symbol: str, period: str, limit: int = 100) -> list[MarketData]:
        """Fetch historical stock data from Alpha Vantage."""
        try:
            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': symbol,
                'apikey': self.api_key,
                'outputsize': 'compact'  # Last 100 data points
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'Time Series (Daily)' in data:
                time_series = data['Time Series (Daily)']
                historical_data = []
                
                for date_str, daily_data in list(time_series.items())[:limit]:
                    # Convert date string to timestamp
                    import datetime
                    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                    timestamp = date_obj.timestamp()
                    
                    historical_data.append(MarketData(
                        symbol=symbol,
                        price=float(daily_data['4. close']),
                        volume=float(daily_data['5. volume']),
                        timestamp=timestamp,
                        additional_data={
                            'open': float(daily_data['1. open']),
                            'high': float(daily_data['2. high']),
                            'low': float(daily_data['3. low']),
                            'close': float(daily_data['4. close']),
                            'period': 'daily',
                            'date': date_str
                        }
                    ))
                
                return historical_data
            else:
                raise ValueError("Invalid response from Alpha Vantage API")
                
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Error fetching historical data from Alpha Vantage: {e}")
            # Fallback to dummy data
            dummy = DummyProvider()
            return dummy.get_historical_data(symbol, period, limit)
