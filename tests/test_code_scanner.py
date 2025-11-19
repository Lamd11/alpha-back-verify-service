"""
Unit tests for CodeScanner module
Tests AST-based security scanning functionality
"""

import pytest
from src.verifier.code_scanner import CodeScanner
from src.verifier.report_generator import ReportGenerator


class TestCodeScanner:
    """Test cases for code security scanning"""

    @pytest.fixture
    def scanner(self):
        """Create a CodeScanner instance with standard config"""
        allowed_imports = ['numpy', 'pandas', 'datetime', 'typing', 'math']
        blocked_imports = ['os', 'sys', 'subprocess', 'socket']
        blocked_builtins = ['eval', 'exec', '__import__', 'open']
        return CodeScanner(allowed_imports, blocked_imports, blocked_builtins)

    @pytest.fixture
    def report(self):
        """Create a fresh report generator"""
        return ReportGenerator()

    def test_valid_code_passes(self, scanner, report):
        """Test that safe code passes validation"""
        code = """
import pandas as pd
import numpy as np

class TradingModel:
    def predict(self, stock_prices, volume, timestamps):
        prices = pd.Series(stock_prices)
        return {"signal": "BUY", "confidence": 0.85}
"""
        result = scanner.scan(code, report)
        assert result is True
        assert len(report.errors) == 0

    def test_disallowed_import_fails(self, scanner, report):
        """Test that disallowed imports are caught"""
        code = """
import os
import pandas as pd

class TradingModel:
    def predict(self, stock_prices, volume, timestamps):
        return {"signal": "BUY", "confidence": 0.85}
"""
        result = scanner.scan(code, report)
        assert result is False
        assert len(report.errors) > 0
        assert any('os' in error['message'] for error in report.errors)

    def test_eval_builtin_fails(self, scanner, report):
        """Test that eval() calls are caught"""
        code = """
import pandas as pd

class TradingModel:
    def predict(self, stock_prices, volume, timestamps):
        result = eval("1 + 1")
        return {"signal": "BUY", "confidence": 0.85}
"""
        result = scanner.scan(code, report)
        assert result is False
        assert any('eval' in error['message'] for error in report.errors)

    def test_exec_builtin_fails(self, scanner, report):
        """Test that exec() calls are caught"""
        code = """
import pandas as pd

class TradingModel:
    def predict(self, stock_prices, volume, timestamps):
        exec("print('hello')")
        return {"signal": "BUY", "confidence": 0.85}
"""
        result = scanner.scan(code, report)
        assert result is False
        assert any('exec' in error['message'] for error in report.errors)

    def test_open_builtin_fails(self, scanner, report):
        """Test that open() calls are caught"""
        code = """
import pandas as pd

class TradingModel:
    def predict(self, stock_prices, volume, timestamps):
        with open('/etc/passwd', 'r') as f:
            data = f.read()
        return {"signal": "BUY", "confidence": 0.85}
"""
        result = scanner.scan(code, report)
        assert result is False
        assert any('open' in error['message'].lower() for error in report.errors)

    def test_subprocess_import_fails(self, scanner, report):
        """Test that subprocess import is blocked"""
        code = """
import subprocess
import pandas as pd

class TradingModel:
    def predict(self, stock_prices, volume, timestamps):
        subprocess.run(['ls'])
        return {"signal": "BUY", "confidence": 0.85}
"""
        result = scanner.scan(code, report)
        assert result is False
        assert any('subprocess' in error['message'] for error in report.errors)

    def test_syntax_error_fails(self, scanner, report):
        """Test that syntax errors are caught"""
        code = """
import pandas as pd

class TradingModel
    def predict(self, stock_prices, volume, timestamps):
        return {"signal": "BUY", "confidence": 0.85}
"""
        result = scanner.scan(code, report)
        assert result is False
        assert any('syntax' in error['message'].lower() for error in report.errors)

    def test_multiple_violations(self, scanner, report):
        """Test that multiple violations are all caught"""
        code = """
import os
import sys
import pandas as pd

class TradingModel:
    def predict(self, stock_prices, volume, timestamps):
        eval("1+1")
        exec("print('test')")
        return {"signal": "BUY", "confidence": 0.85}
"""
        result = scanner.scan(code, report)
        assert result is False
        assert len(report.errors) >= 4  # os, sys, eval, exec

    def test_from_import_blocked(self, scanner, report):
        """Test that 'from' imports are also blocked"""
        code = """
from os import path
import pandas as pd

class TradingModel:
    def predict(self, stock_prices, volume, timestamps):
        return {"signal": "BUY", "confidence": 0.85}
"""
        result = scanner.scan(code, report)
        assert result is False
        assert any('os' in error['message'] for error in report.errors)

    def test_import_summary(self, scanner):
        """Test import summary generation"""
        code = """
import pandas as pd
import numpy as np
from datetime import datetime
"""
        summary = scanner.get_import_summary(code)
        assert summary['total_imports'] == 3
        assert 'pandas' in summary['imports']
        assert 'numpy' in summary['imports']
        assert 'datetime' in summary['from_imports']
