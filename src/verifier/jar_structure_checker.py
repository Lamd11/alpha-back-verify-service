"""
JAR Structure Checker - FR1: Validate Java model package structure
Ensures uploaded JAR files contain required .class files and proper organization
"""

import zipfile
from typing import Dict, List, Optional
from io import BytesIO
from .report_generator import ReportGenerator


class JarStructureChecker:
    """Validates Java JAR/class file structure"""

    def __init__(self, required_files: List[str], max_size_bytes: int):
        """
        Initialize structure checker

        Args:
            required_files: List of required file names (e.g., ["metadata.json"])
            max_size_bytes: Maximum allowed file size
        """
        self.required_files = required_files
        self.max_size_bytes = max_size_bytes

    def extract_jar(self, file_content: bytes, filename: str) -> Optional[Dict[str, bytes]]:
        """
        Extract JAR file (which is just a ZIP archive)

        Args:
            file_content: Raw file bytes
            filename: Original filename

        Returns:
            Dictionary mapping filenames to content, or None if extraction fails
        """
        extracted_files = {}

        try:
            # JAR files are ZIP files
            with zipfile.ZipFile(BytesIO(file_content)) as jar:
                for file_info in jar.filelist:
                    if not file_info.is_dir():
                        # Get full path (keep directory structure)
                        file_path = file_info.filename
                        extracted_files[file_path] = jar.read(file_info)

            return extracted_files

        except zipfile.BadZipFile as e:
            return None
        except Exception as e:
            return None

    def validate_structure(self, extracted_files: Dict[str, bytes],
                          report: ReportGenerator) -> bool:
        """
        Validate JAR package structure

        Args:
            extracted_files: Dictionary of filename -> content
            report: Report generator to record results

        Returns:
            True if structure is valid, False otherwise
        """
        # Check for required files (like metadata.json)
        present_files = set(extracted_files.keys())
        required_set = set(self.required_files)

        # For required files, just check base name (not full path)
        missing_files = []
        for required in required_set:
            found = any(f.endswith(required) for f in present_files)
            if not found:
                missing_files.append(required)

        if missing_files:
            report.add_error(
                "MISSING_REQUIRED_FILES",
                f"JAR package missing required files: {', '.join(missing_files)}",
                "CRITICAL"
            )
            return False

        # Check that we have at least one .class file
        class_files = [f for f in present_files if f.endswith('.class')]

        if not class_files:
            report.add_error(
                "NO_CLASS_FILES",
                "JAR package contains no .class files",
                "CRITICAL"
            )
            return False

        report.add_check_passed("jar_structure_validation")
        return True

    def find_model_class(self, extracted_files: Dict[str, bytes],
                         model_class_name: str) -> Optional[bytes]:
        """
        Find the main model class file

        Args:
            extracted_files: Dictionary of filename -> content
            model_class_name: Fully qualified class name (e.g., "com.example.MyModel")

        Returns:
            Bytes of the .class file, or None if not found
        """
        # Convert class name to path
        # com.example.MyModel -> com/example/MyModel.class
        class_path = model_class_name.replace('.', '/') + '.class'

        # Look for the class file
        for file_path, content in extracted_files.items():
            if file_path.endswith(class_path):
                return content

        return None

    def find_all_class_files(self, extracted_files: Dict[str, bytes]) -> Dict[str, bytes]:
        """
        Find all .class files in the JAR

        Args:
            extracted_files: Dictionary of filename -> content

        Returns:
            Dictionary of class file path -> bytes
        """
        class_files = {}

        for file_path, content in extracted_files.items():
            if file_path.endswith('.class'):
                class_files[file_path] = content

        return class_files

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
                f"JAR file size ({actual_mb:.2f}MB) exceeds maximum allowed ({max_mb:.2f}MB)",
                "CRITICAL"
            )
            return False

        report.add_check_passed("file_size_validation")
        return True

    def get_metadata_file(self, extracted_files: Dict[str, bytes]) -> Optional[bytes]:
        """
        Extract metadata.json file from JAR

        Args:
            extracted_files: Dictionary of filename -> content

        Returns:
            Bytes of metadata.json, or None if not found
        """
        # Look for metadata.json at any level
        for file_path, content in extracted_files.items():
            if file_path.endswith('metadata.json'):
                return content

        return None

    def list_jar_contents(self, extracted_files: Dict[str, bytes]) -> Dict[str, any]:
        """
        Get summary of JAR contents

        Args:
            extracted_files: Dictionary of filename -> content

        Returns:
            Dictionary with JAR statistics
        """
        class_files = [f for f in extracted_files.keys() if f.endswith('.class')]
        json_files = [f for f in extracted_files.keys() if f.endswith('.json')]
        other_files = [f for f in extracted_files.keys()
                      if not f.endswith('.class') and not f.endswith('.json')]

        return {
            'total_files': len(extracted_files),
            'class_files': len(class_files),
            'json_files': len(json_files),
            'other_files': len(other_files),
            'class_file_list': class_files,
            'json_file_list': json_files
        }
