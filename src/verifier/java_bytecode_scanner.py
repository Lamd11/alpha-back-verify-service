"""
Java Bytecode Scanner - FR2: Scan Java bytecode for malicious operations
Uses jawa library to analyze compiled Java .class files for security violations
"""

from typing import List, Dict, Set
from jawa.cf import ClassFile
from jawa.constants import ConstantClass, MethodReference, FieldReference
from .report_generator import ReportGenerator
import io


class JavaBytecodeScanner:
    """Scans Java bytecode for security violations"""

    def __init__(self, allowed_packages: List[str], blocked_packages: List[str],
                 blocked_classes: List[str], blocked_methods: List[str]):
        """
        Initialize bytecode scanner

        Args:
            allowed_packages: List of allowed package prefixes (e.g., "java/util")
            blocked_packages: List of explicitly blocked packages
            blocked_classes: List of blocked class references
            blocked_methods: List of blocked method calls
        """
        self.allowed_packages = set(allowed_packages)
        self.blocked_packages = set(blocked_packages)
        self.blocked_classes = set(blocked_classes)
        self.blocked_methods = set(blocked_methods)

    def scan_class_file(self, class_bytes: bytes, report: ReportGenerator,
                       class_name: str = "model") -> bool:
        """
        Scan a Java .class file for security violations

        Args:
            class_bytes: Raw bytes of the .class file
            report: Report generator to record results
            class_name: Name of the class being scanned (for logging)

        Returns:
            True if bytecode is safe, False if violations found
        """
        try:
            # Parse the class file
            cf = ClassFile(io.BytesIO(class_bytes))
        except Exception as e:
            report.add_error(
                "INVALID_CLASS_FILE",
                f"Cannot parse {class_name}.class: {str(e)}",
                "CRITICAL"
            )
            return False

        # Run all security checks
        violations_found = False

        if not self._check_class_references(cf, report):
            violations_found = True

        if not self._check_method_calls(cf, report):
            violations_found = True

        if not self._check_field_access(cf, report):
            violations_found = True

        if not violations_found:
            report.add_check_passed("bytecode_safety_scan")

        return not violations_found

    def _check_class_references(self, cf: ClassFile, report: ReportGenerator) -> bool:
        """Check for references to dangerous classes"""
        violations = []

        # Iterate through constant pool for class references
        for const in cf.constants:
            if isinstance(const, ConstantClass):
                class_name = const.name.value

                # Check if class is explicitly blocked
                if class_name in self.blocked_classes:
                    violations.append({
                        'class': class_name,
                        'type': 'blocked_class'
                    })
                    continue

                # Check if class is in a blocked package
                for blocked_pkg in self.blocked_packages:
                    if class_name.startswith(blocked_pkg):
                        violations.append({
                            'class': class_name,
                            'type': 'blocked_package'
                        })
                        break

        # Report all violations
        for violation in violations:
            if violation['type'] == 'blocked_class':
                report.add_error(
                    "DISALLOWED_CLASS_REFERENCE",
                    f"Reference to blocked class '{violation['class']}' found",
                    "CRITICAL"
                )
            else:
                report.add_error(
                    "DISALLOWED_PACKAGE_REFERENCE",
                    f"Reference to blocked package class '{violation['class']}' found",
                    "CRITICAL"
                )

        return len(violations) == 0

    def _check_method_calls(self, cf: ClassFile, report: ReportGenerator) -> bool:
        """Check for dangerous method invocations"""
        violations = []

        # Iterate through constant pool for method references
        for const in cf.constants:
            if isinstance(const, MethodReference):
                class_name = const.class_.name.value
                method_name = const.name_and_type.name.value
                method_sig = const.name_and_type.descriptor.value

                full_method = f"{class_name}.{method_name}"

                # Check if method is explicitly blocked
                if full_method in self.blocked_methods:
                    violations.append({
                        'method': full_method,
                        'signature': method_sig
                    })

        # Report all violations
        for violation in violations:
            report.add_error(
                "DISALLOWED_METHOD_CALL",
                f"Call to blocked method '{violation['method']}' found",
                "CRITICAL"
            )

        return len(violations) == 0

    def _check_field_access(self, cf: ClassFile, report: ReportGenerator) -> bool:
        """Check for access to dangerous fields"""
        violations = []

        # Check for suspicious field references
        suspicious_fields = [
            "java/lang/System.out",
            "java/lang/System.err",
            "java/lang/System.in"
        ]

        for const in cf.constants:
            if isinstance(const, FieldReference):
                class_name = const.class_.name.value
                field_name = const.name_and_type.name.value
                full_field = f"{class_name}.{field_name}"

                if full_field in suspicious_fields:
                    report.add_warning(
                        "SUSPICIOUS_FIELD_ACCESS",
                        f"Access to field '{full_field}' detected (may be for logging)"
                    )

        return True  # Warnings don't fail validation

    def check_implements_interface(self, class_bytes: bytes,
                                   required_interface: str,
                                   report: ReportGenerator) -> bool:
        """
        Check if class implements a required interface

        Args:
            class_bytes: Raw bytes of the .class file
            required_interface: Interface name (e.g., "com/ttsudio/alphaback/Model")
            report: Report generator

        Returns:
            True if interface is implemented
        """
        try:
            cf = ClassFile(io.BytesIO(class_bytes))
        except Exception as e:
            report.add_error(
                "INVALID_CLASS_FILE",
                f"Cannot parse class file: {str(e)}",
                "CRITICAL"
            )
            return False

        # Check interfaces
        implements = []
        for interface in cf.interfaces:
            interface_name = interface.name.value
            implements.append(interface_name)

            if interface_name == required_interface:
                report.add_check_passed("interface_implementation")
                return True

        # Not found
        report.add_error(
            "MISSING_REQUIRED_INTERFACE",
            f"Class does not implement required interface '{required_interface}'. "
            f"Found interfaces: {implements if implements else 'none'}",
            "CRITICAL"
        )
        return False

    def check_has_method(self, class_bytes: bytes, method_name: str,
                        method_signature: str, report: ReportGenerator) -> bool:
        """
        Check if class has a required method with specific signature

        Args:
            class_bytes: Raw bytes of the .class file
            method_name: Name of required method (e.g., "simulateStep")
            method_signature: Method descriptor (e.g., "(Lcom/ttsudio/alphaback/State;)Ljava/util/List;")
            report: Report generator

        Returns:
            True if method exists with correct signature
        """
        try:
            cf = ClassFile(io.BytesIO(class_bytes))
        except Exception as e:
            return False

        # Check methods
        for method in cf.methods:
            if method.name.value == method_name:
                actual_sig = method.descriptor.value

                if actual_sig == method_signature:
                    report.add_check_passed("method_signature_validation")
                    return True
                else:
                    report.add_error(
                        "INVALID_METHOD_SIGNATURE",
                        f"Method '{method_name}' has wrong signature. "
                        f"Expected: {method_signature}, Found: {actual_sig}",
                        "CRITICAL"
                    )
                    return False

        # Method not found
        report.add_error(
            "MISSING_REQUIRED_METHOD",
            f"Class does not have required method '{method_name}'",
            "CRITICAL"
        )
        return False

    def get_class_info(self, class_bytes: bytes) -> Dict[str, any]:
        """
        Extract information about a class file

        Args:
            class_bytes: Raw bytes of the .class file

        Returns:
            Dictionary with class information
        """
        try:
            cf = ClassFile(io.BytesIO(class_bytes))

            # Get class name
            class_name = cf.this.name.value

            # Get interfaces
            interfaces = [iface.name.value for iface in cf.interfaces]

            # Get methods
            methods = []
            for method in cf.methods:
                methods.append({
                    'name': method.name.value,
                    'signature': method.descriptor.value,
                    'access_flags': method.access_flags.value
                })

            return {
                'class_name': class_name,
                'interfaces': interfaces,
                'methods': methods,
                'version': f"{cf.version[0]}.{cf.version[1]}"
            }
        except Exception as e:
            return {
                'error': f"Failed to parse class: {str(e)}"
            }
