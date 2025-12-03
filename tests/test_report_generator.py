#!/usr/bin/env python3
"""
Consolidated unit tests for ReportGenerator
Tests report generation, timing, and check tracking
"""

import pytest
import json
from datetime import datetime
import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from verifier.report_generator import ReportGenerator


class TestReportGenerator:
    """Test suite for ReportGenerator class"""

    @pytest.mark.parametrize("check_name,passed,error_msg", [
        ("fileSize", True, None),
        ("classFileValid", False, "Invalid class file format"),
        ("implementsInterface", True, None),
        ("hasSimulateStep", False, "Missing required method"),
        ("securityScan", False, "Blocked method found"),
    ])
    def test_add_checks(self, check_name, passed, error_msg):
        """Test adding passed and failed checks"""
        report = ReportGenerator()
        
        if passed:
            report.add_check_passed(check_name)
            assert report.checks[check_name]["passed"] is True
        else:
            report.add_check_failed(check_name, error_msg)
            assert report.checks[check_name]["passed"] is False
            assert report.checks[check_name]["error"] == error_msg

    def test_timing(self):
        """Test execution timing functionality"""
        report = ReportGenerator()
        report.start_timing()
        time.sleep(0.01)
        report.end_timing()
        
        execution_time = report.get_execution_time_ms()
        assert execution_time >= 10
        assert execution_time < 100

    @pytest.mark.parametrize("checks,expected_verified", [
        ([("fileSize", True), ("classFileValid", True), ("implementsInterface", True)], True),
        ([("fileSize", True), ("classFileValid", False, "error"), ("implementsInterface", True)], False),
        ([], False),
    ])
    def test_is_verified(self, checks, expected_verified):
        """Test verification status with various check combinations"""
        report = ReportGenerator()
        
        for check in checks:
            if check[1]:
                report.add_check_passed(check[0])
            else:
                report.add_check_failed(check[0], check[2])
        
        assert report.is_verified() is expected_verified

    def test_get_overall_errors(self):
        """Test overall errors collection"""
        report = ReportGenerator()
        report.add_check_passed("fileSize")
        report.add_check_failed("classFileValid", "Invalid format")
        report.add_check_failed("securityScan", "Blocked method found")
        
        errors = report.get_overall_errors()
        assert len(errors) == 2
        assert any("classFileValid" in err for err in errors)
        assert any("securityScan" in err for err in errors)

    def test_generate_report_structure(self):
        """Test generated report has correct structure and values"""
        report = ReportGenerator()
        report.start_timing()
        report.add_check_passed("fileSize")
        report.add_check_failed("classFileValid", "Error message")
        report.end_timing()
        
        result = report.generate_report("test_model")
        
        # Check required fields
        assert result["modelId"] == "test_model"
        assert result["verified"] is False
        assert len(result["checks"]) == 2
        assert len(result["overallErrors"]) == 1
        assert result["executionTimeMs"] >= 0
        assert "timestamp" in result
        assert result["timestamp"].endswith("Z")

    def test_to_json(self):
        """Test JSON serialization"""
        report = ReportGenerator()
        report.add_check_passed("fileSize")
        report.add_check_failed("classFileValid", "Invalid")
        
        json_str = report.to_json("test_model")
        parsed = json.loads(json_str)
        
        assert parsed["modelId"] == "test_model"
        assert parsed["verified"] is False
        assert len(parsed["checks"]) == 2

    def test_add_warning_and_error(self):
        """Test adding warnings and errors to checks"""
        report = ReportGenerator()
        report.add_check_passed("fileSize")
        report.add_warning("fileSize", "File is large but acceptable")
        
        assert report.checks["fileSize"]["passed"] is True
        assert report.checks["fileSize"]["warning"] == "File is large but acceptable"
        
        # Test backwards compatible add_error method
        report.add_error("securityScan", "Security violation", "CRITICAL")
        assert report.checks["securityScan"]["passed"] is False
        assert report.checks["securityScan"]["error"] == "Security violation"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
