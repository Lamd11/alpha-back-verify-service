"""
Invalid Trading Model Example - Contains Security Violations
This model will FAIL verification due to disallowed imports and operations
"""

import pandas as pd
import numpy as np
import os  # VIOLATION: Disallowed import
import subprocess  # VIOLATION: Disallowed import
from typing import Dict


class TradingModel:
    """
    A malicious trading model that attempts dangerous operations
    """

    def __init__(self):
        self.config_file = "/etc/passwd"  # Suspicious

    def predict(self, stock_prices, volume, timestamps):
        """
        This model attempts to perform unauthorized operations
        """
        # VIOLATION: Attempting to read system files
        try:
            with open(self.config_file, 'r') as f:
                data = f.read()
        except:
            pass

        # VIOLATION: Attempting to execute system commands
        try:
            result = subprocess.run(['ls', '-la'], capture_output=True)
        except:
            pass

        # VIOLATION: Using eval
        code = "1 + 1"
        eval(code)

        # Some actual trading logic (but will be rejected anyway)
        prices = pd.Series(stock_prices)
        signal = "BUY" if prices.iloc[-1] > prices.mean() else "SELL"

        return {
            "signal": signal,
            "confidence": 0.80
        }

    def steal_data(self):
        """Suspicious method that shouldn't be here"""
        # VIOLATION: Network access attempt
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        return sock
