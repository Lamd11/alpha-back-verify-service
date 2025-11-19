"""
Valid Trading Model Example
This model passes all verification checks
"""

import pandas as pd
import numpy as np
from typing import Dict


class TradingModel:
    """
    A simple trend-following trading model
    Uses moving averages to generate buy/sell signals
    """

    def __init__(self):
        self.short_window = 10
        self.long_window = 30

    def predict(self, stock_prices, volume, timestamps):
        """
        Generate trading signal based on moving average crossover

        Args:
            stock_prices: Array of stock prices
            volume: Array of trading volumes
            timestamps: Array of timestamps

        Returns:
            Dictionary with signal and confidence
        """
        # Convert to pandas Series for easier computation
        prices = pd.Series(stock_prices)

        # Calculate moving averages
        short_ma = prices.rolling(window=self.short_window).mean()
        long_ma = prices.rolling(window=self.long_window).mean()

        # Get the most recent values
        current_short_ma = short_ma.iloc[-1]
        current_long_ma = long_ma.iloc[-1]
        previous_short_ma = short_ma.iloc[-2]
        previous_long_ma = long_ma.iloc[-2]

        # Generate signal based on crossover
        if current_short_ma > current_long_ma and previous_short_ma <= previous_long_ma:
            # Bullish crossover - buy signal
            signal = "BUY"
            confidence = 0.75
        elif current_short_ma < current_long_ma and previous_short_ma >= previous_long_ma:
            # Bearish crossover - sell signal
            signal = "SELL"
            confidence = 0.75
        else:
            # No clear signal - hold
            signal = "HOLD"
            confidence = 0.50

        # Adjust confidence based on volume
        volume_series = pd.Series(volume)
        recent_volume = volume_series.iloc[-5:].mean()
        overall_volume = volume_series.mean()

        if recent_volume > overall_volume * 1.5:
            # High volume confirms signal
            confidence = min(confidence + 0.15, 0.95)

        return {
            "signal": signal,
            "confidence": confidence
        }

    def get_model_info(self):
        """Return model configuration"""
        return {
            "name": "Moving Average Crossover",
            "short_window": self.short_window,
            "long_window": self.long_window,
            "strategy": "trend_following"
        }
