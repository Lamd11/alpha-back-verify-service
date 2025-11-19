"""
Report Generator - FR3: Generate verification reports
Produces structured validation results for Model Registry
"""

from datetime import datetime
from typing import Dict, List, Any
import json


class ReportGenerator:
    """Generates standardized verification reports"""

    def __init__(self):
        self.checks_passed = []
        self.errors = []
        self.warnings = []
        self.start_time = None
        self.end_time = None

    def start_timing(self):
        """Start execution timer"""
        self.start_time = datetime.utcnow()

    def end_timing(self):
        """End execution timer"""
        self.end_time = datetime.utcnow()

    def add_check_passed(self, check_name: str):
        """Record a successful validation check"""
        self.checks_passed.append(check_name)

    def add_error(self, code: str, message: str, severity: str = "CRITICAL"):
        """Add an error to the report"""
        self.errors.append({
            "code": code,
            "message": message,
            "severity": severity
        })

    def add_warning(self, code: str, message: str):
        """Add a warning to the report"""
        self.warnings.append({
            "code": code,
            "message": message
        })

    def get_execution_time_ms(self) -> int:
        """Calculate execution time in milliseconds"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() * 1000)
        return 0

    def is_valid(self) -> bool:
        """Check if model passed all validations"""
        return len(self.errors) == 0

    def generate_report(self, model_id: str) -> Dict[str, Any]:
        """
        Generate final verification report

        Args:
            model_id: Unique identifier for the model

        Returns:
            Structured report dictionary
        """
        status = "VALID" if self.is_valid() else "INVALID"

        report = {
            "model_id": model_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks_passed": self.checks_passed,
            "execution_time_ms": self.get_execution_time_ms()
        }

        # Add warnings if any exist
        if self.warnings:
            report["warnings"] = self.warnings

        # Add errors if validation failed
        if not self.is_valid():
            report["errors"] = self.errors

        return report

    def to_json(self, model_id: str) -> str:
        """Generate report as JSON string"""
        return json.dumps(self.generate_report(model_id), indent=2)

    def to_dynamodb_item(self, model_id: str) -> Dict[str, Any]:
        """
        Convert report to DynamoDB item format

        Returns:
            Dictionary formatted for DynamoDB put_item
        """
        report = self.generate_report(model_id)

        return {
            "model_id": model_id,
            "validation_status": report["status"],
            "validation_timestamp": report["timestamp"],
            "validation_report": json.dumps(report),
            "checks_passed": report["checks_passed"],
            "has_errors": not self.is_valid(),
            "execution_time_ms": report["execution_time_ms"]
        }
