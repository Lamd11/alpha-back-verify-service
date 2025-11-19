"""
Code Scanner - FR2: Scan model code for malicious commands
Uses Python AST to detect unsafe imports, function calls, and code patterns
"""

import ast
from typing import List, Set, Dict, Any
from .report_generator import ReportGenerator


class CodeScanner:
    """Scans Python code for security violations using AST analysis"""

    def __init__(self, allowed_imports: List[str], blocked_imports: List[str],
                 blocked_builtins: List[str]):
        """
        Initialize code scanner

        Args:
            allowed_imports: List of allowed import module names
            blocked_imports: List of explicitly blocked module names
            blocked_builtins: List of blocked builtin functions
        """
        self.allowed_imports = set(allowed_imports)
        self.blocked_imports = set(blocked_imports)
        self.blocked_builtins = set(blocked_builtins)

    def scan(self, code: str, report: ReportGenerator) -> bool:
        """
        Scan code for security violations

        Args:
            code: Python source code to scan
            report: Report generator to record results

        Returns:
            True if code is safe, False if violations found
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            report.add_error(
                "SYNTAX_ERROR",
                f"Code has syntax error at line {e.lineno}: {e.msg}",
                "CRITICAL"
            )
            return False

        # Run all security checks
        violations_found = False

        if not self._check_imports(tree, report):
            violations_found = True

        if not self._check_builtin_calls(tree, report):
            violations_found = True

        if not self._check_file_operations(tree, report):
            violations_found = True

        if not self._check_network_operations(tree, report):
            violations_found = True

        if not self._check_dangerous_patterns(tree, report):
            violations_found = True

        if not violations_found:
            report.add_check_passed("code_safety_scan")

        return not violations_found

    def _check_imports(self, tree: ast.AST, report: ReportGenerator) -> bool:
        """Check for disallowed imports"""
        violations = []

        for node in ast.walk(tree):
            # Check regular imports: import os
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]  # Get base module
                    if module_name in self.blocked_imports:
                        violations.append({
                            'line': node.lineno,
                            'module': module_name,
                            'type': 'import'
                        })
                    elif module_name not in self.allowed_imports:
                        violations.append({
                            'line': node.lineno,
                            'module': module_name,
                            'type': 'import_not_whitelisted'
                        })

            # Check from imports: from os import path
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    if module_name in self.blocked_imports:
                        violations.append({
                            'line': node.lineno,
                            'module': module_name,
                            'type': 'from_import'
                        })
                    elif module_name not in self.allowed_imports:
                        violations.append({
                            'line': node.lineno,
                            'module': module_name,
                            'type': 'import_not_whitelisted'
                        })

        # Report all violations
        for violation in violations:
            if violation['type'] in ['import', 'from_import']:
                report.add_error(
                    "DISALLOWED_IMPORT",
                    f"Disallowed import '{violation['module']}' found at line {violation['line']}",
                    "CRITICAL"
                )
            else:
                report.add_error(
                    "IMPORT_NOT_WHITELISTED",
                    f"Import '{violation['module']}' at line {violation['line']} is not in the allowed list",
                    "CRITICAL"
                )

        return len(violations) == 0

    def _check_builtin_calls(self, tree: ast.AST, report: ReportGenerator) -> bool:
        """Check for dangerous builtin function calls"""
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if calling a blocked builtin
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.blocked_builtins:
                        violations.append({
                            'line': node.lineno,
                            'function': node.func.id
                        })

                # Check for __import__('module')
                elif isinstance(node.func, ast.Name) and node.func.id == '__import__':
                    violations.append({
                        'line': node.lineno,
                        'function': '__import__'
                    })

        for violation in violations:
            report.add_error(
                "DISALLOWED_BUILTIN",
                f"Disallowed builtin function '{violation['function']}' called at line {violation['line']}",
                "CRITICAL"
            )

        return len(violations) == 0

    def _check_file_operations(self, tree: ast.AST, report: ReportGenerator) -> bool:
        """Check for file system operations"""
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for open() calls
                if isinstance(node.func, ast.Name) and node.func.id == 'open':
                    violations.append({
                        'line': node.lineno,
                        'operation': 'open()'
                    })

                # Check for file-related methods
                elif isinstance(node.func, ast.Attribute):
                    dangerous_attrs = ['write', 'read', 'remove', 'unlink', 'mkdir', 'rmdir']
                    if node.func.attr in dangerous_attrs:
                        violations.append({
                            'line': node.lineno,
                            'operation': f'.{node.func.attr}()'
                        })

        for violation in violations:
            report.add_error(
                "DISALLOWED_FILE_OPERATION",
                f"File operation '{violation['operation']}' found at line {violation['line']}",
                "CRITICAL"
            )

        return len(violations) == 0

    def _check_network_operations(self, tree: ast.AST, report: ReportGenerator) -> bool:
        """Check for network/socket operations"""
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    # Check for common network methods
                    network_methods = ['connect', 'send', 'recv', 'sendall', 'request', 'get', 'post']
                    if node.func.attr in network_methods:
                        violations.append({
                            'line': node.lineno,
                            'operation': f'.{node.func.attr}()'
                        })

        for violation in violations:
            report.add_error(
                "DISALLOWED_NETWORK_OPERATION",
                f"Network operation '{violation['operation']}' found at line {violation['line']}",
                "CRITICAL"
            )

        return len(violations) == 0

    def _check_dangerous_patterns(self, tree: ast.AST, report: ReportGenerator) -> bool:
        """Check for other dangerous code patterns"""
        violations = []

        for node in ast.walk(tree):
            # Check for exec/eval statements (as statements, not just calls)
            if isinstance(node, ast.Expr):
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Name):
                        if node.value.func.id in ['exec', 'eval', 'compile']:
                            violations.append({
                                'line': node.lineno,
                                'pattern': node.value.func.id
                            })

            # Check for attribute access to dangerous modules
            if isinstance(node, ast.Attribute):
                dangerous_attrs = ['__globals__', '__builtins__', '__code__', '__import__']
                if node.attr in dangerous_attrs:
                    violations.append({
                        'line': node.lineno,
                        'pattern': f'.{node.attr}'
                    })

        for violation in violations:
            report.add_error(
                "DANGEROUS_PATTERN",
                f"Dangerous code pattern '{violation['pattern']}' found at line {violation['line']}",
                "CRITICAL"
            )

        return len(violations) == 0

    def get_import_summary(self, code: str) -> Dict[str, Any]:
        """
        Get summary of imports in code

        Args:
            code: Python source code

        Returns:
            Dictionary with import statistics
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"error": "Syntax error in code"}

        imports = []
        from_imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    from_imports.append(node.module)

        return {
            "total_imports": len(imports) + len(from_imports),
            "imports": imports,
            "from_imports": from_imports
        }
