"""
Report Generator - Produces structured verification reports
Outputs the verification result in a clean, UI-friendly format
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
import json


class ReportGenerator:
    """
    Generates verification reports in the format:
    {
        "modelId": "abc123",
        "verified": false,
        "checks": {
            "fileSize": {"passed": true},
            "classFileValid": {"passed": true},
            "implementsInterface": {"passed": false, "error": "..."},
            ...
        },
        "overallErrors": ["Error 1", "Error 2"],
        "executionTimeMs": 127,
        "timestamp": "2025-11-22T14:37:12Z"
    }
    """

    def __init__(self):
        self.checks: Dict[str, Dict[str, Any]] = {}
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def start_timing(self):
        """Start execution timer"""
        self.start_time = datetime.utcnow()

    def end_timing(self):
        """End execution timer"""
        self.end_time = datetime.utcnow()

    def add_check_passed(self, check_name: str):
        """Record a successful check"""
        self.checks[check_name] = {
            "passed": True
        }

    def add_check_failed(self, check_name: str, error: str):
        """Record a failed check with error message"""
        self.checks[check_name] = {
            "passed": False,
            "error": error
        }

    # Convenience method (maps old API to new)
    def add_error(self, check_name: str, error_message: str, severity: str = "CRITICAL"):
        """Add a failed check (backwards compatible)"""
        self.add_check_failed(check_name, error_message)

    def add_warning(self, check_name: str, message: str):
        """Add a warning to a check"""
        if check_name in self.checks:
            self.checks[check_name]["warning"] = message
        else:
            self.checks[check_name] = {
                "passed": True,
                "warning": message
            }

    def get_execution_time_ms(self) -> int:
        """Calculate execution time in milliseconds"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() * 1000)
        return 0

    def is_verified(self) -> bool:
        """Check if all checks passed"""
        if not self.checks:
            return False
        return all(check.get("passed", False) for check in self.checks.values())

    def get_overall_errors(self) -> List[str]:
        """Get list of all error messages"""
        errors = []
        for check_name, check_result in self.checks.items():
            if not check_result.get("passed", True):
                error_msg = check_result.get("error", "Check failed")
                errors.append(f"{check_name}: {error_msg}")
        return errors

    def generate_report(self, model_id: str) -> Dict[str, Any]:
        """
        Generate final verification report

        Args:
            model_id: Unique identifier for the model

        Returns:
            Structured report dictionary matching the schema
        """
        return {
            "modelId": model_id,
            "verified": self.is_verified(),
            "checks": self.checks,
            "overallErrors": self.get_overall_errors(),
            "executionTimeMs": self.get_execution_time_ms(),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    def to_json(self, model_id: str) -> str:
        """Generate report as JSON string"""
        return json.dumps(self.generate_report(model_id), indent=2)
