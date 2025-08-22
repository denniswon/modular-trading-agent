"""
Example trading strategy implementations.

This module contains concrete implementations of SignalProcessor.
"""

import statistics
from typing import Dict, Any, Optional
from .base import SignalProcessor, TradingSignal, MarketData, SignalType


class SimpleStrategy(SignalProcessor):
    """Simple price momentum strategy."""
    
    def __init__(self, buy_threshold: float = 0.02, sell_threshold: float = -0.015):
        self.buy_threshold = buy_threshold  # 2% price increase
        self.sell_threshold = sell_threshold  # -1.5% price decrease
        self.last_price = None
        
    def generate_signal(self, data: MarketData, historical_data: Optional[list[MarketData]] = None) -> TradingSignal:
        """Generate signal based on simple price momentum."""
        
        # If we don't have historical data, use conservative approach
        if not self.last_price:
            self.last_price = data.price
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.HOLD,
                confidence=0.5,
                metadata={'reason': 'Initial price recorded, holding'}
            )
        
        # Calculate price change percentage
        price_change = (data.price - self.last_price) / self.last_price
        self.last_price = data.price
        
        # Determine signal based on thresholds
        if price_change >= self.buy_threshold:
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.BUY,
                confidence=min(0.9, 0.5 + abs(price_change) * 2),
                quantity=1.0,
                price=data.price,
                metadata={
                    'price_change': price_change,
                    'threshold': self.buy_threshold,
                    'reason': f'Price increased by {price_change:.2%}'
                }
            )
        elif price_change <= self.sell_threshold:
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.SELL,
                confidence=min(0.9, 0.5 + abs(price_change) * 2),
                quantity=1.0,
                price=data.price,
                metadata={
                    'price_change': price_change,
                    'threshold': self.sell_threshold,
                    'reason': f'Price decreased by {price_change:.2%}'
                }
            )
        else:
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.HOLD,
                confidence=0.7,
                metadata={
                    'price_change': price_change,
                    'reason': 'Price change within hold thresholds'
                }
            )
    
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update strategy parameters."""
        if 'buy_threshold' in parameters:
            self.buy_threshold = parameters['buy_threshold']
        if 'sell_threshold' in parameters:
            self.sell_threshold = parameters['sell_threshold']


class MovingAverageStrategy(SignalProcessor):
    """Moving average crossover strategy."""
    
    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window
        self.price_history = []
        
    def generate_signal(self, data: MarketData, historical_data: Optional[list[MarketData]] = None) -> TradingSignal:
        """Generate signal based on moving average crossover."""
        
        # Update price history
        self.price_history.append(data.price)
        
        # Use historical data if provided, otherwise use internal history
        if historical_data and len(historical_data) >= self.long_window:
            prices = [d.price for d in historical_data[-self.long_window:]]
            prices.append(data.price)  # Add current price
        else:
            prices = self.price_history
            
        # Keep only the data we need
        if len(prices) > self.long_window:
            prices = prices[-self.long_window:]
            self.price_history = prices
        
        # Need enough data for long moving average
        if len(prices) < self.long_window:
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.HOLD,
                confidence=0.3,
                metadata={'reason': f'Insufficient data: {len(prices)}/{self.long_window}'}
            )
        
        # Calculate moving averages
        short_ma = statistics.mean(prices[-self.short_window:])
        long_ma = statistics.mean(prices)
        
        # Calculate previous short MA for crossover detection
        if len(prices) > self.short_window:
            prev_short_ma = statistics.mean(prices[-(self.short_window+1):-1])
            prev_long_ma = statistics.mean(prices[:-1])
        else:
            # Not enough data for crossover detection
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.HOLD,
                confidence=0.5,
                metadata={
                    'short_ma': short_ma,
                    'long_ma': long_ma,
                    'reason': 'Insufficient data for crossover detection'
                }
            )
        
        # Detect crossovers
        bullish_crossover = (prev_short_ma <= prev_long_ma) and (short_ma > long_ma)
        bearish_crossover = (prev_short_ma >= prev_long_ma) and (short_ma < long_ma)
        
        # Calculate signal strength based on MA separation
        ma_separation = abs(short_ma - long_ma) / long_ma
        confidence = min(0.95, 0.6 + ma_separation * 10)
        
        if bullish_crossover:
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.BUY,
                confidence=confidence,
                quantity=1.0,
                price=data.price,
                metadata={
                    'short_ma': short_ma,
                    'long_ma': long_ma,
                    'ma_separation': ma_separation,
                    'reason': f'Bullish crossover: MA{self.short_window} > MA{self.long_window}'
                }
            )
        elif bearish_crossover:
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.SELL,
                confidence=confidence,
                quantity=1.0,
                price=data.price,
                metadata={
                    'short_ma': short_ma,
                    'long_ma': long_ma,
                    'ma_separation': ma_separation,
                    'reason': f'Bearish crossover: MA{self.short_window} < MA{self.long_window}'
                }
            )
        else:
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.HOLD,
                confidence=0.6,
                metadata={
                    'short_ma': short_ma,
                    'long_ma': long_ma,
                    'ma_separation': ma_separation,
                    'reason': 'No crossover detected'
                }
            )
    
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update strategy parameters."""
        if 'short_window' in parameters:
            self.short_window = parameters['short_window']
        if 'long_window' in parameters:
            self.long_window = parameters['long_window']


class RSIStrategy(SignalProcessor):
    """RSI (Relative Strength Index) strategy."""
    
    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.price_history = []
        
    def calculate_rsi(self, prices: list[float]) -> float:
        """Calculate RSI for given prices."""
        if len(prices) < self.period + 1:
            return 50.0  # Neutral RSI
            
        # Calculate price changes
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        # Separate gains and losses
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        # Calculate average gains and losses
        if len(gains) < self.period:
            return 50.0
            
        avg_gain = statistics.mean(gains[-self.period:])
        avg_loss = statistics.mean(losses[-self.period:])
        
        # Calculate RSI
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def generate_signal(self, data: MarketData, historical_data: Optional[list[MarketData]] = None) -> TradingSignal:
        """Generate signal based on RSI levels."""
        
        # Update price history
        self.price_history.append(data.price)
        
        # Use historical data if provided
        if historical_data and len(historical_data) >= self.period:
            prices = [d.price for d in historical_data[-(self.period + 10):]]  # Get extra data for better RSI
            prices.append(data.price)
        else:
            prices = self.price_history
            
        # Keep reasonable history size
        if len(prices) > self.period * 3:
            prices = prices[-(self.period * 2):]
            self.price_history = prices
        
        # Calculate RSI
        rsi = self.calculate_rsi(prices)
        
        # Generate signal based on RSI levels
        if rsi <= self.oversold:
            confidence = min(0.9, 0.5 + (self.oversold - rsi) / self.oversold)
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.BUY,
                confidence=confidence,
                quantity=1.0,
                price=data.price,
                metadata={
                    'rsi': rsi,
                    'oversold_threshold': self.oversold,
                    'reason': f'RSI oversold: {rsi:.1f} <= {self.oversold}'
                }
            )
        elif rsi >= self.overbought:
            confidence = min(0.9, 0.5 + (rsi - self.overbought) / (100 - self.overbought))
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.SELL,
                confidence=confidence,
                quantity=1.0,
                price=data.price,
                metadata={
                    'rsi': rsi,
                    'overbought_threshold': self.overbought,
                    'reason': f'RSI overbought: {rsi:.1f} >= {self.overbought}'
                }
            )
        else:
            return TradingSignal(
                symbol=data.symbol,
                signal_type=SignalType.HOLD,
                confidence=0.6,
                metadata={
                    'rsi': rsi,
                    'oversold_threshold': self.oversold,
                    'overbought_threshold': self.overbought,
                    'reason': f'RSI neutral: {rsi:.1f}'
                }
            )
    
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update strategy parameters."""
        if 'period' in parameters:
            self.period = parameters['period']
        if 'oversold' in parameters:
            self.oversold = parameters['oversold']
        if 'overbought' in parameters:
            self.overbought = parameters['overbought']


class ComboStrategy(SignalProcessor):
    """Combination strategy using multiple indicators."""
    
    def __init__(self):
        self.ma_strategy = MovingAverageStrategy(short_window=5, long_window=15)
        self.rsi_strategy = RSIStrategy(period=14)
        
    def generate_signal(self, data: MarketData, historical_data: Optional[list[MarketData]] = None) -> TradingSignal:
        """Generate signal by combining multiple strategies."""
        
        # Get signals from individual strategies
        ma_signal = self.ma_strategy.generate_signal(data, historical_data)
        rsi_signal = self.rsi_strategy.generate_signal(data, historical_data)
        
        # Combine signals with weights
        ma_weight = 0.6
        rsi_weight = 0.4
        
        # Calculate combined confidence
        combined_confidence = (ma_signal.confidence * ma_weight + 
                             rsi_signal.confidence * rsi_weight)
        
        # Determine final signal
        if ma_signal.signal_type == rsi_signal.signal_type:
            # Both strategies agree
            final_signal_type = ma_signal.signal_type
            final_confidence = min(0.95, combined_confidence * 1.2)  # Boost confidence when strategies agree
        elif ma_signal.signal_type == SignalType.HOLD or rsi_signal.signal_type == SignalType.HOLD:
            # One strategy suggests hold
            final_signal_type = SignalType.HOLD
            final_confidence = combined_confidence * 0.8
        else:
            # Strategies disagree (one buy, one sell)
            final_signal_type = SignalType.HOLD
            final_confidence = 0.4  # Low confidence when strategies conflict
        
        return TradingSignal(
            symbol=data.symbol,
            signal_type=final_signal_type,
            confidence=final_confidence,
            quantity=1.0 if final_signal_type != SignalType.HOLD else None,
            price=data.price,
            metadata={
                'ma_signal': ma_signal.signal_type.value,
                'ma_confidence': ma_signal.confidence,
                'ma_metadata': ma_signal.metadata,
                'rsi_signal': rsi_signal.signal_type.value,
                'rsi_confidence': rsi_signal.confidence,
                'rsi_metadata': rsi_signal.metadata,
                'reason': 'Combined MA and RSI strategy'
            }
        )
    
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update parameters for underlying strategies."""
        if 'ma_short_window' in parameters:
            self.ma_strategy.update_parameters({'short_window': parameters['ma_short_window']})
        if 'ma_long_window' in parameters:
            self.ma_strategy.update_parameters({'long_window': parameters['ma_long_window']})
        if 'rsi_period' in parameters:
            self.rsi_strategy.update_parameters({'period': parameters['rsi_period']})
        if 'rsi_oversold' in parameters:
            self.rsi_strategy.update_parameters({'oversold': parameters['rsi_oversold']})
        if 'rsi_overbought' in parameters:
            self.rsi_strategy.update_parameters({'overbought': parameters['rsi_overbought']})
