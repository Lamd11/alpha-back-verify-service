"""
Metadata Validator - FR1: Validate model metadata structure
Ensures models have proper configuration and expected input/output definitions
"""

import json
from typing import Dict, List, Any, Optional
from .report_generator import ReportGenerator


class MetadataValidator:
    """Validates metadata.json structure and content"""

    def __init__(self, required_fields: List[str]):
        """
        Initialize validator

        Args:
            required_fields: List of required metadata fields
        """
        self.required_fields = required_fields

    def validate(self, metadata_content: str, report: ReportGenerator) -> bool:
        """
        Validate metadata content

        Args:
            metadata_content: Raw metadata.json content
            report: Report generator to record results

        Returns:
            True if valid, False otherwise
        """
        try:
            # Parse JSON
            metadata = json.loads(metadata_content)
        except json.JSONDecodeError as e:
            report.add_error(
                "INVALID_JSON",
                f"metadata.json is not valid JSON: {str(e)}",
                "CRITICAL"
            )
            return False

        # Check required fields
        missing_fields = []
        for field in self.required_fields:
            if field not in metadata:
                missing_fields.append(field)

        if missing_fields:
            report.add_error(
                "MISSING_METADATA_FIELDS",
                f"Missing required fields in metadata.json: {', '.join(missing_fields)}",
                "CRITICAL"
            )
            return False

        # Validate field types and content
        validation_passed = True

        # Validate model_id
        if not isinstance(metadata.get("model_id"), str) or not metadata["model_id"].strip():
            report.add_error(
                "INVALID_MODEL_ID",
                "model_id must be a non-empty string",
                "CRITICAL"
            )
            validation_passed = False

        # Validate version
        if not isinstance(metadata.get("version"), str):
            report.add_error(
                "INVALID_VERSION",
                "version must be a string (e.g., '1.0.0')",
                "CRITICAL"
            )
            validation_passed = False

        # Validate author
        if not isinstance(metadata.get("author"), str) or not metadata["author"].strip():
            report.add_error(
                "INVALID_AUTHOR",
                "author must be a non-empty string",
                "CRITICAL"
            )
            validation_passed = False

        # Validate expected_inputs
        if not isinstance(metadata.get("expected_inputs"), dict):
            report.add_error(
                "INVALID_EXPECTED_INPUTS",
                "expected_inputs must be an object/dictionary",
                "CRITICAL"
            )
            validation_passed = False
        else:
            # Check for required input fields
            expected_inputs = metadata["expected_inputs"]
            required_inputs = ["stock_prices", "volume", "timestamps"]
            missing_inputs = [inp for inp in required_inputs if inp not in expected_inputs]

            if missing_inputs:
                report.add_error(
                    "MISSING_INPUT_FIELDS",
                    f"expected_inputs missing required fields: {', '.join(missing_inputs)}",
                    "CRITICAL"
                )
                validation_passed = False

        # Validate output_format
        if not isinstance(metadata.get("output_format"), dict):
            report.add_error(
                "INVALID_OUTPUT_FORMAT",
                "output_format must be an object/dictionary",
                "CRITICAL"
            )
            validation_passed = False
        else:
            # Check for required output fields
            output_format = metadata["output_format"]
            required_outputs = ["signal", "confidence"]
            missing_outputs = [out for out in required_outputs if out not in output_format]

            if missing_outputs:
                report.add_error(
                    "MISSING_OUTPUT_FIELDS",
                    f"output_format missing required fields: {', '.join(missing_outputs)}",
                    "CRITICAL"
                )
                validation_passed = False

        if validation_passed:
            report.add_check_passed("metadata_validation")

        return validation_passed

    def extract_model_id(self, metadata_content: str) -> Optional[str]:
        """
        Extract model_id from metadata

        Args:
            metadata_content: Raw metadata.json content

        Returns:
            model_id if found, None otherwise
        """
        try:
            metadata = json.loads(metadata_content)
            return metadata.get("model_id")
        except (json.JSONDecodeError, KeyError):
            return None
