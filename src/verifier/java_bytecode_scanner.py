"""
Java Bytecode Scanner - Scans Java bytecode for security violations
Uses jawa library to analyze compiled Java .class files
"""

from typing import List, Dict, Any
from jawa.cf import ClassFile
from jawa.constants import ConstantClass, MethodReference, FieldReference
from .report_generator import ReportGenerator
import io


class JavaBytecodeScanner:
    """Scans Java bytecode for security violations"""

    def __init__(self, allowed_packages: List[str], blocked_packages: List[str],
                 blocked_classes: List[str], blocked_methods: List[str]):
        self.allowed_packages = set(allowed_packages)
        self.blocked_packages = set(blocked_packages)
        self.blocked_classes = set(blocked_classes)
        self.blocked_methods = set(blocked_methods)

    def scan_class_file(self, class_bytes: bytes, report: ReportGenerator,
                       class_name: str = "model") -> bool:
        """
        Scan a Java .class file for security violations

        Returns:
            True if bytecode is safe, False if violations found
        """
        try:
            cf = ClassFile(io.BytesIO(class_bytes))
        except Exception as e:
            report.add_check_failed("bytecodeParsing", f"Cannot parse class: {str(e)}")
            return False

        # Run all security checks
        violations = []

        # Check class references
        class_violations = self._check_class_references(cf)
        violations.extend(class_violations)

        # Check method calls
        method_violations = self._check_method_calls(cf)
        violations.extend(method_violations)

        if violations:
            # Format all violations into error message
            error_msg = "; ".join(violations[:5])  # Limit to first 5
            if len(violations) > 5:
                error_msg += f" (+{len(violations) - 5} more)"
            report.add_check_failed("securityScan", error_msg)
            return False

        report.add_check_passed("securityScan")
        return True

    def _check_class_references(self, cf: ClassFile) -> List[str]:
        """Check for references to dangerous classes"""
        violations = []

        for const in cf.constants:
            if isinstance(const, ConstantClass):
                class_name = const.name.value

                # Check if class is explicitly blocked
                if class_name in self.blocked_classes:
                    violations.append(f"Blocked class: {class_name}")
                    continue

                # Check if class is in a blocked package
                for blocked_pkg in self.blocked_packages:
                    if class_name.startswith(blocked_pkg):
                        violations.append(f"Blocked package: {class_name}")
                        break

        return violations

    def _check_method_calls(self, cf: ClassFile) -> List[str]:
        """Check for dangerous method invocations"""
        violations = []

        for const in cf.constants:
            if isinstance(const, MethodReference):
                class_name = const.class_.name.value
                method_name = const.name_and_type.name.value
                full_method = f"{class_name}.{method_name}"

                if full_method in self.blocked_methods:
                    violations.append(f"Blocked method: {full_method}")

        return violations

    def check_implements_interface(self, class_bytes: bytes,
                                   required_interface: str,
                                   report: ReportGenerator) -> bool:
        """Check if class implements a required interface"""
        try:
            cf = ClassFile(io.BytesIO(class_bytes))
        except Exception as e:
            report.add_check_failed("implementsInterface", f"Cannot parse class: {str(e)}")
            return False

        # Check interfaces
        implements = []
        for interface in cf.interfaces:
            interface_name = interface.name.value
            implements.append(interface_name)

            if interface_name == required_interface:
                report.add_check_passed("implementsInterface")
                return True

        # Not found
        found_str = ", ".join(implements) if implements else "none"
        report.add_check_failed(
            "implementsInterface",
            f"Does not implement Model interface. Found: [{found_str}]"
        )
        return False

    def check_has_method(self, class_bytes: bytes, method_name: str,
                        method_signature: str, report: ReportGenerator) -> bool:
        """Check if class has a required method with specific signature"""
        try:
            cf = ClassFile(io.BytesIO(class_bytes))
        except Exception as e:
            report.add_check_failed("hasSimulateStep", f"Cannot parse class: {str(e)}")
            return False

        # Check methods
        for method in cf.methods:
            if method.name.value == method_name:
                actual_sig = method.descriptor.value

                if actual_sig == method_signature:
                    report.add_check_passed("hasSimulateStep")
                    return True
                else:
                    report.add_check_failed(
                        "hasSimulateStep",
                        f"Wrong signature. Expected: {method_signature}, Found: {actual_sig}"
                    )
                    return False

        # Method not found
        report.add_check_failed("hasSimulateStep", f"Missing required method: {method_name}")
        return False

    def get_class_info(self, class_bytes: bytes) -> Dict[str, Any]:
        """Extract information about a class file"""
        try:
            cf = ClassFile(io.BytesIO(class_bytes))

            return {
                'class_name': cf.this.name.value,
                'interfaces': [iface.name.value for iface in cf.interfaces],
                'methods': [
                    {'name': m.name.value, 'signature': m.descriptor.value}
                    for m in cf.methods
                ],
                'version': f"{cf.version[0]}.{cf.version[1]}"
            }
        except Exception as e:
            return {'error': str(e)}
