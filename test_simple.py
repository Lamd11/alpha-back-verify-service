#!/usr/bin/env python3
"""
Simple local testing script - tests validation logic without AWS dependencies
Tests the verifier modules directly with test fixtures
"""

import os
import sys
import json
import tarfile
from io import BytesIO

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from verifier.structure_checker import StructureChecker
from verifier.metadata_validator import MetadataValidator
from verifier.code_scanner import CodeScanner
from verifier.report_generator import ReportGenerator

# Load config
def load_config():
    config_dir = os.path.join(os.path.dirname(__file__), 'src', 'config')
    with open(os.path.join(config_dir, 'allowed_imports.json'), 'r') as f:
        import_config = json.load(f)
    with open(os.path.join(config_dir, 'validation_rules.json'), 'r') as f:
        validation_config = json.load(f)
    return import_config, validation_config


def test_model(model_path: str, expected_status: str):
    """Test a model file"""
    print(f"\n{'='*60}")
    print(f"Testing: {os.path.basename(model_path)}")
    print(f"Expected Status: {expected_status}")
    print(f"{'='*60}")
    
    if not os.path.exists(model_path):
        print(f"❌ ERROR: File not found: {model_path}")
        return False
    
    # Load config
    import_config, validation_config = load_config()
    
    # Initialize components
    report = ReportGenerator()
    report.start_timing()
    
    structure_checker = StructureChecker(
        required_files=validation_config['required_files'],
        max_size_bytes=validation_config['max_file_size_bytes'],
        required_class=validation_config['required_class_name'],
        required_method=validation_config['required_method_name']
    )
    
    metadata_validator = MetadataValidator(
        required_fields=validation_config['required_metadata_fields']
    )
    
    code_scanner = CodeScanner(
        allowed_imports=import_config['allowed_imports'],
        blocked_imports=import_config['blocked_imports'],
        blocked_builtins=import_config['blocked_builtins']
    )
    
    # Read model file
    with open(model_path, 'rb') as f:
        model_content = f.read()
    
    file_size = len(model_content)
    filename = os.path.basename(model_path)
    
    # Step 1: Check file size
    print("\n1. Checking file size...")
    if not structure_checker.check_file_size(file_size, report):
        print("   ❌ File size check failed")
    else:
        print("   ✓ File size OK")
    
    # Step 2: Extract archive
    print("\n2. Extracting archive...")
    extracted_files = structure_checker.extract_archive(model_content, filename)
    if extracted_files is None:
        print("   ❌ Failed to extract archive")
        report.add_error("INVALID_ARCHIVE", "Unable to extract archive", "CRITICAL")
    else:
        print(f"   ✓ Extracted {len(extracted_files)} files: {list(extracted_files.keys())}")
    
    if extracted_files is None:
        report.end_timing()
        final_report = report.generate_report("test_model")
        print(f"\n❌ Validation failed: {final_report['status']}")
        return final_report['status'] == expected_status
    
    # Step 3: Validate structure
    print("\n3. Validating structure...")
    if not structure_checker.validate_structure(extracted_files, report):
        print("   ❌ Structure validation failed")
    else:
        print("   ✓ Structure OK")
    
    # Step 4: Validate metadata
    print("\n4. Validating metadata...")
    if 'metadata.json' in extracted_files:
        metadata_content = extracted_files['metadata.json'].decode('utf-8')
        if not metadata_validator.validate(metadata_content, report):
            print("   ❌ Metadata validation failed")
        else:
            print("   ✓ Metadata OK")
        model_id = metadata_validator.extract_model_id(metadata_content) or "unknown"
    else:
        model_id = "unknown"
        print("   ❌ metadata.json not found")
    
    # Step 5: Validate class structure
    print("\n5. Validating class structure...")
    if 'model.py' in extracted_files:
        model_code = extracted_files['model.py'].decode('utf-8')
        if not structure_checker.validate_model_class(model_code, report):
            print("   ❌ Class structure validation failed")
        else:
            print("   ✓ Class structure OK")
    else:
        model_code = None
        print("   ❌ model.py not found")
    
    # Step 6: Scan code
    print("\n6. Scanning code for security issues...")
    if model_code:
        if not code_scanner.scan(model_code, report):
            print("   ❌ Code scan found violations")
        else:
            print("   ✓ Code scan passed")
    else:
        print("   ⚠️  Skipped (no model.py)")
    
    # Generate final report
    report.end_timing()
    final_report = report.generate_report(model_id)
    
    # Print results
    print(f"\n{'='*60}")
    print("VALIDATION RESULTS")
    print(f"{'='*60}")
    print(f"Model ID: {final_report['model_id']}")
    print(f"Status: {final_report['status']}")
    print(f"Execution Time: {final_report['execution_time_ms']}ms")
    
    if final_report.get('checks_passed'):
        print(f"\n✓ Checks Passed ({len(final_report['checks_passed'])}):")
        for check in final_report['checks_passed']:
            print(f"  • {check}")
    
    if final_report.get('errors'):
        print(f"\n✗ Errors Found ({len(final_report['errors'])}):")
        for error in final_report['errors']:
            print(f"  • [{error['severity']}] {error['code']}: {error['message']}")
    
    if final_report.get('warnings'):
        print(f"\n⚠️  Warnings ({len(final_report['warnings'])}):")
        for warning in final_report['warnings']:
            print(f"  • {warning['code']}: {warning['message']}")
    
    # Check if result matches expectation
    actual_status = final_report['status']
    matches = actual_status == expected_status
    
    if matches:
        print(f"\n✅ Test PASSED: Model correctly identified as {actual_status}")
    else:
        print(f"\n❌ Test FAILED: Expected {expected_status}, got {actual_status}")
    
    return matches


if __name__ == '__main__':
    print("AlphaBack Verify Service - Simple Local Testing")
    print("="*60)
    print("This script tests the validation logic directly")
    print("without requiring AWS services or mocks")
    print("="*60)
    
    # Test valid model
    valid_model_path = 'tests/fixtures/valid_model.tar.gz'
    valid_result = test_model(valid_model_path, 'VALID')
    
    # Test invalid model
    invalid_model_path = 'tests/fixtures/invalid_model.tar.gz'
    invalid_result = test_model(invalid_model_path, 'INVALID')
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Valid Model Test:   {'✅ PASSED' if valid_result else '❌ FAILED'}")
    print(f"Invalid Model Test: {'✅ PASSED' if invalid_result else '❌ FAILED'}")
    
    if valid_result and invalid_result:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed")
        sys.exit(1)

