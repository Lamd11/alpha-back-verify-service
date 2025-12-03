#!/usr/bin/env python3
"""
Consolidated unit tests for Lambda Function Handler
Tests S3 event processing, validation flow, and DynamoDB integration
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from io import BytesIO

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambda_function import lambda_handler, load_config, _complete_validation


class TestLambdaFunction:
    """Test suite for Lambda function handler"""

    @pytest.fixture
    def s3_event(self):
        """Create a mock S3 event"""
        return {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {
                            "key": "models/TestModel.class",
                            "size": 1024
                        }
                    }
                }
            ]
        }

    @pytest.fixture
    def mock_context(self):
        """Create a mock Lambda context"""
        context = Mock()
        context.function_name = "verify-service"
        context.memory_limit_in_mb = 128
        return context

    def test_load_config_success(self):
        """Test configuration loading succeeds"""
        security_config, validation_config = load_config()

        assert "allowed_packages" in security_config
        assert "blocked_packages" in security_config
        assert "blocked_classes" in security_config
        assert "blocked_methods" in security_config
        assert "max_file_size_bytes" in validation_config
        assert "required_interface" in validation_config
        assert "required_method_name" in validation_config
        assert "required_method_signature" in validation_config

    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_lambda_handler_missing_records(self, mock_dynamo, mock_s3, mock_context):
        """Test handler with invalid event (missing Records)"""
        event = {}
        response = lambda_handler(event, mock_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["verified"] is False
        assert any("eventParsing" in err for err in body["overallErrors"])

    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_lambda_handler_file_too_large(self, mock_dynamo, mock_s3, s3_event, mock_context):
        """Test handler rejects files that are too large"""
        s3_event["Records"][0]["s3"]["object"]["size"] = 11 * 1024 * 1024
        response = lambda_handler(s3_event, mock_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["verified"] is False
        assert any("fileSize" in err for err in body["overallErrors"])

    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_lambda_handler_s3_read_failure(self, mock_dynamo, mock_s3, s3_event, mock_context):
        """Test handler handles S3 read failures"""
        mock_s3.get_object.side_effect = Exception("S3 access denied")
        response = lambda_handler(s3_event, mock_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["verified"] is False
        assert any("s3FileReadable" in err for err in body["overallErrors"])

    @patch('lambda_function.JavaBytecodeScanner')
    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_lambda_handler_invalid_class_file(self, mock_dynamo, mock_s3, mock_scanner_class, s3_event, mock_context):
        """Test handler handles invalid class files"""
        mock_response = {"Body": BytesIO(b"not a valid class file")}
        mock_s3.get_object.return_value = mock_response
        
        mock_scanner = mock_scanner_class.return_value
        mock_scanner.get_class_info.return_value = {"error": "Cannot parse class"}
        
        response = lambda_handler(s3_event, mock_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["verified"] is False
        assert any("classFileValid" in err for err in body["overallErrors"])

    @patch('lambda_function.JavaBytecodeScanner')
    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_lambda_handler_missing_interface(self, mock_dynamo, mock_s3, mock_scanner_class, s3_event, mock_context):
        """Test handler detects missing Model interface"""
        mock_response = {"Body": BytesIO(b"dummy class bytes")}
        mock_s3.get_object.return_value = mock_response
        
        mock_scanner = mock_scanner_class.return_value
        mock_scanner.get_class_info.return_value = {
            "class_name": "TestModel",
            "interfaces": [],
            "methods": [],
            "version": "52.0"
        }
        
        def check_interface_side_effect(class_bytes, interface, report):
            report.add_check_failed("implementsInterface", "Does not implement Model interface")
            return False
        
        mock_scanner.check_implements_interface.side_effect = check_interface_side_effect
        
        response = lambda_handler(s3_event, mock_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["verified"] is False
        assert any("implementsInterface" in err for err in body["overallErrors"])

    @patch('lambda_function.JavaBytecodeScanner')
    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_lambda_handler_missing_method(self, mock_dynamo, mock_s3, mock_scanner_class, s3_event, mock_context):
        """Test handler detects missing simulateStep method"""
        mock_response = {"Body": BytesIO(b"dummy class bytes")}
        mock_s3.get_object.return_value = mock_response
        
        mock_scanner = mock_scanner_class.return_value
        mock_scanner.get_class_info.return_value = {
            "class_name": "TestModel",
            "interfaces": ["com/ttsudio/alphaback/Model"],
            "methods": [],
            "version": "52.0"
        }
        
        def check_interface_side_effect(class_bytes, interface, report):
            report.add_check_passed("implementsInterface")
            return True
        
        def check_method_side_effect(class_bytes, method_name, signature, report):
            report.add_check_failed("hasSimulateStep", "Missing required method: simulateStep")
            return False
        
        mock_scanner.check_implements_interface.side_effect = check_interface_side_effect
        mock_scanner.check_has_method.side_effect = check_method_side_effect
        
        response = lambda_handler(s3_event, mock_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["verified"] is False
        assert any("hasSimulateStep" in err for err in body["overallErrors"])

    @patch('lambda_function.JavaBytecodeScanner')
    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_lambda_handler_security_violation(self, mock_dynamo, mock_s3, mock_scanner_class, s3_event, mock_context):
        """Test handler detects security violations"""
        mock_response = {"Body": BytesIO(b"dummy class bytes")}
        mock_s3.get_object.return_value = mock_response
        
        mock_scanner = mock_scanner_class.return_value
        mock_scanner.get_class_info.return_value = {
            "class_name": "TestModel",
            "interfaces": ["com/ttsudio/alphaback/Model"],
            "methods": [{"name": "simulateStep", "signature": "(Lcom/ttsudio/alphaback/State;)Ljava/util/List;"}],
            "version": "52.0"
        }
        
        def check_interface_side_effect(class_bytes, interface, report):
            report.add_check_passed("implementsInterface")
            return True
        
        def check_method_side_effect(class_bytes, method_name, signature, report):
            report.add_check_passed("hasSimulateStep")
            return True
        
        def scan_class_side_effect(class_bytes, report, class_name):
            report.add_check_failed("securityScan", "Blocked method: java/lang/Runtime.exec")
            return False
        
        mock_scanner.check_implements_interface.side_effect = check_interface_side_effect
        mock_scanner.check_has_method.side_effect = check_method_side_effect
        mock_scanner.scan_class_file.side_effect = scan_class_side_effect
        
        response = lambda_handler(s3_event, mock_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["verified"] is False
        assert any("securityScan" in err for err in body["overallErrors"])

    @patch('lambda_function.JavaBytecodeScanner')
    @patch('lambda_function.s3_client')
    @patch('lambda_function.dynamodb')
    def test_lambda_handler_success(self, mock_dynamo, mock_s3, mock_scanner_class, s3_event, mock_context):
        """Test handler successfully validates a valid model"""
        mock_response = {"Body": BytesIO(b"dummy class bytes")}
        mock_s3.get_object.return_value = mock_response

        mock_table = Mock()
        mock_dynamo.Table.return_value = mock_table

        mock_scanner = mock_scanner_class.return_value
        mock_scanner.get_class_info.return_value = {
            "class_name": "TestModel",
            "interfaces": ["com/ttsudio/alphaback/Model"],
            "methods": [{"name": "simulateStep", "signature": "(Lcom/ttsudio/alphaback/State;)Ljava/util/List;"}],
            "version": "52.0"
        }
        mock_scanner.check_implements_interface.return_value = True
        mock_scanner.check_has_method.return_value = True
        mock_scanner.scan_class_file.return_value = True

        response = lambda_handler(s3_event, mock_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["verified"] is True
        assert body["modelId"] == "TestModel"
        assert len(body["overallErrors"]) == 0
        assert mock_table.put_item.called

    @patch('lambda_function.dynamodb')
    def test_complete_validation_dynamodb_error(self, mock_dynamo):
        """Test _complete_validation handles DynamoDB errors gracefully"""
        from verifier.report_generator import ReportGenerator

        mock_table = Mock()
        mock_table.put_item.side_effect = Exception("DynamoDB error")
        mock_dynamo.Table.return_value = mock_table

        report = ReportGenerator()
        report.start_timing()
        report.add_check_passed("fileSize")
        report.end_timing()

        response = _complete_validation(report, "test_model", "bucket", "key")

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["verified"] is True

    def test_model_id_extraction(self, mock_context):
        """Test model_id is correctly extracted from S3 key"""
        s3_event = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "uploads/models/MyCustomModel.class", "size": 1024}
                }
            }]
        }

        with patch('lambda_function.s3_client') as mock_s3, \
             patch('lambda_function.dynamodb'):
            mock_s3.get_object.side_effect = Exception("Stop early")
            response = lambda_handler(s3_event, mock_context)
            body = json.loads(response["body"])
            assert body["modelId"] == "MyCustomModel"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
