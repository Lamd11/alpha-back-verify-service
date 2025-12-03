#!/usr/bin/env python3
"""
Consolidated unit tests for JavaBytecodeScanner
Tests bytecode scanning, security checks, and validation logic
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from verifier.java_bytecode_scanner import JavaBytecodeScanner
from verifier.report_generator import ReportGenerator


class TestJavaBytecodeScanner:
    """Test suite for JavaBytecodeScanner class"""

    @pytest.fixture
    def scanner(self):
        """Create a scanner with test configuration"""
        return JavaBytecodeScanner(
            allowed_packages=["java/util", "java/lang", "com/ttsudio/alphaback"],
            blocked_packages=["java/io", "java/net", "java/lang/reflect"],
            blocked_classes=["java/lang/Runtime", "java/lang/System"],
            blocked_methods=["java/lang/Runtime.exec", "java/lang/System.exit"]
        )

    @pytest.fixture
    def mock_report(self):
        """Create a mock report generator"""
        return ReportGenerator()

    def test_scanner_initialization(self, scanner):
        """Test scanner initializes with correct configuration"""
        assert "java/util" in scanner.allowed_packages
        assert "java/io" in scanner.blocked_packages
        assert "java/lang/Runtime" in scanner.blocked_classes
        assert "java/lang/Runtime.exec" in scanner.blocked_methods

    @patch('verifier.java_bytecode_scanner.ClassFile')
    def test_get_class_info_invalid_bytes(self, mock_classfile, scanner):
        """Test get_class_info with invalid class bytes"""
        mock_classfile.side_effect = Exception("Invalid bytecode")
        result = scanner.get_class_info(b"not a valid class file")
        assert "error" in result

    @patch('verifier.java_bytecode_scanner.ClassFile')
    def test_get_class_info_success(self, mock_classfile, scanner):
        """Test get_class_info successfully parses valid class"""
        mock_cf = Mock()
        mock_cf.this.name.value = "com/example/TestClass"
        mock_cf.version = (52, 0)
        
        mock_interface = Mock()
        mock_interface.name.value = "java/io/Serializable"
        mock_cf.interfaces = [mock_interface]
        
        mock_method = Mock()
        mock_method.name.value = "testMethod"
        mock_method.descriptor.value = "()V"
        mock_cf.methods = [mock_method]
        
        mock_classfile.return_value = mock_cf
        
        result = scanner.get_class_info(b"dummy bytes")
        assert "error" not in result
        assert result["class_name"] == "com/example/TestClass"
        assert result["version"] == "52.0"

    @pytest.mark.parametrize("interface_name,should_pass", [
        ("com/ttsudio/alphaback/Model", True),
        ("java/io/Serializable", False),
    ])
    @patch('verifier.java_bytecode_scanner.ClassFile')
    def test_check_implements_interface(self, mock_classfile, scanner, mock_report, interface_name, should_pass):
        """Test interface checking with various scenarios"""
        mock_cf = Mock()
        mock_interface = Mock()
        mock_interface.name.value = interface_name
        mock_cf.interfaces = [mock_interface]
        mock_classfile.return_value = mock_cf
        
        result = scanner.check_implements_interface(
            b"dummy bytes",
            "com/ttsudio/alphaback/Model",
            mock_report
        )
        
        assert result is should_pass
        assert mock_report.checks["implementsInterface"]["passed"] is should_pass

    @patch('verifier.java_bytecode_scanner.ClassFile')
    def test_check_implements_interface_parse_error(self, mock_classfile, scanner, mock_report):
        """Test interface check handles parse errors"""
        mock_classfile.side_effect = Exception("Parse error")
        result = scanner.check_implements_interface(b"dummy bytes", "com/ttsudio/alphaback/Model", mock_report)
        assert result is False
        assert mock_report.checks["implementsInterface"]["passed"] is False

    @pytest.mark.parametrize("method_sig,expected_sig,should_pass", [
        ("(Lcom/ttsudio/alphaback/State;)Ljava/util/List;", "(Lcom/ttsudio/alphaback/State;)Ljava/util/List;", True),
        ("()V", "(Lcom/ttsudio/alphaback/State;)Ljava/util/List;", False),
    ])
    @patch('verifier.java_bytecode_scanner.ClassFile')
    def test_check_has_method(self, mock_classfile, scanner, mock_report, method_sig, expected_sig, should_pass):
        """Test method checking with correct and incorrect signatures"""
        mock_cf = Mock()
        mock_method = Mock()
        mock_method.name.value = "simulateStep"
        mock_method.descriptor.value = method_sig
        mock_cf.methods = [mock_method]
        mock_classfile.return_value = mock_cf
        
        result = scanner.check_has_method(b"dummy bytes", "simulateStep", expected_sig, mock_report)
        assert result is should_pass
        assert mock_report.checks["hasSimulateStep"]["passed"] is should_pass

    @patch('verifier.java_bytecode_scanner.ClassFile')
    def test_check_has_method_missing(self, mock_classfile, scanner, mock_report):
        """Test method check when method is missing"""
        mock_cf = Mock()
        mock_cf.methods = []
        mock_classfile.return_value = mock_cf
        
        result = scanner.check_has_method(b"dummy bytes", "simulateStep", "(Lcom/ttsudio/alphaback/State;)Ljava/util/List;", mock_report)
        assert result is False
        assert "Missing required method" in mock_report.checks["hasSimulateStep"]["error"]

    @pytest.mark.parametrize("class_name,is_blocked,violation_msg", [
        ("java/util/ArrayList", False, None),
        ("java/lang/Runtime", True, "Blocked class"),
        ("java/io/FileInputStream", True, "Blocked package"),
    ])
    @patch('verifier.java_bytecode_scanner.ClassFile')
    def test_scan_class_file_security(self, mock_classfile, scanner, mock_report, class_name, is_blocked, violation_msg):
        """Test security scanning with blocked and safe classes"""
        mock_cf = Mock()
        mock_const = Mock()
        mock_const.name.value = class_name
        
        from jawa.constants import ConstantClass
        mock_const.__class__ = ConstantClass
        mock_cf.constants = [mock_const]
        mock_classfile.return_value = mock_cf
        
        result = scanner.scan_class_file(b"dummy bytes", mock_report, "test_model")
        
        assert result is (not is_blocked)
        assert mock_report.checks["securityScan"]["passed"] is (not is_blocked)
        if is_blocked:
            assert violation_msg in mock_report.checks["securityScan"]["error"]

    @patch('verifier.java_bytecode_scanner.ClassFile')
    def test_scan_class_file_blocked_method(self, mock_classfile, scanner, mock_report):
        """Test detection of blocked method calls"""
        mock_cf = Mock()
        mock_method_ref = Mock()
        mock_class = Mock()
        mock_class.name.value = "java/lang/Runtime"
        mock_method_ref.class_ = mock_class
        
        mock_name_type = Mock()
        mock_name_type.name.value = "exec"
        mock_method_ref.name_and_type = mock_name_type
        
        from jawa.constants import MethodReference
        mock_method_ref.__class__ = MethodReference
        mock_cf.constants = [mock_method_ref]
        mock_classfile.return_value = mock_cf
        
        result = scanner.scan_class_file(b"dummy bytes", mock_report, "test_model")
        assert result is False
        assert "Blocked method" in mock_report.checks["securityScan"]["error"]

    @patch('verifier.java_bytecode_scanner.ClassFile')
    def test_scan_class_file_parse_error(self, mock_classfile, scanner, mock_report):
        """Test security scan handles parse errors"""
        mock_classfile.side_effect = Exception("Cannot parse")
        result = scanner.scan_class_file(b"dummy bytes", mock_report, "test_model")
        assert result is False
        assert mock_report.checks["bytecodeParsing"]["passed"] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
