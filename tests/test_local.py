#!/usr/bin/env python3
"""
Local Test Script for AlphaBack Verify Service
Tests the verification logic without requiring AWS

Usage:
    python tests/test_local.py                    # Run all tests
    python tests/test_local.py path/to/file.class # Test specific .class file
"""

import sys
import os
import json

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from verifier.java_bytecode_scanner import JavaBytecodeScanner
from verifier.report_generator import ReportGenerator


def load_config():
    """Load verification configuration"""
    config_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'config')

    with open(os.path.join(config_dir, 'allowed_imports.json'), 'r') as f:
        security_config = json.load(f)

    with open(os.path.join(config_dir, 'validation_rules.json'), 'r') as f:
        validation_config = json.load(f)

    return security_config, validation_config


def verify_class_file(class_file_path: str) -> dict:
    """
    Verify a single .class file and return the report

    Args:
        class_file_path: Path to the .class file

    Returns:
        Verification report dictionary
    """
    security_config, validation_config = load_config()

    report = ReportGenerator()
    report.start_timing()

    # Extract model_id from filename
    filename = os.path.basename(class_file_path)
    model_id = filename.replace('.class', '')

    # CHECK 1: File exists and readable
    if not os.path.exists(class_file_path):
        report.add_check_failed("fileExists", f"File not found: {class_file_path}")
        report.end_timing()
        return report.generate_report(model_id)

    # CHECK 2: File size
    file_size = os.path.getsize(class_file_path)
    max_size = validation_config.get('max_file_size_bytes', 10485760)

    if file_size > max_size:
        report.add_check_failed("fileSize", f"File too large: {file_size} bytes (max: {max_size})")
        report.end_timing()
        return report.generate_report(model_id)

    report.add_check_passed("fileSize")

    # Read the class file
    with open(class_file_path, 'rb') as f:
        class_bytes = f.read()

    report.add_check_passed("s3FileReadable")  # Using same check name for consistency

    # Initialize scanner
    scanner = JavaBytecodeScanner(
        allowed_packages=security_config['allowed_packages'],
        blocked_packages=security_config['blocked_packages'],
        blocked_classes=security_config['blocked_classes'],
        blocked_methods=security_config['blocked_methods']
    )

    # CHECK 3: Valid class file
    class_info = scanner.get_class_info(class_bytes)

    if 'error' in class_info:
        report.add_check_failed("classFileValid", f"Invalid .class file: {class_info['error']}")
        report.end_timing()
        return report.generate_report(model_id)

    report.add_check_passed("classFileValid")
    print(f"  Class: {class_info['class_name']}")
    print(f"  Interfaces: {class_info['interfaces']}")
    print(f"  Methods: {[m['name'] for m in class_info['methods']]}")

    # CHECK 4: Implements Model interface
    required_interface = validation_config['required_interface']
    if not scanner.check_implements_interface(class_bytes, required_interface, report):
        report.end_timing()
        return report.generate_report(model_id)

    # CHECK 5: Has simulateStep method
    required_method = validation_config['required_method_name']
    required_signature = validation_config['required_method_signature']
    if not scanner.check_has_method(class_bytes, required_method, required_signature, report):
        report.end_timing()
        return report.generate_report(model_id)

    # CHECK 6: Security scan
    if not scanner.scan_class_file(class_bytes, report, model_id):
        report.end_timing()
        return report.generate_report(model_id)

    report.end_timing()
    return report.generate_report(model_id)


def print_report(report: dict):
    """Pretty print a verification report"""
    print("\n" + "=" * 60)
    print(f"MODEL: {report['modelId']}")
    print(f"VERIFIED: {'✓ YES' if report['verified'] else '✗ NO'}")
    print("=" * 60)

    print("\nChecks:")
    for check_name, check_result in report['checks'].items():
        status = "✓" if check_result['passed'] else "✗"
        print(f"  {status} {check_name}")
        if 'error' in check_result:
            print(f"      Error: {check_result['error']}")

    if report['overallErrors']:
        print("\nErrors:")
        for error in report['overallErrors']:
            print(f"  - {error}")

    print(f"\nExecution time: {report['executionTimeMs']}ms")
    print(f"Timestamp: {report['timestamp']}")
    print()


def run_demo():
    """Run demo with sample .class files if they exist"""
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'java_models')

    # Look for compiled .class files
    class_files = []
    for root, dirs, files in os.walk(fixtures_dir):
        for f in files:
            if f.endswith('.class'):
                class_files.append(os.path.join(root, f))

    if not class_files:
        print("No .class files found in tests/fixtures/java_models/")
        print("\nTo test, you need to compile the Java files first:")
        print("  1. Clone Justin's repo: https://github.com/JustinTsangg/alphaback-model")
        print("  2. Compile a model: javac -cp alphaback-model/src YourModel.java")
        print("  3. Run: python tests/test_local.py YourModel.class")
        return

    print(f"Found {len(class_files)} .class file(s)")

    for class_file in class_files:
        print(f"\nVerifying: {class_file}")
        report = verify_class_file(class_file)
        print_report(report)

        # Also save JSON report
        output_path = class_file.replace('.class', '_report.json')
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {output_path}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Test specific file
        class_file = sys.argv[1]
        print(f"Verifying: {class_file}")
        report = verify_class_file(class_file)
        print_report(report)

        # Print raw JSON
        print("\nRaw JSON Report:")
        print(json.dumps(report, indent=2))
    else:
        # Run demo
        print("AlphaBack Verify Service - Local Test")
        print("=" * 40)
        run_demo()
