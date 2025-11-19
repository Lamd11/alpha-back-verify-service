"""
Structure Checker - FR1: Validate model package structure
Ensures uploaded models contain required files and proper organization
"""

import tarfile
import zipfile
import ast
from typing import List, Dict, Set, Optional
from io import BytesIO
from .report_generator import ReportGenerator


class StructureChecker:
    """Validates model package structure and Python code structure"""

    def __init__(self, required_files: List[str], max_size_bytes: int,
                 required_class: str, required_method: str):
        """
        Initialize structure checker

        Args:
            required_files: List of required file names
            max_size_bytes: Maximum allowed file size
            required_class: Required class name in model.py
            required_method: Required method name in class
        """
        self.required_files = required_files
        self.max_size_bytes = max_size_bytes
        self.required_class = required_class
        self.required_method = required_method

    def extract_archive(self, file_content: bytes, filename: str) -> Optional[Dict[str, bytes]]:
        """
        Extract tar.gz or zip archive

        Args:
            file_content: Raw file bytes
            filename: Original filename

        Returns:
            Dictionary mapping filenames to content, or None if extraction fails
        """
        extracted_files = {}

        try:
            # Try tar.gz first
            if filename.endswith('.tar.gz') or filename.endswith('.tgz'):
                with tarfile.open(fileobj=BytesIO(file_content), mode='r:gz') as tar:
                    for member in tar.getmembers():
                        if member.isfile():
                            # Get just the filename without directory path
                            file_name = member.name.split('/')[-1]
                            extracted_files[file_name] = tar.extractfile(member).read()

            # Try zip
            elif filename.endswith('.zip'):
                with zipfile.ZipFile(BytesIO(file_content)) as zf:
                    for file_info in zf.filelist:
                        if not file_info.is_dir():
                            file_name = file_info.filename.split('/')[-1]
                            extracted_files[file_name] = zf.read(file_info)

            else:
                return None

            return extracted_files

        except (tarfile.TarError, zipfile.BadZipFile) as e:
            return None

    def validate_structure(self, extracted_files: Dict[str, bytes],
                          report: ReportGenerator) -> bool:
        """
        Validate model package structure

        Args:
            extracted_files: Dictionary of filename -> content
            report: Report generator to record results

        Returns:
            True if structure is valid, False otherwise
        """
        # Check for required files
        present_files = set(extracted_files.keys())
        required_set = set(self.required_files)
        missing_files = required_set - present_files

        if missing_files:
            report.add_error(
                "MISSING_REQUIRED_FILES",
                f"Model package missing required files: {', '.join(missing_files)}",
                "CRITICAL"
            )
            return False

        report.add_check_passed("structure_validation")
        return True

    def validate_model_class(self, model_code: str, report: ReportGenerator) -> bool:
        """
        Validate model.py has required class and method structure

        Args:
            model_code: Content of model.py
            report: Report generator to record results

        Returns:
            True if valid, False otherwise
        """
        try:
            # Parse the Python code into AST
            tree = ast.parse(model_code)
        except SyntaxError as e:
            report.add_error(
                "SYNTAX_ERROR",
                f"model.py has syntax error at line {e.lineno}: {e.msg}",
                "CRITICAL"
            )
            return False

        # Find the required class
        class_found = False
        method_found = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name == self.required_class:
                    class_found = True

                    # Check for required method
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            if item.name == self.required_method:
                                method_found = True
                                # Validate method signature
                                if not self._validate_predict_signature(item, report):
                                    return False
                                break

        if not class_found:
            report.add_error(
                "MISSING_REQUIRED_CLASS",
                f"model.py must contain a class named '{self.required_class}'",
                "CRITICAL"
            )
            return False

        if not method_found:
            report.add_error(
                "MISSING_REQUIRED_METHOD",
                f"Class '{self.required_class}' must have a method named '{self.required_method}'",
                "CRITICAL"
            )
            return False

        report.add_check_passed("class_structure_validation")
        return True

    def _validate_predict_signature(self, func_node: ast.FunctionDef,
                                    report: ReportGenerator) -> bool:
        """
        Validate predict method has correct signature

        Args:
            func_node: AST node for the predict method
            report: Report generator

        Returns:
            True if signature is valid
        """
        # Expected: def predict(self, stock_prices, volume, timestamps)
        args = func_node.args
        arg_names = [arg.arg for arg in args.args]

        # Should have at least 4 args: self, stock_prices, volume, timestamps
        expected_args = ['self', 'stock_prices', 'volume', 'timestamps']

        if len(arg_names) < len(expected_args):
            report.add_error(
                "INVALID_METHOD_SIGNATURE",
                f"predict() method must accept parameters: {', '.join(expected_args)}",
                "CRITICAL"
            )
            return False

        # Check that the first 4 args match expected
        for i, expected in enumerate(expected_args):
            if i >= len(arg_names) or arg_names[i] != expected:
                report.add_warning(
                    "METHOD_SIGNATURE_MISMATCH",
                    f"predict() parameter mismatch. Expected '{expected}' but found '{arg_names[i] if i < len(arg_names) else 'missing'}'"
                )

        return True

    def check_file_size(self, file_size: int, report: ReportGenerator) -> bool:
        """
        Check if file size is within limits

        Args:
            file_size: Size in bytes
            report: Report generator

        Returns:
            True if within limits
        """
        if file_size > self.max_size_bytes:
            max_mb = self.max_size_bytes / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            report.add_error(
                "FILE_TOO_LARGE",
                f"Model file size ({actual_mb:.2f}MB) exceeds maximum allowed ({max_mb:.2f}MB)",
                "CRITICAL"
            )
            return False

        report.add_check_passed("file_size_validation")
        return True
