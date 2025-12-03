#!/usr/bin/env python3
"""
Integration tests for Verify Service
Tests full validation flow with mocked AWS services
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch
from io import BytesIO

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambda_function import lambda_handler


class TestVerifyServiceIntegration:
    """Integration test suite for full verification flow"""

    @pytest.fixture
    def valid_s3_event(self):
        """S3 event for a valid model upload"""
        return {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "alphaback-models"},
                        "object": {
                            "key": "models/ValidModel.class",
                            "size": 2048
                        }
                    }
                }
            ]
        }

    @pytest.fixture
    def invalid_s3_event(self):
        """S3 event for an invalid model upload"""
        return {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "alphaback-models"},
                        "object": {
                            "key": "models/InvalidModel.class",
                            "size": 1024
                        }
                    }
                }
            ]
        }

    @pytest.fixture
    def mock_context(self):
        """Mock Lambda context"""
        context = Mock()
        context.function_name = "verify-service"
        context.memory_limit_in_mb = 512
        context.request_id = "test-request-id"
        return context

    @patch('lambda_function.JavaBytecodeScanner')
    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_valid_model_full_flow(self, mock_dynamo, mock_s3, mock_scanner_class, valid_s3_event, mock_context):
        """
        Integration test: Valid model passes all checks
        Tests the complete validation pipeline from S3 to DynamoDB
        """
        # Setup S3 mock
        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"valid class file bytes")
        }

        # Setup DynamoDB mock
        mock_table = Mock()
        mock_dynamo.Table.return_value = mock_table

        # Setup bytecode scanner mock
        mock_scanner = mock_scanner_class.return_value
        mock_scanner.get_class_info.return_value = {
            "class_name": "com/ttsudio/alphaback/ValidModel",
            "interfaces": ["com/ttsudio/alphaback/Model"],
            "methods": [
                {
                    "name": "simulateStep",
                    "signature": "(Lcom/ttsudio/alphaback/State;)Ljava/util/List;"
                }
            ],
            "version": "52.0"
        }

        # Create side effects that modify report
        def check_interface_side_effect(class_bytes, interface, report):
            report.add_check_passed("implementsInterface")
            return True

        def check_method_side_effect(class_bytes, method_name, signature, report):
            report.add_check_passed("hasSimulateStep")
            return True

        def scan_class_side_effect(class_bytes, report, class_name):
            report.add_check_passed("securityScan")
            return True

        mock_scanner.check_implements_interface.side_effect = check_interface_side_effect
        mock_scanner.check_has_method.side_effect = check_method_side_effect
        mock_scanner.scan_class_file.side_effect = scan_class_side_effect

        # Execute Lambda handler
        response = lambda_handler(valid_s3_event, mock_context)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Check verification result
        assert body["verified"] is True
        assert body["modelId"] == "ValidModel"
        assert len(body["overallErrors"]) == 0

        # Check all required checks passed
        assert body["checks"]["fileSize"]["passed"] is True
        assert body["checks"]["s3FileReadable"]["passed"] is True
        assert body["checks"]["classFileValid"]["passed"] is True
        assert body["checks"]["implementsInterface"]["passed"] is True
        assert body["checks"]["hasSimulateStep"]["passed"] is True
        assert body["checks"]["securityScan"]["passed"] is True

        # Verify DynamoDB interactions
        assert mock_table.put_item.called
        assert mock_table.update_item.called

        # Verify S3 was accessed
        mock_s3.get_object.assert_called_once_with(
            Bucket="alphaback-models",
            Key="models/ValidModel.class"
        )

    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_invalid_class_file_full_flow(self, mock_dynamo, mock_s3, invalid_s3_event, mock_context):
        """
        Integration test: Invalid class file is rejected
        Tests that corrupted files are properly detected
        """
        # Setup S3 to return invalid bytes
        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"corrupted data not a class file")
        }

        mock_table = Mock()
        mock_dynamo.Table.return_value = mock_table

        # Execute Lambda handler
        response = lambda_handler(invalid_s3_event, mock_context)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Check verification failed
        assert body["verified"] is False
        assert body["modelId"] == "InvalidModel"
        assert len(body["overallErrors"]) > 0

        # Check that classFileValid check failed
        assert body["checks"]["classFileValid"]["passed"] is False

    @patch('lambda_function.JavaBytecodeScanner')
    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_security_violation_full_flow(self, mock_dynamo, mock_s3, mock_scanner_class, valid_s3_event, mock_context):
        """
        Integration test: Model with security violations is rejected
        Tests that dangerous code patterns are detected
        """
        # Setup S3
        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"malicious class file bytes")
        }

        mock_table = Mock()
        mock_dynamo.Table.return_value = mock_table

        # Setup scanner to detect security violations
        mock_scanner = mock_scanner_class.return_value
        mock_scanner.get_class_info.return_value = {
            "class_name": "com/ttsudio/alphaback/MaliciousModel",
            "interfaces": ["com/ttsudio/alphaback/Model"],
            "methods": [
                {
                    "name": "simulateStep",
                    "signature": "(Lcom/ttsudio/alphaback/State;)Ljava/util/List;"
                }
            ],
            "version": "52.0"
        }

        # Create side effects
        def check_interface_side_effect(class_bytes, interface, report):
            report.add_check_passed("implementsInterface")
            return True

        def check_method_side_effect(class_bytes, method_name, signature, report):
            report.add_check_passed("hasSimulateStep")
            return True

        def scan_class_side_effect(class_bytes, report, class_name):
            report.add_check_failed("securityScan", "Blocked class: java/lang/Runtime")
            return False

        mock_scanner.check_implements_interface.side_effect = check_interface_side_effect
        mock_scanner.check_has_method.side_effect = check_method_side_effect
        mock_scanner.scan_class_file.side_effect = scan_class_side_effect

        # Execute Lambda handler
        response = lambda_handler(valid_s3_event, mock_context)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Check verification failed
        assert body["verified"] is False
        assert len(body["overallErrors"]) > 0

        # Check security scan failed
        assert body["checks"]["securityScan"]["passed"] is False

    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_oversized_file_rejection(self, mock_dynamo, mock_s3, valid_s3_event, mock_context):
        """
        Integration test: Oversized files are rejected before download
        Tests file size validation
        """
        # Set file size to exceed 10MB limit
        valid_s3_event["Records"][0]["s3"]["object"]["size"] = 11 * 1024 * 1024

        mock_table = Mock()
        mock_dynamo.Table.return_value = mock_table

        # Execute Lambda handler
        response = lambda_handler(valid_s3_event, mock_context)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Check verification failed
        assert body["verified"] is False
        assert any("fileSize" in err for err in body["overallErrors"])

        # Verify S3 was NOT accessed (early rejection)
        mock_s3.get_object.assert_not_called()

    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_s3_access_failure(self, mock_dynamo, mock_s3, valid_s3_event, mock_context):
        """
        Integration test: S3 access failures are handled gracefully
        Tests error handling for AWS service failures
        """
        # Mock S3 to throw exception
        mock_s3.get_object.side_effect = Exception("Access Denied")

        mock_table = Mock()
        mock_dynamo.Table.return_value = mock_table

        # Execute Lambda handler
        response = lambda_handler(valid_s3_event, mock_context)

        # Verify response (should not crash)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Check verification failed
        assert body["verified"] is False
        assert any("s3FileReadable" in err for err in body["overallErrors"])

    @patch('lambda_function.JavaBytecodeScanner')
    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_dynamodb_write_failure_handled(self, mock_dynamo, mock_s3, mock_scanner_class, valid_s3_event, mock_context):
        """
        Integration test: DynamoDB write failures don't crash the handler
        Tests resilient error handling
        """
        # Setup S3
        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"valid class file bytes")
        }

        # Setup DynamoDB to fail
        mock_table = Mock()
        mock_table.put_item.side_effect = Exception("DynamoDB Unavailable")
        mock_dynamo.Table.return_value = mock_table

        # Setup scanner (all checks pass)
        mock_scanner = mock_scanner_class.return_value
        mock_scanner.get_class_info.return_value = {
            "class_name": "com/ttsudio/alphaback/ValidModel",
            "interfaces": ["com/ttsudio/alphaback/Model"],
            "methods": [{"name": "simulateStep", "signature": "(Lcom/ttsudio/alphaback/State;)Ljava/util/List;"}],
            "version": "52.0"
        }

        # Create side effects
        def check_interface_side_effect(class_bytes, interface, report):
            report.add_check_passed("implementsInterface")
            return True

        def check_method_side_effect(class_bytes, method_name, signature, report):
            report.add_check_passed("hasSimulateStep")
            return True

        def scan_class_side_effect(class_bytes, report, class_name):
            report.add_check_passed("securityScan")
            return True

        mock_scanner.check_implements_interface.side_effect = check_interface_side_effect
        mock_scanner.check_has_method.side_effect = check_method_side_effect
        mock_scanner.scan_class_file.side_effect = scan_class_side_effect

        # Execute Lambda handler (should not raise exception)
        response = lambda_handler(valid_s3_event, mock_context)

        # Verify response is still valid
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["verified"] is True

    @patch('lambda_function.JavaBytecodeScanner')
    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_multiple_validation_errors(self, mock_dynamo, mock_s3, mock_scanner_class, invalid_s3_event, mock_context):
        """
        Integration test: Multiple validation errors are properly collected
        Tests error aggregation
        """
        # Setup S3
        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"class file bytes")
        }

        mock_table = Mock()
        mock_dynamo.Table.return_value = mock_table

        # Setup scanner with multiple failures
        mock_scanner = mock_scanner_class.return_value
        mock_scanner.get_class_info.return_value = {
            "class_name": "com/example/BadModel",
            "interfaces": [],  # Missing required interface
            "methods": [],  # Missing required method
            "version": "52.0"
        }

        # Create side effect that fails interface check
        def check_interface_side_effect(class_bytes, interface, report):
            report.add_check_failed("implementsInterface", "Does not implement Model interface")
            return False

        mock_scanner.check_implements_interface.side_effect = check_interface_side_effect

        # Execute Lambda handler
        response = lambda_handler(invalid_s3_event, mock_context)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Check verification failed with multiple errors
        assert body["verified"] is False
        assert len(body["overallErrors"]) >= 1

        # Should have implementsInterface error
        assert any("implementsInterface" in err for err in body["overallErrors"])

    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_response_structure_compliance(self, mock_dynamo, mock_s3, valid_s3_event, mock_context):
        """
        Integration test: Response structure matches expected API contract
        Tests API schema compliance
        """
        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"any bytes")
        }

        mock_table = Mock()
        mock_dynamo.Table.return_value = mock_table

        # Execute Lambda handler
        response = lambda_handler(valid_s3_event, mock_context)

        # Verify response structure
        assert "statusCode" in response
        assert "body" in response
        assert response["statusCode"] == 200

        body = json.loads(response["body"])

        # Verify required fields exist
        required_fields = ["modelId", "verified", "checks", "overallErrors", "executionTimeMs", "timestamp"]
        for field in required_fields:
            assert field in body, f"Missing required field: {field}"

        # Verify data types
        assert isinstance(body["modelId"], str)
        assert isinstance(body["verified"], bool)
        assert isinstance(body["checks"], dict)
        assert isinstance(body["overallErrors"], list)
        assert isinstance(body["executionTimeMs"], int)
        assert isinstance(body["timestamp"], str)

        # Verify timestamp format
        assert body["timestamp"].endswith("Z")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
