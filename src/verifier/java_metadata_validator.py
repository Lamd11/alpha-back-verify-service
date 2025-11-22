"""
Java Model Metadata Validator - FR1: Validate Java model metadata structure
Ensures models have proper configuration for Java-based trading models
"""

import json
from typing import Dict, List, Any, Optional
from .report_generator import ReportGenerator


class JavaMetadataValidator:
    """Validates metadata.json structure and content for Java models"""

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

        # Validate model_class (NEW - required for Java models)
        if not isinstance(metadata.get("model_class"), str) or not metadata["model_class"].strip():
            report.add_error(
                "INVALID_MODEL_CLASS",
                "model_class must be a non-empty string (fully qualified class name)",
                "CRITICAL"
            )
            validation_passed = False
        else:
            # Validate that model_class looks like a valid Java class name
            model_class = metadata["model_class"]
            if not self._is_valid_java_class_name(model_class):
                report.add_error(
                    "INVALID_MODEL_CLASS_FORMAT",
                    f"model_class '{model_class}' is not a valid Java class name. "
                    f"Expected format: com.example.MyModel",
                    "CRITICAL"
                )
                validation_passed = False

        if validation_passed:
            report.add_check_passed("metadata_validation")

        return validation_passed

    def _is_valid_java_class_name(self, class_name: str) -> bool:
        """
        Check if string is a valid Java fully qualified class name

        Args:
            class_name: Class name to validate

        Returns:
            True if valid
        """
        # Basic validation: should contain at least one dot and valid characters
        if '.' not in class_name:
            return False

        parts = class_name.split('.')
        for part in parts:
            if not part:  # Empty part
                return False
            # Check if part starts with letter and contains only valid Java identifier chars
            if not part[0].isalpha() and part[0] != '_':
                return False
            if not all(c.isalnum() or c == '_' for c in part):
                return False

        return True

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

    def extract_model_class(self, metadata_content: str) -> Optional[str]:
        """
        Extract model_class from metadata

        Args:
            metadata_content: Raw metadata.json content

        Returns:
            model_class (fully qualified class name) if found, None otherwise
        """
        try:
            metadata = json.loads(metadata_content)
            return metadata.get("model_class")
        except (json.JSONDecodeError, KeyError):
            return None

    def extract_metadata(self, metadata_content: str) -> Optional[Dict[str, Any]]:
        """
        Extract full metadata as dictionary

        Args:
            metadata_content: Raw metadata.json content

        Returns:
            Metadata dictionary if valid JSON, None otherwise
        """
        try:
            return json.loads(metadata_content)
        except json.JSONDecodeError:
            return None
